use crate::Result;
use anyhow::{Context, bail, ensure};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, path::PathBuf, str::FromStr};

pub const MAX_PINS: usize = 100;
pub const DEFAULT_PINS: usize = 6;

#[derive(Parser)]
#[command(
    version,
    about = "Generate GitHub profile repository pin SVGs and update README markers"
)]
pub struct Arguments {
    #[arg(long, env = "GH_API_TOKEN", hide_env_values = true, default_value = "")]
    pub token: String,
    #[arg(long, env = "GH_USERNAME")]
    pub username: Option<String>,
    #[arg(long, env = "GH_REPO_OWNER")]
    pub owner: Option<String>,
    #[arg(long, env = "REPO_NAMES_EXCLUSIVE")]
    pub repos: Option<String>,
    #[arg(long, env = "THEME")]
    pub theme: Option<String>,
    #[arg(long, env = "BG_IMG")]
    pub img: Option<String>,
    #[arg(long, env = "NUM_REPO_PINS", value_parser = parse_pin_count)]
    pub pins: Option<usize>,
    #[arg(long, env = "REPO_PIN_ORDER")]
    pub order: Option<OrderField>,
    #[arg(long, env = "IS_EXCLUDE_REPOS_OWNED", default_value = "false", value_parser = parse_bool)]
    pub not_owned: bool,
    #[arg(long, env = "IS_EXCLUDE_REPOS_CONTRIBUTED", default_value = "false", value_parser = parse_bool)]
    pub not_contributed: bool,
    #[arg(long, env = "IS_CONTRIBUTION_STATS", default_value = "false", value_parser = parse_bool)]
    pub stats: bool,
    #[arg(long, env = "IS_TRANSLATE", default_value = "false", value_parser = parse_bool)]
    pub is_translate: bool,
    #[arg(long, env = "IS_NLLB", default_value = "false", value_parser = parse_bool)]
    pub is_nllb: bool,
    #[arg(long, env = "GH_REPO_NAME")]
    pub target_repo: Option<String>,
    #[arg(long, default_value = ".")]
    pub output_dir: PathBuf,
    #[arg(long)]
    pub themes: Option<PathBuf>,
    #[arg(long)]
    pub stats_policy: Option<PathBuf>,
    #[arg(long, env = "REPO_PINS_WORKERS", default_value = "4", value_parser = clap::value_parser!(u16).range(1..=32))]
    pub workers: u16,
    #[arg(long, env = "REPO_PINS_TIMEOUT", default_value = "180", value_parser = clap::value_parser!(u64).range(1..=3600))]
    pub git_timeout: u64,
    #[arg(
        long,
        env = "REPO_PINS_GRAPHQL_URL",
        default_value = "https://api.github.com/graphql"
    )]
    pub graphql_url: String,
    #[arg(
        long,
        env = "REPO_PINS_API_URL",
        default_value = "https://api.github.com"
    )]
    pub api_url: String,
    #[arg(long)]
    pub input: Option<PathBuf>,
    #[arg(long, env = "REPO_PINS_MODEL_CACHE")]
    pub model_cache: Option<PathBuf>,
    #[arg(long)]
    pub locales: Option<String>,
}

