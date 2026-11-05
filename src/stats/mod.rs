mod attribution;
mod git;
mod provenance;
mod sequence;
mod structure;

use crate::{
    Result, contributors,
    model::{Contributor, Identity},
};
pub use git::HistReader;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
    sync::Arc,
};

pub type LineKey = (String, String);
pub type Mask = BTreeMap<LineKey, usize>;

#[derive(Clone, Debug, Default, Deserialize)]
pub struct AddedLine {
    pub key: LineKey,
    pub row: Option<usize>,
}
#[derive(Clone, Debug, Default, Deserialize)]
pub struct Commit {
    pub hash: String,
    pub tree: String,
    pub parents: Vec<String>,
    pub authors: Vec<Identity>,
    pub additions: Vec<AddedLine>,
    pub deletions: Vec<LineKey>,
    pub renames: BTreeMap<String, String>,
    pub snapshots: BTreeMap<String, Arc<str>>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Policy {
    pub ignore_path: BTreeSet<String>,
    pub ignore_base: BTreeSet<String>,
    pub ignore_sfx: Vec<String>,
    pub ignore_sfx_bin: Vec<String>,
    pub auto_bot_name: BTreeSet<String>,
    pub auto_bot_email: BTreeSet<String>,
    pub ai_agent_names: BTreeSet<String>,
    pub ai_agent_emails: BTreeSet<String>,
}
impl Policy {
    pub fn bundled() -> Result<Self> {
        Ok(serde_json::from_str(include_str!(
            "../../files/stats.json"
        ))?)
    }
    pub fn load(path: &Path) -> Result<Self> {
        Ok(serde_json::from_slice(&std::fs::read(path)?)?)
    }
    pub(crate) fn path_specs(&self) -> Vec<String> {
        let mut paths: Vec<String> = vec![".".to_owned()];
        paths.extend(
            self.ignore_path
                .iter()
                .map(|dir| format!(":(exclude,icase,glob)**/{dir}/**")),
        );
        paths.extend(
            self.ignore_base
                .iter()
                .map(|name| format!(":(exclude,icase,glob)**/{name}")),
        );
        paths.extend(
            self.ignore_sfx
                .iter()
                .chain(&self.ignore_sfx_bin)
                .map(|suffix| format!(":(exclude,icase,glob)**/*{suffix}")),
        );
        paths.push(":(exclude,icase,glob)**/useractionhistory*.xml".to_owned());
        paths
    }
    pub fn eligible(&self, path: &str) -> bool {
        let path: String = path.replace('\\', "/").to_lowercase();
        let parts: Vec<&str> = path.split('/').collect();
        let name: &str = parts.last().copied().unwrap_or("");
        !name.is_empty()
            && !parts[..parts.len().saturating_sub(1)]
                .iter()
                .any(|part| self.ignore_path.contains(*part))
            && !self.ignore_base.contains(name)
            && !(name.starts_with("useractionhistory") && name.ends_with(".xml"))
            && !self
                .ignore_sfx
                .iter()
                .chain(&self.ignore_sfx_bin)
                .any(|suffix| name.ends_with(suffix))
    }
    pub fn is_ai(&self, identity: &Identity) -> bool {
        identity
            .names
            .iter()
            .chain(std::iter::once(&identity.login))
            .any(|name| self.ai_agent_names.contains(&contributors::norm(name)))
            || identity.emails.iter().any(|email| {
                let email: String = contributors::norm(email);
                self.ai_agent_emails.contains(&email)
                    || email
                        .strip_suffix("@users.noreply.github.com")
                        .is_some_and(|local| {
                            self.ai_agent_names
                                .contains(local.rsplit('+').next().unwrap_or(local))
                        })
            })
    }
    pub fn is_automated(&self, identity: &Identity) -> bool {
        self.is_ai(identity)
            || identity
                .names
                .iter()
                .chain(std::iter::once(&identity.login))
                .any(|name| {
                    self.auto_bot_name.contains(&contributors::norm(name))
                        || name.ends_with("[bot]")
                })
            || identity.emails.iter().any(|email| {
                self.auto_bot_email.contains(&contributors::norm(email))
                    || email
                        .split('@')
                        .next()
                        .is_some_and(|local| local.contains("[bot]"))
            })
    }
}

pub(crate) struct Ancestry<'a> {
    commits: &'a [Commit],
    indices: BTreeMap<&'a str, usize>,
    cache: BTreeMap<(usize, usize), bool>,
}
impl<'a> Ancestry<'a> {
    fn new(commits: &'a [Commit]) -> Self {
        Self {
            commits,
            indices: commits
                .iter()
                .enumerate()
                .map(|(idx, commit)| (commit.hash.as_str(), idx))
                .collect(),
            cache: BTreeMap::new(),
        }
    }
    fn contains(&mut self, src: usize, target: usize) -> bool {
        if src == target {
            return true;
        }
        if src > target {
            return false;
        }
        if let Some(val) = self.cache.get(&(src, target)) {
            return *val;
        }
        let mut pending: Vec<&str> = self.commits[target]
            .parents
            .iter()
            .map(String::as_str)
            .collect();
        let mut seen: BTreeSet<&str> = BTreeSet::new();
        let mut res: bool = false;
        while let Some(hash) = pending.pop() {
            if !seen.insert(hash) {
                continue;
            }
            let Some(idx) = self.indices.get(hash).copied() else {
                continue;
            };
            if idx == src {
                res = true;
                break;
            }
            if idx > src {
                pending.extend(self.commits[idx].parents.iter().map(String::as_str));
            }
        }
        self.cache.insert((src, target), res);
        res
    }
}

