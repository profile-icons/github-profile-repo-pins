use super::{Ancestry, Commit, LineKey, Mask, provenance, sequence, structure};
use regex::Regex;
use std::{
    collections::{BTreeMap, BTreeSet, VecDeque},
    sync::LazyLock,
};

static CODE_TOKENS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][A-Za-z0-9_$]*|\d+(?:\.\d+)?|\S"#).expect("valid token pattern")
});
pub(crate) fn canonical(line: &str) -> String {
    CODE_TOKENS
        .find_iter(line.trim())
        .map(|token| token.as_str())
        .collect::<Vec<&str>>()
        .join("\u{1f}")
}
fn substantial(line: &str) -> bool {
    line.len() >= 8 && line.chars().any(char::is_alphanumeric)
}
fn increment(mask: &mut Mask, key: &LineKey) {
    *mask.entry(key.clone()).or_default() += 1;
}
fn consume(mask: &mut Mask, key: &LineKey) -> bool {
    if let Some(count) = mask.get_mut(key).filter(|count| **count > 0) {
        *count -= 1;
        true
    } else {
        false
    }
}
fn rename_fragment(old: &str, new: &str) -> Option<(String, String)> {
    let old: Vec<char> = old.rsplit('/').next().unwrap_or(old).chars().collect();
    let new: Vec<char> = new.rsplit('/').next().unwrap_or(new).chars().collect();
    let prefix: usize = old
        .iter()
        .zip(&new)
        .take_while(|(left, right)| left == right)
        .count();
    let suffix: usize = old[prefix..]
        .iter()
        .rev()
        .zip(new[prefix..].iter().rev())
        .take_while(|(left, right)| left == right)
        .count();
    let left: String = old[prefix..old.len() - suffix].iter().collect();
    let right: String = new[prefix..new.len() - suffix].iter().collect();
    (left.chars().count() >= 3 && right.chars().count() >= 3 && left != right)
        .then_some((left, right))
}
fn immediate(commit: &Commit) -> (Mask, Mask) {
    let mut inferred: BTreeMap<(String, String), usize> = BTreeMap::new();
    for (old, new) in &commit.renames {
        if let Some(pair) = rename_fragment(old, new) {
            *inferred.entry(pair).or_default() += 1;
        }
    }
    let mut replacements: BTreeSet<(String, String)> = BTreeSet::new();
    for ((old, new), count) in inferred {
        if count >= 3 {
            replacements.extend([
                (old.to_lowercase(), new.to_lowercase()),
                (old.to_uppercase(), new.to_uppercase()),
                (old, new),
            ]);
        }
    }
    let mut replacements: Vec<(String, String)> = replacements.into_iter().collect();
    replacements.sort_by_key(|(old, _)| std::cmp::Reverse(old.len()));
    let mut remaining: Mask = BTreeMap::new();
    for line in &commit.additions {
        increment(&mut remaining, &line.key);
    }
    let mut deletes: Mask = Mask::new();
    let mut adds: Mask = Mask::new();
    for key in &commit.deletions {
        let mut text: String = key.1.clone();
        for (old, new) in &replacements {
            text = text.replace(old, new);
        }
        if text == key.1 {
            continue;
        }
        let candidate: LineKey = (commit.renames.get(&key.0).unwrap_or(&key.0).clone(), text);
        if consume(&mut remaining, &candidate) {
            increment(&mut deletes, key);
            increment(&mut adds, &candidate);
        }
    }
    let mut skip: Mask = deletes.clone();
    let mut candidates: BTreeMap<String, VecDeque<LineKey>> = BTreeMap::new();
    for key in &commit.deletions {
        if consume(&mut skip, key) {
            continue;
        }
        let text: String = canonical(&key.1);
        if substantial(&text) {
            candidates.entry(text).or_default().push_back(key.clone());
        }
    }
    let mut skip: Mask = adds.clone();
    for line in &commit.additions {
        if consume(&mut skip, &line.key) {
            continue;
        }
        if let Some(key) = candidates
            .get_mut(&canonical(&line.key.1))
            .and_then(VecDeque::pop_front)
        {
            increment(&mut deletes, &key);
            increment(&mut adds, &line.key);
        }
    }
    (adds, deletes)
}
pub(crate) fn exclusions(commits: &[Commit]) -> Vec<Mask> {
    let (mut adds, mut deletes): (Vec<Mask>, Vec<Mask>) = commits.iter().map(immediate).unzip();
    let mut ancestry: Ancestry<'_> = Ancestry::new(commits);
    let mut pending: BTreeMap<LineKey, Vec<usize>> = BTreeMap::new();
    for (idx, commit) in commits.iter().enumerate() {
        let mut skip: Mask = deletes[idx].clone();
        for key in &commit.deletions {
            if !consume(&mut skip, key) {
                pending.entry(key.clone()).or_default().push(idx);
            }
        }
        let mut skip: Mask = adds[idx].clone();
        for line in &commit.additions {
            if consume(&mut skip, &line.key) {
                continue;
            }
            if let Some(candidates) = pending.get_mut(&line.key)
                && let Some(pos) = candidates
                    .iter()
                    .position(|candidate| ancestry.contains(*candidate, idx))
            {
                let src: usize = candidates.remove(pos);
                increment(&mut deletes[src], &line.key);
                increment(&mut adds[idx], &line.key);
            }
        }
    }
    hist_rewrites(commits, &mut adds, &mut deletes, &mut ancestry);
    let lexical: Vec<Mask> = provenance::exclusions(commits, &mut ancestry);
    let structural: Vec<Mask> = structure::exclusions(commits, &mut ancestry);
    for (idx, mask) in adds.iter_mut().enumerate() {
        for (key, count) in lexical[idx].iter().chain(&structural[idx]) {
            let val: &mut usize = mask.entry(key.clone()).or_default();
            *val = (*val).max(*count);
        }
    }
    adds
}

