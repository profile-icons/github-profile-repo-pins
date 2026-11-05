use crate::{
    Result,
    config::{Config, OrderField},
    contributors,
    github::RepoSrc,
    hash::sha256_hex,
    i18n,
    model::{Repo, User},
    output::{self, PinOutput},
    render::{Renderer, media::MediaLoader, theme::Themes},
    stats::{self, HistReader, Policy},
};
use anyhow::Context;
use chrono::{Datelike, Timelike};
use rayon::prelude::*;
use serde::Deserialize;
use std::{collections::HashSet, path::PathBuf, time::Duration};

#[derive(Deserialize)]
pub struct Input {
    pub user: User,
    #[serde(default)]
    pub is_org: bool,
    #[serde(rename = "repositories", alias = "repos")]
    pub repos: Vec<Repo>,
}
pub struct Application<'a> {
    src: &'a dyn RepoSrc,
    config: Config,
}
impl<'a> Application<'a> {
    pub fn new(src: &'a dyn RepoSrc, config: Config) -> Self {
        Self { src, config }
    }
    pub fn run(&self) -> Result<usize> {
        let (user, is_org, mut repos): (User, bool, Vec<Repo>) =
            if let Some(input) = &self.config.args.input {
                let input: Input = serde_json::from_slice(&std::fs::read(input)?)
                    .context("invalid typed repository input JSON")?;
                (input.user, input.is_org, input.repos)
            } else {
                let user: User = self
                    .src
                    .authenticate(self.config.args.username.as_deref())?;
                let owner: &str = self.config.args.owner.as_deref().unwrap_or(&user.login);
                let is_org: bool = self.src.is_org(owner)?;
                let repos: Vec<Repo> = self.fetch(&user)?;
                (user, is_org, repos)
            };
        select(&mut repos, &self.config, user.db_id, chrono::Utc::now());
        let policy: Policy = if let Some(path) = &self.config.args.stats_policy {
            Policy::load(path)?
        } else {
            Policy::bundled()?
        };
        if self.config.args.input.is_none() {
            let pool: rayon::ThreadPool = rayon::ThreadPoolBuilder::new()
                .num_threads(usize::from(self.config.args.workers))
                .build()?;
            let hist: HistReader = HistReader::new(
                Duration::from_secs(self.config.args.git_timeout),
                policy.clone(),
            );
            pool.install(|| {
                repos.par_iter_mut().try_for_each(|repo| -> Result<()> {
                    let local: Result<Vec<stats::Commit>> =
                        hist.remote(&repo.full_name(), &self.config.args.token);
                    match local {
                        Ok(commits) => {
                            repo.local_contributors = Some(stats::score(&commits, &policy));
                        }
                        Err(err) if self.config.args.stats => {
                            return Err(err).with_context(|| {
                                format!("contribution statistics for {}", repo.full_name())
                            });
                        }
                        Err(_) => eprintln!(
                            "Local history unavailable for {}; using GitHub contributor counts",
                            repo.full_name()
                        ),
                    }
                    let res: Result<Vec<crate::model::Contributor>> = if self.config.args.stats {
                        self.src
                            .profiles(repo, repo.local_contributors.as_deref().unwrap_or(&[]))
                    } else {
                        self.src.contributors(repo)
                    };
                    match res {
                        Ok(vals) => repo.contributors = vals,
                        Err(_) => eprintln!(
                            "GitHub contributor profiles unavailable for {}",
                            repo.full_name()
                        ),
                    }
                    Ok(())
                })
            })?;
        }
        let themes: Themes = Themes::load(self.config.args.themes.as_deref())?;
        let mut media: MediaLoader = MediaLoader::new()?;
        let mut translator: Box<dyn i18n::Translator> = i18n::create(
            self.config.args.is_translate,
            self.config.args.is_nllb,
            self.config.args.model_cache.clone(),
            self.config.args.locales.as_deref(),
        )?;
        let mut renderer: Renderer<'_> = Renderer::new(&mut media, translator.as_mut())?;
        let owner: &str = self.config.args.owner.as_deref().unwrap_or(&user.login);
        let mut pins: Vec<PinOutput> = Vec::new();
        for repo in &repos {
            let full_name: String = repo.full_name();
            let background: Option<crate::config::ImgOptions> = self
                .config
                .background
                .as_ref()
                .and_then(|selection| selection.for_repo(&full_name))
                .map(crate::config::ImgSetting::options);
            let theme: &str = self
                .config
                .theme
                .as_ref()
                .and_then(|selection| selection.for_repo(&full_name))
                .map_or(
                    if background.is_some() {
                        "bg_img_contrast"
                    } else {
                        "github_soft"
                    },
                    String::as_str,
                );
            let contributors: Vec<crate::model::Contributor> =
                contributors::for_repo(repo, &user, &policy);
            let name: String = repo.display_name(owner);
            let svg: String = renderer.render(
                repo,
                &name,
                &contributors,
                self.config.args.stats,
                themes.get(theme)?,
                background.as_ref(),
            )?;
            pins.push(PinOutput {
                name,
                url: repo.display_url(),
                svg,
            });
        }
        let target: String = self
            .config
            .args
            .target_repo
            .clone()
            .unwrap_or_else(|| format!("{owner}/{owner}"));
        output::save(&self.config.args.output_dir, is_org, &target, &pins)?;
        let env: Option<PathBuf> = std::env::var_os("GITHUB_ENV").map(PathBuf::from);
        output::write_git_credentials(&user, env.as_deref())?;
        eprintln!(
            "Generated {} pins; GraphQL cost: {}",
            pins.len(),
            self.src.cost()
        );
        Ok(pins.len())
    }
    fn fetch(&self, user: &User) -> Result<Vec<Repo>> {
        if !self.config.repos.is_empty() {
            return self
                .config
                .repos
                .iter()
                .map(|name| self.src.repo(name))
                .collect();
        }
        let mut res: Vec<Repo> = self.src.pinned(&user.login)?;
        if res.len() < self.config.pin_count {
            let order: OrderField = self.config.args.order.unwrap_or(OrderField::Stars);
            if !self.config.args.not_owned {
                res.extend(self.src.repos(&user.login, order, false)?);
            }
            if !self.config.args.not_contributed {
                res.extend(self.src.repos(&user.login, order, true)?);
            }
        }
        Ok(res)
    }
}
pub fn select(
    repos: &mut Vec<Repo>,
    config: &Config,
    user_id: Option<u64>,
    now: chrono::DateTime<chrono::Utc>,
) {
    let mut seen: HashSet<String> = HashSet::new();
    repos.retain(|repo| seen.insert(repo.full_name().to_lowercase()));
    let order: Option<OrderField> = config
        .args
        .order
        .or_else(|| config.repos.is_empty().then_some(OrderField::Stars));
    match order {
        None => {
            repos.sort_by_key(|repo| {
                config
                    .repos
                    .iter()
                    .position(|name| name.eq_ignore_ascii_case(&repo.full_name()))
                    .unwrap_or(usize::MAX)
            });
            repos.retain(|repo| {
                config
                    .repos
                    .iter()
                    .any(|name| name.eq_ignore_ascii_case(&repo.full_name()))
            });
        }
        Some(OrderField::Name) => repos.sort_by(|left, right| left.name.cmp(&right.name)),
        Some(OrderField::Stars) => {
            repos.sort_by_key(|repo| std::cmp::Reverse(repo.stargazer_count))
        }
        Some(OrderField::CreatedAt) => {
            repos.sort_by(|left, right| right.created_at.cmp(&left.created_at))
        }
        Some(OrderField::UpdatedAt) => {
            repos.sort_by(|left, right| right.updated_at.cmp(&left.updated_at))
        }
        Some(OrderField::PushedAt) => {
            repos.sort_by(|left, right| right.pushed_at.cmp(&left.pushed_at))
        }
        Some(OrderField::Random) => {
            let seed: String = format!(
                "{}:{}:{}:{}",
                user_id.unwrap_or(0),
                now.month(),
                now.day(),
                now.hour()
            );
            repos.sort_by_cached_key(|repo| sha256_hex(&format!("{seed}:{}", repo.full_name())));
        }
    }
    repos.truncate(config.pin_count);
}
