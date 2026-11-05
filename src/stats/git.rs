use super::{AddedLine, Commit, Policy, sequence};
use crate::{Result, model::Identity};
use anyhow::{Context, ensure};
use base64::{Engine, engine::general_purpose::STANDARD};
use regex::Regex;
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    io::{Read, Seek, SeekFrom, Write},
    path::Path,
    process::{Command, Stdio},
    sync::Arc,
    time::Duration,
};
use tempfile::{NamedTempFile, TempDir};
use wait_timeout::ChildExt;

const HIST_ARGS: &[&str] = &[
    "log",
    "HEAD",
    "--reverse",
    "--topo-order",
    "--full-history",
    "--no-diff-merges",
    "--no-ext-diff",
    "--no-textconv",
];
const RAW_DIFF_PATTERN: &str = r"^:[0-7]{6} [0-7]{6} ([0-9a-f]+) ([0-9a-f]+) ([A-Z])[0-9]*\t(.+)$";
const PREFETCH_BATCH: usize = 200;

pub struct HistReader {
    timeout: Duration,
    policy: Policy,
}
#[derive(Clone)]
struct BlobDiff {
    commit: usize,
    old_blob: String,
    new_blob: String,
    old_path: String,
    new_path: String,
}
#[derive(Deserialize)]
struct Notebook {
    cells: Vec<Cell>,
}
#[derive(Deserialize)]
struct Cell {
    cell_type: String,
    #[serde(default)]
    source: Option<CellSource>,
}
#[derive(Deserialize)]
#[serde(untagged)]
enum CellSource {
    Text(String),
    Chunks(Vec<String>),
}

