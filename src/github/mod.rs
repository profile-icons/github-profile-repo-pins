use crate::{
    Result,
    config::OrderField,
    contributors,
    model::{Contributor, Count, Identity, Repo, User},
};
use anyhow::{Context, bail, ensure};
use reqwest::{
    blocking::Client,
    header::{AUTHORIZATION, HeaderMap, HeaderValue as HeaderVal},
};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use std::{
    collections::{BTreeMap, HashSet},
    sync::atomic::{AtomicU64, Ordering},
    time::Duration,
};

const FIELDS: &str = "name url owner { login } stargazerCount forkCount issues(states:OPEN){totalCount} issuesHelp:issues(states:OPEN,labels:[\"help wanted\"]){totalCount} pullRequests(states:OPEN){totalCount} description primaryLanguage{name color} isFork parent{nameWithOwner} isTemplate isArchived isPrivate pushedAt createdAt updatedAt homepageUrl";
const AUTHOR_FIELDS: &str = "committedDate parents(first:2){totalCount} authors(first:100){nodes{name email user{login databaseId avatarUrl}}}";

pub trait RepoSrc: Sync {
    fn authenticate(&self, username: Option<&str>) -> Result<User>;
    fn is_org(&self, owner: &str) -> Result<bool>;
    fn pinned(&self, username: &str) -> Result<Vec<Repo>>;
    fn repos(&self, username: &str, order: OrderField, contributed: bool) -> Result<Vec<Repo>>;
    fn repo(&self, name: &str) -> Result<Repo>;
    fn contributors(&self, repo: &Repo) -> Result<Vec<Contributor>>;
    fn profiles(&self, repos: &Repo, contributors: &[Contributor]) -> Result<Vec<Contributor>>;
    fn cost(&self) -> u64;
}