pub fn parse_bool(val: &str) -> std::result::Result<bool, String> {
    match val.trim().to_ascii_lowercase().as_str() {
        "" | "false" | "0" | "no" | "off" => Ok(false),
        "true" | "1" | "yes" | "on" => Ok(true),
        _ => Err("expected true/false, 1/0, yes/no or on/off".to_owned()),
    }
}
fn parse_pin_count(val: &str) -> std::result::Result<usize, String> {
    if val.is_empty() {
        return Ok(DEFAULT_PINS);
    }
    let count: usize = val
        .parse()
        .map_err(|_| "pin count must be a positive integer".to_owned())?;
    if count == 0 {
        return Err("pin count must be greater than zero".to_owned());
    }
    Ok(count.min(MAX_PINS))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
pub enum OrderField {
    #[serde(rename = "stargazerCount")]
    Stars,
    Name,
    CreatedAt,
    UpdatedAt,
    PushedAt,
    Random,
}
impl FromStr for OrderField {
    type Err = String;
    fn from_str(val: &str) -> std::result::Result<Self, Self::Err> {
        match val.to_ascii_lowercase().as_str() {
            "stargazercount" | "stars" | "stargazers" | "" => Ok(Self::Stars),
            "name" => Ok(Self::Name),
            "createdat" => Ok(Self::CreatedAt),
            "updatedat" => Ok(Self::UpdatedAt),
            "pushedat" => Ok(Self::PushedAt),
            "random" => Ok(Self::Random),
            _ => Err(format!("unknown repository order: {val}")),
        }
    }
}
impl OrderField {
    pub fn graphql(self) -> &'static str {
        match self {
            Self::Stars | Self::Random => "STARGAZERS",
            Self::Name => "NAME",
            Self::CreatedAt => "CREATED_AT",
            Self::UpdatedAt => "UPDATED_AT",
            Self::PushedAt => "PUSHED_AT",
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(untagged)]
pub enum Selection<T> {
    All(T),
    Repos(BTreeMap<String, T>),
}
impl<T> Selection<T> {
    pub fn for_repo(&self, full_name: &str) -> Option<&T> {
        match self {
            Self::All(val) => Some(val),
            Self::Repos(vals) => vals
                .iter()
                .find(|(name, _)| name.eq_ignore_ascii_case(full_name))
                .map(|(_, val)| val),
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ImgMode {
    Cover,
    Contain,
    #[default]
    Stretch,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ImgOptions {
    pub img: String,
    #[serde(default = "default_alignment")]
    pub align: String,
    #[serde(default)]
    pub mode: ImgMode,
    #[serde(default = "default_opacity")]
    pub opacity: f32,
}
fn default_alignment() -> String {
    "xMidYMid".to_owned()
}
fn default_opacity() -> f32 {
    0.25
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(untagged)]
pub enum ImgSetting {
    Source(String),
    Options(ImgOptions),
}
impl ImgSetting {
    pub fn options(&self) -> ImgOptions {
        match self {
            Self::Options(options) => options.clone(),
            Self::Source(src) => ImgOptions {
                img: src.clone(),
                align: default_alignment(),
                mode: ImgMode::Stretch,
                opacity: default_opacity(),
            },
        }
    }
}
impl ImgOptions {
    pub fn aspect_ratio(&self) -> Result<String> {
        let alignment: &str = match self.align.to_ascii_lowercase().as_str() {
            "xminymin" => "xMinYMin",
            "xmidymin" => "xMidYMin",
            "xmaxymin" => "xMaxYMin",
            "xminymid" => "xMinYMid",
            "xmidymid" => "xMidYMid",
            "xmaxymid" => "xMaxYMid",
            "xminymax" => "xMinYMax",
            "xmidymax" => "xMidYMax",
            "xmaxymax" => "xMaxYMax",
            _ => bail!("invalid background alignment: {}", self.align),
        };
        ensure!(
            !self.img.trim().is_empty(),
            "background image source cannot be empty"
        );
        ensure!(
            self.opacity.is_finite() && (0.0..=1.0).contains(&self.opacity),
            "background opacity must be between zero and one"
        );
        Ok(match self.mode {
            ImgMode::Cover => format!("{alignment} slice"),
            ImgMode::Contain => format!("{alignment} meet"),
            ImgMode::Stretch => "none".to_owned(),
        })
    }
}

pub struct Config {
    pub args: Arguments,
    pub repos: Vec<String>,
    pub theme: Option<Selection<String>>,
    pub background: Option<Selection<ImgSetting>>,
    pub pin_count: usize,
}
impl Config {
    pub fn new(mut args: Arguments) -> Result<Self> {
        for val in [&mut args.username, &mut args.owner, &mut args.target_repo] {
            if val.as_ref().is_some_and(|text| text.trim().is_empty()) {
                *val = None;
            }
        }
        let repos: Vec<String> = args
            .repos
            .as_deref()
            .unwrap_or("")
            .split(',')
            .map(str::trim)
            .filter(|name| !name.is_empty())
            .map(str::to_owned)
            .collect();
        for name in &repos {
            validate_repo_name(name)?;
        }
        if let Some(name) = &args.target_repo {
            validate_repo_name(name)?;
        }
        let theme: Option<Selection<String>> = parse_selection(args.theme.as_deref())?;
        let background: Option<Selection<ImgSetting>> = parse_selection(args.img.as_deref())?;
        if let Some(setting) = &background {
            let vals: Vec<&ImgSetting> = match setting {
                Selection::All(val) => vec![val],
                Selection::Repos(vals) => vals.values().collect(),
            };
            for val in vals {
                val.options().aspect_ratio()?;
            }
        }
        let pin_count: usize = args
            .pins
            .unwrap_or(if repos.is_empty() {
                DEFAULT_PINS
            } else {
                repos.len()
            })
            .min(MAX_PINS);
        ensure!(
            args.input.is_some() || !args.token.trim().is_empty(),
            "provide --token or GH_API_TOKEN"
        );
        Ok(Self {
            args,
            repos,
            theme,
            background,
            pin_count,
        })
    }
}
fn parse_selection<T: serde::de::DeserializeOwned>(
    raw: Option<&str>,
) -> Result<Option<Selection<T>>> {
    let Some(val) = raw.map(str::trim).filter(|val| !val.is_empty()) else {
        return Ok(None);
    };
    let encoded: String = if val.starts_with('{') || val.starts_with('"') {
        val.to_owned()
    } else {
        serde_json::to_string(val)?
    };
    Ok(Some(
        serde_json::from_str(&encoded).context("invalid theme or background configuration")?,
    ))
}
pub fn validate_repo_name(val: &str) -> Result<()> {
    let parts: Vec<&str> = val.split('/').collect();
    ensure!(
        parts.len() == 2
            && parts.iter().all(|part| !part.is_empty()
                && *part != "."
                && *part != ".."
                && part.chars().all(
                    |character| character.is_ascii_alphanumeric() || "._-".contains(character)
                )),
        "expected owner/repository, got {val}"
    );
    Ok(())
}