impl HistReader {
    pub fn new(timeout: Duration, policy: Policy) -> Self {
        Self { timeout, policy }
    }
    pub fn remote(&self, full_name: &str, token: &str) -> Result<Vec<Commit>> {
        crate::config::validate_repo_name(full_name)?;
        let temp: TempDir = tempfile::Builder::new()
            .prefix("repo-pins-history-")
            .tempdir()?;
        let url: String = format!("https://github.com/{full_name}.git");
        let auth: String = format!(
            "AUTHORIZATION: basic {}",
            STANDARD.encode(format!("x-access-token:{token}"))
        );
        let mut command: Command = self.command();
        command
            .args([
                "clone",
                "--no-tags",
                "--single-branch",
                "--no-checkout",
                "--filter=blob:none",
                &url,
            ])
            .arg(temp.path());
        command
            .env("GIT_CONFIG_COUNT", "1")
            .env("GIT_CONFIG_KEY_0", "http.extraHeader")
            .env("GIT_CONFIG_VALUE_0", &auth);
        run(command, None, self.timeout).map_err(|_| {
            anyhow::anyhow!("could not clone {full_name}; check token access and Git connectivity")
        })?;
        self.read_with_auth(temp.path(), Some(&auth))
    }
    pub fn local(&self, dir: &Path) -> Result<Vec<Commit>> {
        self.read_with_auth(dir, None)
    }
    fn command(&self) -> Command {
        let mut command: Command = Command::new("git");
        command
            .env("GIT_TERMINAL_PROMPT", "0")
            .env("GIT_OPTIONAL_LOCKS", "0")
            .env("GIT_LFS_SKIP_SMUDGE", "1")
            .env("GIT_PAGER", "cat")
            .env("GIT_HTTP_LOW_SPEED_LIMIT", "1024")
            .env("GIT_HTTP_LOW_SPEED_TIME", "60");
        command.args([
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.quotePath=false",
        ]);
        command
    }
    fn git(
        &self,
        dir: &Path,
        args: &[&str],
        input: Option<&[u8]>,
        auth: Option<&str>,
    ) -> Result<Vec<u8>> {
        let mut command: Command = self.command();
        command.arg("-C").arg(dir).args(args);
        if let Some(auth) = auth {
            command
                .env("GIT_CONFIG_COUNT", "1")
                .env("GIT_CONFIG_KEY_0", "http.extraHeader")
                .env("GIT_CONFIG_VALUE_0", auth);
        }
        run(command, input, self.timeout)
    }
    fn stream(
        &self,
        dir: &Path,
        options: &[&str],
        paths: &[String],
        auth: Option<&str>,
    ) -> Result<Vec<u8>> {
        let mut args: Vec<&str> = HIST_ARGS.to_vec();
        args.extend_from_slice(options);
        args.push("--");
        args.extend(paths.iter().map(String::as_str));
        self.git(dir, &args, None, auth)
    }
    fn read_with_auth(&self, dir: &Path, auth: Option<&str>) -> Result<Vec<Commit>> {
        let metadata: Vec<u8> = self.git(
            dir,
            &[
                "log",
                "HEAD",
                "--use-mailmap",
                "--reverse",
                "--topo-order",
                "--no-patch",
                "--format=%H%x00%T%x00%P%x00%aN%x00%aE%x00%an%x00%ae%x00%B%x00",
            ],
            None,
            auth,
        )?;
        let fields: Vec<&[u8]> = metadata.split(|byte| *byte == 0).collect();
        let mut commits: Vec<Commit> = Vec::new();
        let coauthor: Regex = Regex::new(r"(?im)^\s*Co-authored-by:\s*(.+?)\s*<([^>]+)>\s*$")?;
        for record in fields.chunks(8).filter(|record| record.len() == 8) {
            let val =
                |idx: usize| -> String { String::from_utf8_lossy(record[idx]).trim().to_owned() };
            let mut author: Identity = Identity::default();
            author.names.extend(
                [val(3).to_lowercase(), val(5).to_lowercase()]
                    .into_iter()
                    .filter(|val| !val.is_empty()),
            );
            author.emails.extend(
                [val(4).to_lowercase(), val(6).to_lowercase()]
                    .into_iter()
                    .filter(|val| !val.is_empty()),
            );
            let mut authors: Vec<Identity> = vec![author];
            for capture in coauthor.captures_iter(&val(7)) {
                authors.push(Identity {
                    names: BTreeSet::from([capture[1].trim().to_lowercase()]),
                    emails: BTreeSet::from([capture[2].trim().to_lowercase()]),
                    ..Identity::default()
                });
            }
            commits.push(Commit {
                hash: val(0),
                tree: val(1),
                parents: val(2).split_whitespace().map(str::to_owned).collect(),
                authors,
                ..Commit::default()
            });
        }
        if commits.is_empty() {
            return Ok(commits);
        }
        let paths: Vec<String> = self.policy.path_specs();
        if auth.is_some() {
            let raw: Vec<u8> = self.stream(
                dir,
                &["--raw", "--no-renames", "--abbrev=40", "--format="],
                &paths,
                auth,
            )?;
            let pattern: Regex = Regex::new(RAW_DIFF_PATTERN)?;
            let raw: String = String::from_utf8_lossy(&raw).into_owned();
            let ids: BTreeSet<String> = raw
                .lines()
                .filter_map(|line| pattern.captures(line))
                .flat_map(|capture| [capture[1].to_owned(), capture[2].to_owned()])
                .filter(|id| id.bytes().any(|byte| byte != b'0'))
                .collect();
            let ids: Vec<String> = ids.into_iter().collect();
            for batch in ids.chunks(PREFETCH_BATCH) {
                let mut args: Vec<&str> = vec![
                    "-c",
                    "fetch.negotiationAlgorithm=noop",
                    "fetch",
                    "origin",
                    "--no-tags",
                    "--no-write-fetch-head",
                    "--recurse-submodules=no",
                    "--filter=blob:none",
                ];
                args.extend(batch.iter().map(String::as_str));
                self.git(dir, &args, None, auth)?;
            }
        }
        let mut text_paths: Vec<String> = paths;
        text_paths.push(":(exclude,icase,glob)**/*.ipynb".to_owned());
        let patch: Vec<u8> = self.stream(
            dir,
            &[
                "--raw",
                "--patch",
                "--unified=0",
                "--find-renames=20%",
                "--abbrev=40",
                "--format=@@COMMIT@@ %H",
            ],
            &text_paths,
            auth,
        )?;
        let mut diffs: Vec<BlobDiff> =
            parse_patches(&String::from_utf8_lossy(&patch), &mut commits, &self.policy)?;
        let notebooks: Vec<u8> = self.stream(
            dir,
            &[
                "--raw",
                "--no-renames",
                "--abbrev=40",
                "--format=@@COMMIT@@ %H",
            ],
            &[":(icase,glob)**/*.ipynb".to_owned()],
            auth,
        )?;
        diffs.extend(parse_patches(
            &String::from_utf8_lossy(&notebooks),
            &mut commits,
            &self.policy,
        )?);
        let ids: BTreeSet<&str> = diffs
            .iter()
            .flat_map(|diff| [diff.old_blob.as_str(), diff.new_blob.as_str()])
            .filter(|id| id.bytes().any(|byte| byte != b'0'))
            .collect();
        let input: String = ids.iter().map(|id| format!("{id}\n")).collect();
        let data: Vec<u8> =
            self.git(dir, &["cat-file", "--batch"], Some(input.as_bytes()), auth)?;
        let blobs: BTreeMap<String, Arc<str>> = parse_blobs(&data)?;
        for diff in diffs {
            let commit: &mut Commit = &mut commits[diff.commit];
            let old: &str = blobs.get(&diff.old_blob).map_or("", Arc::as_ref);
            let new: &str = blobs.get(&diff.new_blob).map_or("", Arc::as_ref);
            if diff.new_path.to_lowercase().ends_with(".py")
                && self.policy.eligible(&diff.new_path)
                && let Some(src) = blobs.get(&diff.new_blob)
            {
                commit
                    .snapshots
                    .insert(diff.new_path.clone(), Arc::clone(src));
            }
            if diff.new_path.to_lowercase().ends_with(".ipynb")
                || diff.old_path.to_lowercase().ends_with(".ipynb")
            {
                notebook_changes(commit, &diff, old, new, &self.policy);
            }
        }
        Ok(commits)
    }
}

