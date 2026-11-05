use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Repo {
    pub name: String,
    pub url: String,
    pub owner: Owner,
    #[serde(default)]
    pub stargazer_count: u64,
    #[serde(default)]
    pub fork_count: u64,
    #[serde(default)]
    pub issues: Count,
    #[serde(default)]
    pub issues_help: Count,
    #[serde(default)]
    pub pull_requests: Count,
    pub description: Option<String>,
    #[serde(rename = "primaryLanguage", alias = "primaryLang")]
    pub primary_lang: Option<Lang>,
    #[serde(default)]
    pub is_fork: bool,
    pub parent: Option<Parent>,
    #[serde(default)]
    pub is_template: bool,
    #[serde(default)]
    pub is_archived: bool,
    #[serde(default)]
    pub is_private: bool,
    pub pushed_at: Option<String>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub homepage_url: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub contributors: Vec<Contributor>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub local_contributors: Option<Vec<Contributor>>,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Owner {
    pub login: String,
}
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Count {
    pub total_count: u64,
}
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Lang {
    pub name: String,
    pub color: Option<String>,
}
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Parent {
    pub name_with_owner: String,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Identity {
    #[serde(default)]
    pub names: BTreeSet<String>,
    #[serde(default)]
    pub emails: BTreeSet<String>,
    #[serde(default)]
    pub login: String,
    pub user_id: Option<u64>,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Contributor {
    #[serde(flatten)]
    pub identity: Identity,
    pub avatar_url: Option<String>,
    #[serde(default)]
    pub additions: f64,
    #[serde(default)]
    pub commit_count: u64,
    #[serde(default)]
    pub last_commit_at: String,
    #[serde(default)]
    pub profile_commits: Vec<String>,
    #[serde(default)]
    pub is_automated: bool,
    #[serde(default)]
    pub is_user: bool,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct User {
    #[serde(default)]
    pub login: String,
    pub name: Option<String>,
    #[serde(rename = "databaseId", alias = "dbId")]
    pub db_id: Option<u64>,
    pub avatar_url: Option<String>,
}

impl Repo {
    pub fn full_name(&self) -> String {
        format!("{}/{}", self.owner.login, self.name)
    }
    pub fn display_name(&self, profile_owner: &str) -> String {
        if self.owner.login.eq_ignore_ascii_case(profile_owner) {
            self.name.clone()
        } else {
            self.full_name()
        }
    }
    pub fn display_url(&self) -> String {
        if !self.is_private {
            return self.url.clone();
        }
        if let Some(url) = self.homepage_url.as_ref().filter(|url| {
            reqwest::Url::parse(url)
                .is_ok_and(|parsed| parsed.scheme() == "https" && parsed.host_str().is_some())
        }) {
            return url.clone();
        }
        let host: String = format!("{}.github.io", self.owner.login.to_lowercase());
        if self.name.eq_ignore_ascii_case(&host) || self.name == ".github" {
            format!("https://{host}")
        } else {
            format!("https://{host}/{}", self.name)
        }
    }
}