struct DeletedBlock {
    commit: usize,
    keys: Vec<LineKey>,
    lines: Vec<String>,
    consumed: Vec<Vec<usize>>,
}
fn groups(keys: impl IntoIterator<Item = LineKey>) -> Vec<Vec<LineKey>> {
    let mut res: BTreeMap<String, Vec<LineKey>> = BTreeMap::new();
    for key in keys {
        res.entry(key.0.clone()).or_default().push(key);
    }
    res.into_values().collect()
}
fn windows(lines: &[String]) -> BTreeSet<[String; 3]> {
    lines
        .windows(3)
        .filter(|window| {
            window.iter().all(|line| substantial(line))
                && window[0] != window[1]
                && window[0] != window[2]
                && window[1] != window[2]
        })
        .map(|window| [window[0].clone(), window[1].clone(), window[2].clone()])
        .collect()
}
fn hist_rewrites(
    commits: &[Commit],
    adds: &mut [Mask],
    deletes: &mut [Mask],
    ancestry: &mut Ancestry<'_>,
) {
    let mut blocks: Vec<DeletedBlock> = Vec::new();
    let mut idx: BTreeMap<[String; 3], BTreeSet<usize>> = BTreeMap::new();
    for (commit_idx, commit) in commits.iter().enumerate() {
        let mut skip: Mask = adds[commit_idx].clone();
        for keys in groups(commit.additions.iter().map(|line| line.key.clone())) {
            let eligible: Vec<LineKey> = keys
                .into_iter()
                .filter(|key| !consume(&mut skip, key))
                .collect();
            let canonical: Vec<String> = eligible.iter().map(|(_, text)| canonical(text)).collect();
            let candidates: BTreeSet<usize> = windows(&canonical)
                .iter()
                .flat_map(|key| idx.get(key).into_iter().flatten().copied())
                .collect();
            let mut used: BTreeSet<usize> = BTreeSet::new();
            for block_id in candidates.into_iter().rev() {
                let src: &mut DeletedBlock = &mut blocks[block_id];
                if !ancestry.contains(src.commit, commit_idx) {
                    continue;
                }
                let src_lines: Vec<String> = src
                    .lines
                    .iter()
                    .enumerate()
                    .map(|(pos, text)| {
                        if src.consumed[pos]
                            .iter()
                            .any(|user| ancestry.contains(*user, commit_idx))
                        {
                            format!("\0source:{pos}")
                        } else {
                            text.clone()
                        }
                    })
                    .collect();
                let target_lines: Vec<String> = canonical
                    .iter()
                    .enumerate()
                    .map(|(pos, text)| {
                        if used.contains(&pos) {
                            format!("\0target:{pos}")
                        } else {
                            text.clone()
                        }
                    })
                    .collect();
                for (old, new, len) in sequence::matching_blocks(&src_lines, &target_lines) {
                    if windows(&target_lines[new..new + len]).is_empty() {
                        continue;
                    }
                    for offset in 0..len {
                        if src.consumed[old + offset].is_empty() {
                            increment(&mut deletes[src.commit], &src.keys[old + offset]);
                        }
                        src.consumed[old + offset].push(commit_idx);
                        increment(&mut adds[commit_idx], &eligible[new + offset]);
                        used.insert(new + offset);
                    }
                }
            }
        }
        let mut skip: Mask = deletes[commit_idx].clone();
        for keys in groups(commit.deletions.clone()) {
            let keys: Vec<LineKey> = keys
                .into_iter()
                .filter(|key| !consume(&mut skip, key))
                .collect();
            let lines: Vec<String> = keys.iter().map(|(_, text)| canonical(text)).collect();
            let block_id: usize = blocks.len();
            for window in windows(&lines) {
                idx.entry(window).or_default().insert(block_id);
            }
            blocks.push(DeletedBlock {
                commit: commit_idx,
                consumed: vec![Vec::new(); keys.len()],
                keys,
                lines,
            });
        }
    }
}