pub fn score(commits: &[Commit], policy: &Policy) -> Vec<Contributor> {
    let additions: Vec<usize> = retained_additions(commits);
    let mut sigs: BTreeSet<Vec<LineKey>> = BTreeSet::new();
    let mut credited: Vec<(Vec<Identity>, usize, &str)> = Vec::new();
    for (idx, commit) in commits.iter().enumerate() {
        let mut sig: Vec<LineKey> = commit
            .additions
            .iter()
            .map(|line| (format!("+{}", line.key.0), line.key.1.clone()))
            .chain(
                commit
                    .deletions
                    .iter()
                    .map(|(path, text)| (format!("-{path}"), text.clone())),
            )
            .collect();
        sig.sort();
        let count: usize = additions[idx];
        if commit.parents.len() > 1 || count == 0 || !sigs.insert(sig) {
            continue;
        }
        let ai: Vec<Identity> = commit
            .authors
            .iter()
            .filter(|identity| policy.is_ai(identity))
            .cloned()
            .collect();
        let authors: Vec<Identity> = if ai.is_empty() {
            commit.authors.clone()
        } else {
            ai
        };
        credited.push((authors, count, &commit.hash));
    }
    let obs: Vec<Identity> = credited
        .iter()
        .flat_map(|(authors, _, _)| authors.clone())
        .collect();
    let roots: Vec<usize> = contributors::resolve(&obs, false);
    let mut res: BTreeMap<usize, Contributor> = BTreeMap::new();
    let mut offset: usize = 0;
    for (authors, count, hash) in credited {
        let author_count: usize = authors.len();
        let unique: BTreeSet<usize> = roots[offset..offset + authors.len()]
            .iter()
            .copied()
            .collect();
        let share: f64 = if unique.is_empty() {
            0.0
        } else {
            count as f64 / unique.len() as f64
        };
        for (author_idx, identity) in authors.into_iter().enumerate() {
            let root: usize = roots[offset + author_idx];
            let contributor: &mut Contributor = res.entry(root).or_default();
            contributor.identity.names.extend(identity.names);
            contributor.identity.emails.extend(identity.emails);
        }
        for root in unique {
            let contributor: &mut Contributor = res.entry(root).or_default();
            contributor.additions += share;
            contributor.commit_count += 1;
            contributor.profile_commits.retain(|sha| sha != hash);
            contributor.profile_commits.insert(0, hash.to_owned());
            contributor.profile_commits.truncate(3);
        }
        offset += author_count;
    }
    let mut res: Vec<Contributor> = res.into_values().collect();
    for contributor in &mut res {
        contributor.identity.login = contributor
            .identity
            .names
            .iter()
            .max_by_key(|name| (name.len(), *name))
            .cloned()
            .unwrap_or_else(|| "unknown".to_owned());
    }
    res.sort_by(|left, right| {
        right
            .additions
            .total_cmp(&left.additions)
            .then_with(|| left.identity.login.cmp(&right.identity.login))
    });
    res
}

pub fn retained_additions(commits: &[Commit]) -> Vec<usize> {
    let masks: Vec<Mask> = attribution::exclusions(commits);
    commits
        .iter()
        .zip(&masks)
        .map(|(commit, mask)| {
            commit
                .additions
                .len()
                .saturating_sub(mask.values().sum::<usize>())
        })
        .collect()
}