fn run(mut command: Command, input: Option<&[u8]>, timeout: Duration) -> Result<Vec<u8>> {
    let mut stdout: NamedTempFile = NamedTempFile::new()?;
    let mut stderr: NamedTempFile = NamedTempFile::new()?;
    let mut stdin: NamedTempFile = NamedTempFile::new()?;
    if let Some(input) = input {
        stdin.write_all(input)?;
        stdin.seek(SeekFrom::Start(0))?;
    }
    command
        .stdout(Stdio::from(stdout.reopen()?))
        .stderr(Stdio::from(stderr.reopen()?))
        .stdin(Stdio::from(stdin.reopen()?));
    let mut child: std::process::Child = command
        .spawn()
        .context("could not start Git; install Git and check executable permissions")?;
    let status: std::process::ExitStatus = match child.wait_timeout(timeout)? {
        Some(status) => status,
        None => {
            let _ = child.kill();
            let _ = child.wait();
            anyhow::bail!("Git timed out after {} seconds", timeout.as_secs());
        }
    };
    let mut err: String = String::new();
    stderr.read_to_string(&mut err)?;
    ensure!(status.success(), "Git failed: {}", err.trim());
    let mut res: Vec<u8> = Vec::new();
    stdout.read_to_end(&mut res)?;
    Ok(res)
}
fn parse_blobs(data: &[u8]) -> Result<BTreeMap<String, Arc<str>>> {
    let mut blobs: BTreeMap<String, Arc<str>> = BTreeMap::new();
    let mut offset: usize = 0;
    while offset < data.len() {
        let end: usize = data[offset..]
            .iter()
            .position(|byte| *byte == b'\n')
            .map(|idx| offset + idx)
            .context("incomplete Git blob header")?;
        let header: String = String::from_utf8_lossy(&data[offset..end]).into_owned();
        let fields: Vec<&str> = header.split_whitespace().collect();
        ensure!(
            fields.len() == 3 && fields[1] == "blob",
            "missing Git source blob"
        );
        let size: usize = fields[2].parse()?;
        offset = end + 1;
        let end: usize = offset
            .checked_add(size)
            .filter(|end| *end < data.len())
            .context("incomplete Git blob")?;
        blobs.insert(
            fields[0].to_owned(),
            Arc::from(String::from_utf8_lossy(&data[offset..end]).as_ref()),
        );
        offset = end + 1;
    }
    Ok(blobs)
}
fn parse_patches(output: &str, commits: &mut [Commit], policy: &Policy) -> Result<Vec<BlobDiff>> {
    let indices: BTreeMap<String, usize> = commits
        .iter()
        .enumerate()
        .map(|(idx, commit)| (commit.hash.clone(), idx))
        .collect();
    let raw: Regex = Regex::new(RAW_DIFF_PATTERN)?;
    let hunk: Regex = Regex::new(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")?;
    let mut cur: Option<usize> = None;
    let mut path: String = String::new();
    let mut old_path: String = String::new();
    let mut row: Option<usize> = None;
    let mut diffs: Vec<BlobDiff> = Vec::new();
    for line in output.lines() {
        if let Some(hash) = line.strip_prefix("@@COMMIT@@ ") {
            cur = indices.get(hash).copied();
            row = None;
            continue;
        }
        let Some(idx) = cur else {
            continue;
        };
        let commit: &mut Commit = &mut commits[idx];
        if let Some(capture) = raw.captures(line) {
            let paths: Vec<String> = capture[4]
                .split('\t')
                .map(decode_path)
                .collect::<Result<Vec<String>>>()?;
            let old_path: String = if &capture[3] == "A" {
                String::new()
            } else {
                paths[0].clone()
            };
            let new_path: String = if &capture[3] == "D" {
                String::new()
            } else {
                paths.last().cloned().unwrap_or_default()
            };
            if &capture[3] == "R" {
                commit.renames.insert(old_path.clone(), new_path.clone());
            }
            if [old_path.as_str(), new_path.as_str()].iter().any(|path| {
                policy.eligible(path)
                    && (path.to_lowercase().ends_with(".py")
                        || path.to_lowercase().ends_with(".ipynb"))
            }) {
                diffs.push(BlobDiff {
                    commit: idx,
                    old_blob: capture[1].to_owned(),
                    new_blob: capture[2].to_owned(),
                    old_path,
                    new_path,
                });
            }
            continue;
        }
        if line.starts_with("diff --git ") {
            row = None;
            path.clear();
            old_path.clear();
            continue;
        }
        if row.is_none() && line.starts_with("--- ") {
            let decoded: String = decode_path(&line[4..])?;
            old_path = decoded.strip_prefix("a/").unwrap_or(&decoded).to_owned();
            continue;
        }
        if row.is_none() && line.starts_with("+++ ") {
            let decoded: String = decode_path(&line[4..])?;
            path = decoded.strip_prefix("b/").unwrap_or(&decoded).to_owned();
            continue;
        }
        if let Some(capture) = hunk.captures(line) {
            row = Some(capture[2].parse()?);
            continue;
        }
        let Some(new_row) = row else {
            continue;
        };
        if let Some(text) = line.strip_prefix('+') {
            if policy.eligible(&path) && !path.to_lowercase().ends_with(".ipynb") {
                commit.additions.push(AddedLine {
                    key: (path.clone(), text.to_owned()),
                    row: Some(new_row),
                });
            }
            row = Some(new_row + 1);
        } else if let Some(text) = line.strip_prefix('-') {
            if old_path != "/dev/null"
                && policy.eligible(&old_path)
                && !old_path.to_lowercase().ends_with(".ipynb")
            {
                commit.deletions.push((old_path.clone(), text.to_owned()));
            }
        } else if line.starts_with(' ') {
            row = Some(new_row + 1);
        }
    }
    Ok(diffs)
}
fn decode_path(path: &str) -> Result<String> {
    let path: &str = path.trim_end_matches('\t');
    if !path.starts_with('"') {
        return Ok(path.trim_end_matches('\t').to_owned());
    }
    let mut res: Vec<u8> = Vec::new();
    let mut bytes: std::iter::Peekable<std::slice::Iter<'_, u8>> = path.as_bytes()
        [1..path.len().saturating_sub(1)]
        .iter()
        .peekable();
    while let Some(byte) = bytes.next().copied() {
        if byte != b'\\' {
            res.push(byte);
            continue;
        }
        let escaped: u8 = bytes.next().copied().context("invalid Git path escape")?;
        if (b'0'..=b'7').contains(&escaped) {
            let mut val: u16 = u16::from(escaped - b'0');
            for _ in 0..2 {
                if bytes
                    .peek()
                    .is_some_and(|byte| (b'0'..=b'7').contains(*byte))
                {
                    val = val * 8 + u16::from(*bytes.next().context("missing octal byte")? - b'0');
                }
            }
            res.push(u8::try_from(val)?);
        } else {
            res.push(match escaped {
                b'n' => b'\n',
                b't' => b'\t',
                b'r' => b'\r',
                b'b' => 8,
                b'f' => 12,
                b'v' => 11,
                b'a' => 7,
                other => other,
            });
        }
    }
    Ok(String::from_utf8(res)?)
}
fn notebook_lines(raw: &str) -> Vec<String> {
    let Ok(notebook) = serde_json::from_str::<Notebook>(raw) else {
        return Vec::new();
    };
    notebook
        .cells
        .into_iter()
        .flat_map(|cell| {
            let chunks: Vec<String> = match cell.source {
                Some(CellSource::Text(text)) => vec![text],
                Some(CellSource::Chunks(chunks)) => chunks,
                None => Vec::new(),
            };
            chunks.into_iter().flat_map(move |chunk| {
                chunk
                    .lines()
                    .map(|line| format!("[{}] {line}", cell.cell_type))
                    .collect::<Vec<String>>()
            })
        })
        .collect()
}
fn notebook_changes(commit: &mut Commit, diff: &BlobDiff, old: &str, new: &str, policy: &Policy) {
    let old_lines: Vec<String> = notebook_lines(old);
    let new_lines: Vec<String> = notebook_lines(new);
    let mut old_cursor: usize = 0;
    let mut new_cursor: usize = 0;
    for (old_start, new_start, len) in sequence::matching_blocks(&old_lines, &new_lines) {
        if policy.eligible(&diff.old_path) {
            commit.deletions.extend(
                old_lines[old_cursor..old_start]
                    .iter()
                    .map(|line| (diff.old_path.clone(), line.clone())),
            );
        }
        if policy.eligible(&diff.new_path) {
            commit
                .additions
                .extend(
                    new_lines[new_cursor..new_start]
                        .iter()
                        .enumerate()
                        .map(|(idx, line)| AddedLine {
                            key: (diff.new_path.clone(), line.clone()),
                            row: Some(new_cursor + idx + 1),
                        }),
                );
        }
        old_cursor = old_start + len;
        new_cursor = new_start + len;
    }
    if policy.eligible(&diff.new_path) && !diff.new_path.is_empty() {
        let src: String = new_lines
            .iter()
            .map(|line| line.strip_prefix("[code] ").unwrap_or(""))
            .collect::<Vec<&str>>()
            .join("\n");
        commit
            .snapshots
            .insert(diff.new_path.clone(), Arc::from(src));
    }
}