pub struct GitHubClient {
    client: Client,
    graphql_url: reqwest::Url,
    api_url: reqwest::Url,
    cost: AtomicU64,
}
#[derive(Default, Serialize)]
struct Variables<'a> {
    #[serde(skip_serializing_if = "Option::is_none")]
    login: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    owner: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    name: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    field: Option<&'a str>,
    after: Option<&'a str>,
}
#[derive(Serialize)]
struct Request<'a> {
    query: &'a str,
    variables: Variables<'a>,
}
#[derive(Deserialize)]
struct Response<T> {
    data: Option<T>,
    #[serde(default)]
    errors: Vec<ApiError>,
}
#[derive(Deserialize)]
struct ApiError {
    message: String,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Rated<T> {
    #[serde(default)]
    rate_limit: RateLimit,
    #[serde(flatten)]
    val: T,
}
#[derive(Default, Deserialize)]
struct RateLimit {
    #[serde(default)]
    cost: u64,
}
#[derive(Deserialize)]
struct ViewerData {
    viewer: User,
}
#[derive(Deserialize)]
struct UserData {
    user: Option<UserNode>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct UserNode {
    #[serde(flatten)]
    profile: User,
    pinned_items: Option<Connection>,
    #[serde(rename = "repositories", alias = "repos")]
    repos: Option<Connection>,
    #[serde(rename = "repositoriesContributedTo", alias = "reposContributedTo")]
    repos_contributed_to: Option<Connection>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct OwnerData {
    #[serde(rename = "repositoryOwner", alias = "repoOwner")]
    repo_owner: Option<OwnerType>,
}
#[derive(Deserialize)]
struct OwnerType {
    #[serde(rename = "__typename")]
    kind: String,
}
#[derive(Default, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Connection {
    #[serde(default)]
    nodes: Vec<Option<Repo>>,
    #[serde(default)]
    edges: Vec<Edge>,
    #[serde(default)]
    page_info: PageInfo,
}
#[derive(Deserialize)]
struct Edge {
    node: Option<Repo>,
}
#[derive(Default, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PageInfo {
    #[serde(default)]
    has_next_page: bool,
    end_cursor: Option<String>,
}
#[derive(Deserialize)]
struct RepoData {
    #[serde(rename = "repository", alias = "repo")]
    repo: Option<Repo>,
}
#[derive(Deserialize)]
struct HistData {
    #[serde(rename = "repository", alias = "repo")]
    repo: Option<HistRepo>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct HistRepo {
    default_branch_ref: Option<Branch>,
}
#[derive(Deserialize)]
struct Branch {
    target: HistTarget,
}
#[derive(Deserialize)]
struct HistTarget {
    #[serde(rename = "history", alias = "hist")]
    hist: Hist,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Hist {
    nodes: Vec<Option<CommitAuthors>>,
    page_info: PageInfo,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct CommitAuthors {
    committed_date: String,
    #[serde(default)]
    parents: Count,
    authors: Authors,
}
#[derive(Deserialize)]
struct Authors {
    nodes: Vec<Option<Actor>>,
}
#[derive(Deserialize)]
struct Actor {
    name: Option<String>,
    email: Option<String>,
    user: Option<User>,
}
#[derive(Deserialize)]
struct RestContributor {
    login: Option<String>,
    name: Option<String>,
    email: Option<String>,
    id: Option<u64>,
    avatar_url: Option<String>,
    #[serde(default)]
    contributions: u64,
    #[serde(rename = "type")]
    kind: Option<String>,
}
#[derive(Deserialize)]
struct ProfileData {
    #[serde(rename = "repository", alias = "repo")]
    repo: Option<BTreeMap<String, Option<CommitAuthors>>>,
}

impl GitHubClient {
    pub fn new(token: &str, graphql_url: &str, api_url: &str) -> Result<Self> {
        let mut authorization: HeaderVal =
            HeaderVal::from_str(&format!("Bearer {token}")).context("invalid API token")?;
        authorization.set_sensitive(true);
        let mut headers: HeaderMap = HeaderMap::new();
        headers.insert(AUTHORIZATION, authorization);
        let client: Client = Client::builder()
            .default_headers(headers)
            .user_agent("github-profile-repo-pins/2.0")
            .timeout(Duration::from_secs(30))
            .connect_timeout(Duration::from_secs(10))
            .redirect(reqwest::redirect::Policy::none())
            .build()?;
        let graphql_url: reqwest::Url = parse_endpoint(graphql_url)?;
        let api_url: reqwest::Url = parse_endpoint(&format!("{}/", api_url.trim_end_matches('/')))?;
        Ok(Self {
            client,
            graphql_url,
            api_url,
            cost: AtomicU64::new(0),
        })
    }
    fn query<T: DeserializeOwned>(&self, query: &str, variables: Variables<'_>) -> Result<T> {
        let res: reqwest::blocking::Response = self
            .client
            .post(self.graphql_url.clone())
            .json(&Request { query, variables })
            .send()
            .context("GitHub GraphQL request failed")?;
        let status: reqwest::StatusCode = res.status();
        ensure!(status.is_success(), "GitHub GraphQL returned HTTP {status}");
        let payload: Response<Rated<T>> = res.json().context("invalid GitHub GraphQL response")?;
        if !payload.errors.is_empty() {
            bail!(
                "GitHub GraphQL: {}",
                payload
                    .errors
                    .iter()
                    .map(|error| error.message.as_str())
                    .collect::<Vec<&str>>()
                    .join("; ")
            );
        }
        let data: Rated<T> = payload.data.context("GitHub GraphQL returned no data")?;
        self.cost.fetch_add(data.rate_limit.cost, Ordering::Relaxed);
        Ok(data.val)
    }
    fn hist(&self, repo: &Repo) -> Result<Vec<Contributor>> {
        let query: String = "query($owner:String!,$name:String!,$after:String){rateLimit{cost} repository(owner:$owner,name:$name){defaultBranchRef{target{... on Commit{history(first:100,after:$after){pageInfo{hasNextPage endCursor} nodes{AUTHOR_FIELDS}}}}}}}".replace("AUTHOR_FIELDS", AUTHOR_FIELDS);
        let mut cursor: Option<String> = None;
        let mut seen: HashSet<String> = HashSet::new();
        let mut observations: Vec<Contributor> = Vec::new();
        let mut commits: Vec<Vec<usize>> = Vec::new();
        loop {
            let data: HistData = self.query(
                &query,
                Variables {
                    owner: Some(&repo.owner.login),
                    name: Some(&repo.name),
                    after: cursor.as_deref(),
                    ..Variables::default()
                },
            )?;
            let Some(branch) = data.repo.and_then(|repo| repo.default_branch_ref) else {
                break;
            };
            for commit in branch
                .target
                .hist
                .nodes
                .into_iter()
                .flatten()
                .filter(|commit| commit.parents.total_count <= 1)
            {
                let mut indices: Vec<usize> = Vec::new();
                for actor in commit.authors.nodes.into_iter().flatten() {
                    indices.push(observations.len());
                    observations.push(actor.contributor(&commit.committed_date));
                }
                commits.push(indices);
            }
            if !advance(branch.target.hist.page_info, &mut cursor, &mut seen)? {
                break;
            }
        }
        Ok(contributors::aggregate_obs(observations, &commits))
    }
    fn rest_contributors(&self, repo: &Repo) -> Result<Vec<Contributor>> {
        let url: reqwest::Url = self.api_url.join(&format!(
            "repos/{}/{}/contributors",
            repo.owner.login, repo.name
        ))?;
        let mut result: Vec<Contributor> = Vec::new();
        for page in 1_u32.. {
            let mut res: Option<reqwest::blocking::Response> = None;
            for attempt in 0_u32..4 {
                let current: reqwest::blocking::Response = self
                    .client
                    .get(url.clone())
                    .query(&[("anon", 1), ("per_page", 100), ("page", page)])
                    .send()?;
                if current.status() == reqwest::StatusCode::ACCEPTED {
                    std::thread::sleep(Duration::from_secs(1_u64 << attempt));
                } else {
                    res = Some(current.error_for_status()?);
                    break;
                }
            }
            let res: reqwest::blocking::Response =
                res.context("GitHub contributor statistics are still pending after four attempts")?;
            if res.status() == reqwest::StatusCode::NO_CONTENT {
                break;
            }
            let vals: Vec<RestContributor> = res.json()?;
            if vals.is_empty() {
                break;
            }
            for val in vals {
                result.push(Contributor {
                    identity: Identity {
                        login: val.login.unwrap_or_default(),
                        user_id: val.id,
                        names: val.name.into_iter().collect(),
                        emails: val.email.into_iter().collect(),
                    },
                    commit_count: val.contributions,
                    avatar_url: val.avatar_url,
                    is_automated: val.kind.as_deref() == Some("Bot"),
                    ..Contributor::default()
                });
            }
        }
        Ok(result)
    }
}
fn parse_endpoint(val: &str) -> Result<reqwest::Url> {
    let url: reqwest::Url = reqwest::Url::parse(val)?;
    ensure!(
        url.scheme() == "https"
            || (url.scheme() == "http"
                && matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"))),
        "API endpoints require HTTPS (HTTP is allowed for local fixtures)"
    );
    ensure!(
        url.username().is_empty() && url.password().is_none(),
        "API endpoint must not contain credentials"
    );
    Ok(url)
}
fn advance(
    page: PageInfo,
    cursor: &mut Option<String>,
    seen: &mut HashSet<String>,
) -> Result<bool> {
    if !page.has_next_page {
        return Ok(false);
    }
    let next: String = page
        .end_cursor
        .filter(|val| !val.is_empty())
        .context("GitHub pagination returned no cursor")?;
    ensure!(
        seen.insert(next.clone()),
        "GitHub pagination repeated a cursor"
    );
    *cursor = Some(next);
    Ok(true)
}
impl Actor {
    fn contributor(self, date: &str) -> Contributor {
        let user: User = self.user.unwrap_or_default();
        Contributor {
            identity: Identity {
                names: self.name.into_iter().collect(),
                emails: self.email.into_iter().collect(),
                login: user.login,
                user_id: user.db_id,
            },
            avatar_url: user.avatar_url,
            last_commit_at: date.to_owned(),
            ..Contributor::default()
        }
    }
}
impl RepoSrc for GitHubClient {
    fn authenticate(&self, username: Option<&str>) -> Result<User> {
        let viewer: ViewerData = self.query(
            "query { rateLimit{cost} viewer{login} }",
            Variables::default(),
        )?;
        let login: &str = username.unwrap_or(&viewer.viewer.login);
        let data: UserData = self.query("query($login:String!){rateLimit{cost} user(login:$login){login name databaseId avatarUrl}}", Variables { login: Some(login), ..Variables::default() })?;
        Ok(data.user.context("GitHub user was not found")?.profile)
    }
    fn is_org(&self, owner: &str) -> Result<bool> {
        let data: OwnerData = self.query(
            "query($login:String!){rateLimit{cost} repositoryOwner(login:$login){__typename}}",
            Variables {
                login: Some(owner),
                ..Variables::default()
            },
        )?;
        Ok(data
            .repo_owner
            .context("GitHub repository owner was not found")?
            .kind
            == "Organization")
    }
    fn pinned(&self, username: &str) -> Result<Vec<Repo>> {
        let query: String = format!(
            "query($login:String!){{rateLimit{{cost}} user(login:$login){{pinnedItems(first:100,types:[REPOSITORY]){{edges{{node{{... on Repository{{{FIELDS}}}}}}}}}}}}}"
        );
        let data: UserData = self.query(
            &query,
            Variables {
                login: Some(username),
                ..Variables::default()
            },
        )?;
        Ok(data
            .user
            .and_then(|user| user.pinned_items)
            .unwrap_or_default()
            .edges
            .into_iter()
            .filter_map(|edge| edge.node)
            .collect())
    }
    fn repos(&self, username: &str, order: OrderField, contributed: bool) -> Result<Vec<Repo>> {
        let field: &str = if contributed {
            "repositoriesContributedTo"
        } else {
            "repositories"
        };
        let extra: &str = if contributed {
            ",contributionTypes:[COMMIT]"
        } else {
            ""
        };
        let query: String = format!(
            "query($login:String!,$after:String,$field:RepositoryOrderField!){{rateLimit{{cost}} user(login:$login){{{field}(first:100,after:$after,orderBy:{{field:$field,direction:DESC}}{extra}){{pageInfo{{hasNextPage endCursor}} nodes{{{FIELDS}}}}}}}}}"
        );
        let mut result: Vec<Repo> = Vec::new();
        let mut cursor: Option<String> = None;
        let mut seen: HashSet<String> = HashSet::new();
        loop {
            let data: UserData = self.query(
                &query,
                Variables {
                    login: Some(username),
                    field: Some(order.graphql()),
                    after: cursor.as_deref(),
                    ..Variables::default()
                },
            )?;
            let user: UserNode = data.user.context("GitHub user was not found")?;
            let connection: Connection = if contributed {
                user.repos_contributed_to
            } else {
                user.repos
            }
            .unwrap_or_default();
            result.extend(connection.nodes.into_iter().flatten());
            if !advance(connection.page_info, &mut cursor, &mut seen)? {
                break;
            }
        }
        Ok(result)
    }
    fn repo(&self, full_name: &str) -> Result<Repo> {
        crate::config::validate_repo_name(full_name)?;
        let (owner, name): (&str, &str) = full_name
            .split_once('/')
            .context("repository must contain owner/name")?;
        let query: String = format!(
            "query($owner:String!,$name:String!){{rateLimit{{cost}} repository(owner:$owner,name:$name){{{FIELDS}}}}}"
        );
        let data: RepoData = self.query(
            &query,
            Variables {
                owner: Some(owner),
                name: Some(name),
                ..Variables::default()
            },
        )?;
        data.repo
            .with_context(|| format!("repository {full_name} is missing or inaccessible"))
    }
    fn contributors(&self, repo: &Repo) -> Result<Vec<Contributor>> {
        match self.hist(repo) {
            Ok(vals) if !vals.is_empty() => Ok(vals),
            _ => self.rest_contributors(repo),
        }
    }
    fn profiles(&self, repo: &Repo, contributors: &[Contributor]) -> Result<Vec<Contributor>> {
        let mut commits: Vec<&str> = Vec::new();
        for contributor in contributors {
            if contributors::noreply_profile(&contributor.identity).is_some() {
                continue;
            }
            for sha in &contributor.profile_commits {
                if sha.len() == 40
                    && sha.bytes().all(|byte| byte.is_ascii_hexdigit())
                    && !commits.contains(&sha.as_str())
                    && commits.len() < 24
                {
                    commits.push(sha);
                }
            }
        }
        if commits.is_empty() {
            return Ok(Vec::new());
        }
        let fields: String = commits
            .iter()
            .enumerate()
            .map(|(index, sha)| {
                format!("c{index}:object(oid:\"{sha}\"){{... on Commit{{{AUTHOR_FIELDS}}}}}")
            })
            .collect();
        let query: String = format!(
            "query($owner:String!,$name:String!){{rateLimit{{cost}} repository(owner:$owner,name:$name){{{fields}}}}}"
        );
        let data: ProfileData = self.query(
            &query,
            Variables {
                owner: Some(&repo.owner.login),
                name: Some(&repo.name),
                ..Variables::default()
            },
        )?;
        let vals: Vec<Contributor> = data
            .repo
            .unwrap_or_default()
            .into_values()
            .flatten()
            .flat_map(|commit| {
                commit
                    .authors
                    .nodes
                    .into_iter()
                    .flatten()
                    .map(move |actor| actor.contributor(&commit.committed_date))
            })
            .collect();
        let observations: Vec<Vec<usize>> = (0..vals.len()).map(|index| vec![index]).collect();
        Ok(contributors::aggregate_obs(vals, &observations))
    }
    fn cost(&self) -> u64 {
        self.cost.load(Ordering::Relaxed)
    }
}
