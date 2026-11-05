use crate::{
    hash::sha256_hex,
    model::{Contributor, Identity, Repo, User},
};
use base64::{Engine, engine::general_purpose::STANDARD};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use unicode_casefold::UnicodeCaseFold;

pub fn norm(val: &str) -> String {
    val.trim().case_fold().collect()
}

impl Identity {
    pub fn normd(&self) -> Self {
        let login: String = norm(&self.login);
        let mut names: BTreeSet<String> = self
            .names
            .iter()
            .map(|name| norm(name))
            .filter(|name| !name.is_empty())
            .collect();
        let mut emails: BTreeSet<String> = self
            .emails
            .iter()
            .map(|email| norm(email))
            .filter(|email| !email.is_empty())
            .collect();
        if !login.is_empty() {
            names.insert(login.clone());
            emails.insert(format!("{login}@users.noreply.github.com"));
            if let Some(id) = self.user_id {
                emails.insert(format!("{id}+{login}@users.noreply.github.com"));
            }
        }
        let mut res: Self = Self {
            names,
            emails,
            login,
            user_id: self.user_id,
        };
        if let Some((login, id, _)) = noreply_profile(&res) {
            res.names.insert(login);
            if res.user_id.is_none() {
                res.user_id = id;
            }
        }
        res
    }
}

struct DisjointSets {
    parents: Vec<usize>,
    profiles: Vec<BTreeSet<String>>,
}
impl DisjointSets {
    fn new(identities: &[Identity]) -> Self {
        Self {
            parents: (0..identities.len()).collect(),
            profiles: identities
                .iter()
                .map(|identity| {
                    identity
                        .user_id
                        .map(|id| format!("id:{id}"))
                        .or_else(|| {
                            (!identity.login.is_empty())
                                .then(|| format!("login:{}", identity.login))
                        })
                        .into_iter()
                        .collect()
                })
                .collect(),
        }
    }
    fn root(&mut self, mut idx: usize) -> usize {
        while self.parents[idx] != idx {
            self.parents[idx] = self.parents[self.parents[idx]];
            idx = self.parents[idx];
        }
        idx
    }
    fn join(&mut self, left: usize, right: usize, allow_profiles: bool) {
        let left: usize = self.root(left);
        let right: usize = self.root(right);
        if left == right {
            return;
        }
        if !allow_profiles
            && !self.profiles[left].is_empty()
            && !self.profiles[right].is_empty()
            && self.profiles[left] != self.profiles[right]
        {
            return;
        }
        self.parents[right] = left;
        let profiles: BTreeSet<String> = self.profiles[right].clone();
        self.profiles[left].extend(profiles);
    }
}

pub fn resolve(identities: &[Identity], allow_email_profile_merge: bool) -> Vec<usize> {
    let identities: Vec<Identity> = identities.iter().map(Identity::normd).collect();
    let mut sets: DisjointSets = DisjointSets::new(&identities);
    let mut profiles: HashMap<String, usize> = HashMap::new();
    let mut emails: HashMap<&str, usize> = HashMap::new();
    let mut names: BTreeMap<&str, Vec<usize>> = BTreeMap::new();
    for (idx, identity) in identities.iter().enumerate() {
        if let Some(profile) = sets.profiles[idx].first().cloned()
            && let Some(prev) = profiles.insert(profile, idx)
        {
            sets.join(prev, idx, false);
        }
        for email in &identity.emails {
            if let Some(prev) = emails.insert(email, idx) {
                sets.join(prev, idx, allow_email_profile_merge);
            }
        }
        for name in &identity.names {
            names.entry(name).or_default().push(idx);
        }
    }
    for indices in names.values() {
        let roots: BTreeSet<usize> = indices.iter().map(|idx| sets.root(*idx)).collect();
        if roots
            .iter()
            .filter(|root| !sets.profiles[**root].is_empty())
            .count()
            > 1
        {
            continue;
        }
        for idx in &indices[1..] {
            sets.join(indices[0], *idx, false);
        }
    }
    loop {
        let mut root_names: BTreeMap<usize, BTreeSet<&str>> = BTreeMap::new();
        for (idx, identity) in identities.iter().enumerate() {
            root_names
                .entry(sets.root(idx))
                .or_default()
                .extend(identity.names.iter().map(String::as_str));
        }
        let mut choices: BTreeMap<usize, usize> = BTreeMap::new();
        for (root, names) in &root_names {
            let mut best: f64 = 0.0;
            let mut matches: Vec<usize> = Vec::new();
            for (other, aliases) in &root_names {
                if root == other {
                    continue;
                }
                let score: f64 = names
                    .iter()
                    .flat_map(|name| aliases.iter().map(move |alias| alias_score(name, alias)))
                    .fold(0.0, f64::max);
                if score > best {
                    best = score;
                    matches = vec![*other];
                } else if score > 0.0 && score == best {
                    matches.push(*other);
                }
            }
            if best > 0.0 && matches.len() == 1 {
                choices.insert(*root, matches[0]);
            }
        }
        let mut changed: bool = false;
        for (left, right) in &choices {
            if choices.get(right) != Some(left) || sets.root(*left) == sets.root(*right) {
                continue;
            }
            sets.join(*left, *right, false);
            changed |= sets.root(*left) == sets.root(*right);
        }
        if !changed {
            break;
        }
    }
    (0..identities.len()).map(|idx| sets.root(idx)).collect()
}
fn alias_score(left: &str, right: &str) -> f64 {
    let left: BTreeSet<&str> = left
        .split(|character: char| !character.is_alphanumeric())
        .filter(|part| !part.is_empty())
        .collect();
    let right: BTreeSet<&str> = right
        .split(|character: char| !character.is_alphanumeric())
        .filter(|part| !part.is_empty())
        .collect();
    let (shorter, longer): (&BTreeSet<&str>, &BTreeSet<&str>) = if left.len() < right.len() {
        (&left, &right)
    } else {
        (&right, &left)
    };
    if shorter.is_empty()
        || shorter == longer
        || !shorter.is_subset(longer)
        || (shorter.len() == 1 && shorter.first().is_some_and(|val| val.len() < 5))
    {
        return 0.0;
    }
    shorter.len() as f64 / longer.len() as f64
}

