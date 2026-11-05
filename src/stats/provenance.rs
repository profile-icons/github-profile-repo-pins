use super::{Ancestry, Commit, LineKey, Mask};
use regex::Regex;
use rustpython_parser::{Parse, ast};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    sync::LazyLock,
};

const WINDOW: usize = 12;
const MIN_MATCH: usize = 24;
const MAX_POSTINGS: usize = 128;
static TOKENS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][A-Za-z0-9_$]*|\d+(?:\.\d+)?|\*\*=|>>=|<<=|===|!==|==|!=|<=|>=|:=|->|=>|\+\+|--|\*\*|//|<<|>>|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|\S"#).expect("valid provenance pattern")
});
struct Block {
    commit: usize,
    keys: Vec<LineKey>,
    tokens: Vec<String>,
    spans: Vec<(usize, usize)>,
}

fn tokenize(path: &str, text: &str) -> Vec<String> {
    let notebook: bool = path.to_lowercase().ends_with(".ipynb");
    let python: bool =
        path.to_lowercase().ends_with(".py") || notebook && text.starts_with("[code] ");
    let text: &str = if notebook {
        text.strip_prefix("[code] ").unwrap_or(text)
    } else {
        text
    };
    let text: &str = if python {
        text.trim_start()
            .strip_prefix('#')
            .unwrap_or(text.trim_start())
            .trim_start()
    } else {
        text
    };
    let mut tokens: Vec<String> = Vec::new();
    if notebook && !python {
        tokens.push("NOTEBOOK_PROSE".to_owned());
    }
    for token in TOKENS.find_iter(text).map(|token| token.as_str()) {
        if python
            && (token.starts_with('"') || token.starts_with('\''))
            && let Ok(ast::Expr::Constant(val)) = ast::Expr::parse(token, "<provenance>")
        {
            tokens.push(format!("{:?}", val.value));
            continue;
        }
        tokens.push(token.to_owned());
    }
    tokens
}
fn blocks(idx: usize, commit: &Commit) -> Vec<Block> {
    let mut paths: BTreeMap<&str, Vec<LineKey>> = BTreeMap::new();
    for line in &commit.additions {
        paths.entry(&line.key.0).or_default().push(line.key.clone());
    }
    let mut res: Vec<Block> = Vec::new();
    for (path, keys) in paths {
        let commented: bool = path.to_lowercase().ends_with(".py")
            && keys
                .iter()
                .all(|(_, line)| line.trim().is_empty() || line.trim_start().starts_with('#'));
        let mut tokens: Vec<String> = Vec::new();
        let mut spans: Vec<(usize, usize)> = Vec::new();
        let mut triple: Option<&str> = None;
        for (_, original) in &keys {
            let text: String = if commented && original.trim_start().starts_with('#') {
                let indent: usize = original.len() - original.trim_start().len();
                format!(
                    "{}{}",
                    &original[..indent],
                    original[indent + 1..]
                        .strip_prefix(' ')
                        .unwrap_or(&original[indent + 1..])
                )
            } else {
                original.clone()
            };
            let start: usize = tokens.len();
            let python: bool = path.to_lowercase().ends_with(".py")
                || path.to_lowercase().ends_with(".ipynb") && text.starts_with("[code] ");
            let mut delimiters: Vec<&str> = Vec::new();
            if python {
                let bytes: &[u8] = text.as_bytes();
                let mut pos: usize = 0;
                while pos + 2 < bytes.len() {
                    if (pos == 0 || bytes[pos - 1] != b'\\')
                        && (&bytes[pos..pos + 3] == b"\"\"\"" || &bytes[pos..pos + 3] == b"'''")
                    {
                        delimiters.push(&text[pos..pos + 3]);
                        pos += 3;
                    } else {
                        pos += 1;
                    }
                }
            }
            let literal: bool = triple.is_some() || !delimiters.is_empty();
            for delimiter in delimiters {
                if triple.is_none() {
                    triple = Some(if delimiter == "'''" { "'''" } else { "\"\"\"" });
                } else if triple == Some(delimiter) {
                    triple = None;
                }
            }
            if literal {
                tokens.push(format!("\0literal:{text}"));
            } else {
                tokens.extend(tokenize(path, &text));
            }
            spans.push((start, tokens.len()));
        }
        res.push(Block {
            commit: idx,
            keys,
            tokens,
            spans,
        });
    }
    res
}
pub(crate) fn exclusions(commits: &[Commit], ancestry: &mut Ancestry<'_>) -> Vec<Mask> {
    let mut res: Vec<Mask> = vec![Mask::new(); commits.len()];
    let mut srcs: Vec<Block> = Vec::new();
    let mut idx: HashMap<Vec<String>, Vec<(usize, usize)>> = HashMap::new();
    for (commit_idx, commit) in commits.iter().enumerate() {
        let targets: Vec<Block> = blocks(commit_idx, commit);
        for target in &targets {
            let mut anchors: BTreeMap<(usize, isize), Vec<usize>> = BTreeMap::new();
            for (pos, window) in target.tokens.windows(WINDOW).enumerate() {
                let Some(postings) = idx.get(window) else {
                    continue;
                };
                if postings.len() > MAX_POSTINGS {
                    continue;
                }
                for (block_id, src_pos) in postings {
                    if ancestry.contains(srcs[*block_id].commit, commit_idx) {
                        anchors
                            .entry((*block_id, *src_pos as isize - pos as isize))
                            .or_default()
                            .push(pos);
                    }
                }
            }
            let mut covered: BTreeSet<usize> = BTreeSet::new();
            for ((_src, _diagonal), positions) in anchors {
                let mut first: usize = positions[0];
                let mut prev: usize = first;
                let mut runs: Vec<(usize, usize)> = Vec::new();
                for pos in &positions[1..] {
                    if *pos != prev + 1 {
                        runs.push((first, prev + WINDOW));
                        first = *pos;
                    }
                    prev = *pos;
                }
                runs.push((first, prev + WINDOW));
                for (begin, end) in runs {
                    if end - begin < MIN_MATCH
                        || target.tokens[begin..end]
                            .iter()
                            .filter(|token| token.chars().any(char::is_alphanumeric))
                            .collect::<BTreeSet<&String>>()
                            .len()
                            < 6
                    {
                        continue;
                    }
                    for (row, (start, stop)) in target
                        .spans
                        .iter()
                        .enumerate()
                        .skip_while(|(_, (start, _))| *start < begin)
                        .take_while(|(_, (start, _))| *start < end)
                    {
                        if start < stop && *stop <= end && covered.insert(row) {
                            *res[commit_idx].entry(target.keys[row].clone()).or_default() += 1;
                        }
                    }
                }
            }
        }
        for target in targets {
            let block_id: usize = srcs.len();
            for (pos, window) in target.tokens.windows(WINDOW).enumerate() {
                idx.entry(window.to_vec())
                    .or_default()
                    .push((block_id, pos));
            }
            srcs.push(target);
        }
    }
    res
}
