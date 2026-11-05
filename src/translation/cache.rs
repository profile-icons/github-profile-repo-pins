use crate::Result;
use anyhow::{Context, ensure};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::{Read, Write},
    path::PathBuf,
    time::Duration,
};

#[derive(Clone, Copy)]
pub(super) struct ModelSpec {
    pub repo: &'static str,
    pub revision: &'static str,
    pub dir: &'static str,
}
#[derive(Clone, Copy)]
pub(super) struct AssetSpec {
    pub remote: &'static str,
    pub name: &'static str,
    pub bytes: Option<u64>,
    pub checksum: Option<[u8; 32]>,
}
impl AssetSpec {
    pub const fn new(remote: &'static str, name: &'static str) -> Self {
        Self {
            remote,
            name,
            bytes: None,
            checksum: None,
        }
    }
}
pub(super) struct ModelCache {
    root: PathBuf,
    client: reqwest::blocking::Client,
}
impl ModelCache {
    pub fn new(root: PathBuf) -> Result<Self> {
        Ok(Self {
            root,
            client: reqwest::blocking::Client::builder()
                .timeout(Duration::from_secs(600))
                .connect_timeout(Duration::from_secs(20))
                .redirect(reqwest::redirect::Policy::limited(5))
                .build()?,
        })
    }
    pub fn dir(&self, model: ModelSpec) -> PathBuf {
        self.root.join(model.dir).join(model.revision)
    }
    pub fn file(&self, model: ModelSpec, asset: AssetSpec) -> Result<PathBuf> {
        let dir: PathBuf = self.dir(model);
        let target: PathBuf = dir.join(asset.name);
        if target.is_file() {
            let len: u64 = target.metadata()?.len();
            if len > 0 && asset.bytes.is_none_or(|expected| len == expected) {
                return Ok(target);
            }
        }
        fs::create_dir_all(&dir)?;
        eprintln!(
            "Downloading {}/{} into {}",
            model.repo,
            asset.remote,
            dir.display()
        );
        let url: String = format!(
            "https://huggingface.co/{}/resolve/{}/{}",
            model.repo, model.revision, asset.remote
        );
        let mut request: reqwest::blocking::RequestBuilder = self.client.get(url);
        if let Ok(token) = std::env::var("HF_TOKEN")
            && !token.is_empty()
        {
            request = request.bearer_auth(token);
        }
        let mut res: reqwest::blocking::Response = request
            .send()
            .with_context(|| format!("could not download {}", asset.remote))?
            .error_for_status()?;
        let expected: Option<u64> = asset.bytes.or(res.content_length());
        let mut file: tempfile::NamedTempFile = tempfile::NamedTempFile::new_in(&dir)?;
        let mut checksum: Sha256 = Sha256::new();
        let mut buffer: [u8; 65_536] = [0; 65_536];
        let mut written: u64 = 0;
        loop {
            let count: usize = res.read(&mut buffer)?;
            if count == 0 {
                break;
            }
            checksum.update(&buffer[..count]);
            file.write_all(&buffer[..count])?;
            written += u64::try_from(count)?;
        }
        ensure!(
            written > 0 && expected.is_none_or(|size| size == written),
            "incomplete model download: {}",
            asset.remote
        );
        let actual: [u8; 32] = checksum.finalize().into();
        ensure!(
            asset.checksum.is_none_or(|expected| expected == actual),
            "model checksum mismatch: {}",
            asset.remote
        );
        file.flush()?;
        file.persist(&target)?;
        Ok(target)
    }
}