pub fn aggregate_obs(obs: Vec<Contributor>, commits: &[Vec<usize>]) -> Vec<Contributor> {
    let identities: Vec<Identity> = obs.iter().map(|val| val.identity.clone()).collect();
    let roots: Vec<usize> = resolve(&identities, true);
    let mut groups: BTreeMap<usize, Contributor> = BTreeMap::new();
    for (idx, obs) in obs.into_iter().enumerate() {
        merge(groups.entry(roots[idx]).or_default(), obs, false);
    }
    for commit in commits {
        for root in commit
            .iter()
            .filter_map(|idx| roots.get(*idx))
            .copied()
            .collect::<BTreeSet<usize>>()
        {
            groups.entry(root).or_default().commit_count += 1;
        }
    }
    let mut res: Vec<Contributor> = groups.into_values().collect();
    res.sort_by(|left, right| {
        right
            .commit_count
            .cmp(&left.commit_count)
            .then_with(|| right.identity.login.cmp(&left.identity.login))
    });
    res
}

pub fn merge(target: &mut Contributor, src: Contributor, sum: bool) {
    let identity: Identity = src.identity.normd();
    target.identity.names.extend(identity.names);
    target.identity.emails.extend(identity.emails);
    target.additions += src.additions;
    if sum {
        target.commit_count += src.commit_count;
    }
    target.is_automated |= src.is_automated;
    target.is_user |= src.is_user;
    if (!identity.login.is_empty() || identity.user_id.is_some() || src.avatar_url.is_some())
        && (target.last_commit_at.is_empty() || src.last_commit_at >= target.last_commit_at)
    {
        if !identity.login.is_empty() {
            target.identity.login = identity.login;
        }
        target.identity.user_id = identity.user_id.or(target.identity.user_id);
        target.avatar_url = src.avatar_url.or(target.avatar_url.take());
        target.last_commit_at = src.last_commit_at;
    }
    for sha in src.profile_commits {
        if target.profile_commits.len() < 3 && !target.profile_commits.contains(&sha) {
            target.profile_commits.push(sha);
        }
    }
}

pub fn noreply_profile(identity: &Identity) -> Option<(String, Option<u64>, String)> {
    for email in &identity.emails {
        let email: String = norm(email);
        let Some(local) = email.strip_suffix("@users.noreply.github.com") else {
            continue;
        };
        let (id, login): (Option<u64>, &str) = match local.split_once('+') {
            Some((id, login)) => (id.parse().ok(), login),
            None => (None, local),
        };
        if !valid_login(login.strip_suffix("[bot]").unwrap_or(login)) {
            continue;
        }
        let avatar: String = id.map_or_else(
            || format!("https://github.com/{login}.png?size=80"),
            |id| format!("https://avatars.githubusercontent.com/u/{id}?v=4"),
        );
        return Some((login.to_owned(), id, avatar));
    }
    None
}
fn valid_login(val: &str) -> bool {
    !val.is_empty()
        && val.len() <= 39
        && val
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
        && !val.starts_with('-')
        && !val.ends_with('-')
}
fn is_user(identity: &Identity, user: &User) -> bool {
    identity.user_id.is_some() && identity.user_id == user.db_id
        || identity.login.eq_ignore_ascii_case(&user.login)
        || identity.names.contains(&norm(&user.login))
        || user
            .name
            .as_ref()
            .is_some_and(|name| !name.is_empty() && identity.names.contains(&norm(name)))
        || user.db_id.is_some_and(|id| {
            identity.emails.iter().any(|email| {
                email.starts_with(&format!("{id}+")) && email.ends_with("@users.noreply.github.com")
            })
        })
}
pub fn for_repo(repo: &Repo, user: &User, policy: &crate::stats::Policy) -> Vec<Contributor> {
    let local: Option<&Vec<Contributor>> = repo
        .local_contributors
        .as_ref()
        .filter(|vals| !vals.is_empty());
    let mut srcs: Vec<Contributor> = local.cloned().unwrap_or_default();
    let local_count: usize = srcs.len();
    srcs.extend(repo.contributors.clone());
    for src in &mut srcs {
        src.identity = src.identity.normd();
        src.is_user = is_user(&src.identity, user);
        if src.is_user {
            src.identity.login = norm(&user.login);
            src.identity.user_id = user.db_id;
        }
    }
    let roots: Vec<usize> = resolve(
        &srcs
            .iter()
            .map(|src| src.identity.clone())
            .collect::<Vec<Identity>>(),
        true,
    );
    let local_roots: BTreeSet<usize> = roots.iter().take(local_count).copied().collect();
    let mut res: BTreeMap<usize, Contributor> = BTreeMap::new();
    for (index, mut source) in srcs.into_iter().enumerate() {
        let root: usize = roots[index];
        if local.is_some() && !local_roots.contains(&root) {
            continue;
        }
        if index >= local_count && local_roots.contains(&root) {
            source.commit_count = 0;
            source.additions = 0.0;
        }
        merge(res.entry(root).or_default(), source, true);
    }
    let mut res: Vec<Contributor> = res.into_values().collect();
    for contributor in &mut res {
        contributor.is_automated |= policy.is_automated(&contributor.identity);
        if contributor.identity.login.is_empty() {
            contributor.identity.login = contributor
                .identity
                .names
                .iter()
                .max_by_key(|name| (name.len(), *name))
                .cloned()
                .unwrap_or_else(|| "unknown".to_owned());
        }
        if contributor.avatar_url.is_none() {
            if contributor.is_user && user.db_id.is_some() {
                contributor.avatar_url = user.avatar_url.clone().or_else(|| {
                    user.db_id
                        .map(|id| format!("https://avatars.githubusercontent.com/u/{id}?v=4"))
                });
            } else if let Some((login, id, avatar)) = noreply_profile(&contributor.identity) {
                contributor.identity.login = login;
                contributor.identity.user_id = id;
                contributor.avatar_url = Some(avatar);
            } else if contributor.is_automated {
                contributor.avatar_url = Some(automation_avatar(&contributor.identity.login));
            } else if local.is_some() && valid_login(&contributor.identity.login) {
                contributor.avatar_url = Some(format!(
                    "https://github.com/{}.png?size=80",
                    contributor.identity.login
                ));
            }
        }
    }
    res.sort_by(|left, right| {
        let left_score: f64 = if local.is_some() {
            left.additions
        } else {
            left.commit_count as f64
        };
        let right_score: f64 = if local.is_some() {
            right.additions
        } else {
            right.commit_count as f64
        };
        right_score
            .total_cmp(&left_score)
            .then_with(|| right.commit_count.cmp(&left.commit_count))
            .then_with(|| right.identity.login.cmp(&left.identity.login))
    });
    res
}
fn automation_avatar(login: &str) -> String {
    let digest: String = sha256_hex(&norm(login));
    let color: &str = &digest[..6];
    let svg: String = format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="40" fill="#{color}"/><path d="M40 16v10" stroke="white" stroke-width="4"/><circle cx="40" cy="14" r="4" fill="white"/><rect x="18" y="26" width="44" height="34" rx="9" fill="white"/><circle cx="30" cy="40" r="4" fill="#{color}"/><circle cx="50" cy="40" r="4" fill="#{color}"/><path d="M30 51h20" stroke="#{color}" stroke-width="4"/></svg>"##
    );
    format!("data:image/svg+xml;base64,{}", STANDARD.encode(svg))
}
