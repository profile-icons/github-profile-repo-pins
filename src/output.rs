use crate::{Result, model::User};
use anyhow::{Context, ensure};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
};

pub const START_MARKER: &str = "<!-- START: REPO-PINS -->";
pub const END_MARKER: &str = "<!-- END: REPO-PINS -->";
pub const IMGS_DIR: &str = "repo_pin_imgs";
pub struct PinOutput {
    pub name: String,
    pub url: String,
    pub svg: String,
}

pub fn update_markers(readme: &str, grid: &str) -> Result<Option<String>> {
    let mut res: String = String::new();
    let mut remaining: &str = readme;
    let mut found: bool = false;
    while let Some(start) = remaining.find(START_MARKER) {
        let body: usize = start + START_MARKER.len();
        let end: usize = remaining[body..]
            .find(END_MARKER)
            .map(|end| body + end)
            .context("README has a start marker without an end marker")?;
        ensure!(
            !remaining[body..end].contains(START_MARKER),
            "README contains nested repo-pin markers"
        );
        res.push_str(&remaining[..body]);
        res.push_str(grid);
        res.push('\n');
        res.push_str(END_MARKER);
        remaining = &remaining[end + END_MARKER.len()..];
        found = true;
    }
    res.push_str(remaining);
    Ok(found.then_some(res))
}
pub fn markdown_grid(pins: &[PinOutput], target_repo: &str) -> String {
    let mut grid: String = String::new();
    for (idx, pin) in pins.iter().enumerate() {
        if idx % 2 == 0 {
            grid.push('\n');
        }
        let name: String = pin
            .name
            .replace('\\', "\\\\")
            .replace('[', "\\[")
            .replace(']', "\\]");
        let image: String = format!(
            "https://raw.githubusercontent.com/{target_repo}/refs/heads/generated/{IMGS_DIR}/{idx}.svg"
        );
        grid.push_str(&format!(
            "[![{name} pin img]({image})](<{}>) ",
            pin.url
                .replace('>', "%3E")
                .replace('<', "%3C")
                .replace(['\r', '\n'], "")
        ));
    }
    grid
}
pub fn save(dir: &Path, is_org: bool, target_repo: &str, pins: &[PinOutput]) -> Result<()> {
    crate::config::validate_repo_name(target_repo)?;
    fs::create_dir_all(dir)?;
    let readme_path: PathBuf = dir.join(if is_org {
        "profile/README.md"
    } else {
        "README.md"
    });
    let grid: String = markdown_grid(pins, target_repo);
    let updated: Option<String> = if readme_path.is_file() {
        ensure!(!readme_path.is_symlink(), "README must be a regular file");
        update_markers(&fs::read_to_string(&readme_path)?, &grid)?
    } else {
        None
    };
    if updated.is_none() {
        eprintln!(
            "No repo-pin marker pair found in {}; images will still be written",
            readme_path.display()
        );
    }
    let img_dir: PathBuf = dir.join(IMGS_DIR);
    ensure!(
        !img_dir.is_symlink(),
        "repo_pin_imgs must not be a symbolic link"
    );
    fs::create_dir_all(&img_dir)?;
    let staging: tempfile::TempDir = tempfile::Builder::new()
        .prefix(".repo-pins-stage-")
        .tempdir_in(dir)?;
    for (idx, pin) in pins.iter().enumerate() {
        fs::write(staging.path().join(format!("{idx}.svg")), &pin.svg)?;
    }
    for (idx, _) in pins.iter().enumerate() {
        atomic_write(
            &img_dir.join(format!("{idx}.svg")),
            &fs::read(staging.path().join(format!("{idx}.svg")))?,
        )?;
    }
    if let Some(updated) = updated {
        atomic_write(&readme_path, updated.as_bytes())?;
    }
    for entry in fs::read_dir(&img_dir)? {
        let entry: fs::DirEntry = entry?;
        let path: PathBuf = entry.path();
        let idx: Option<usize> = path
            .file_stem()
            .and_then(|name| name.to_str())
            .and_then(|name| name.parse().ok());
        if path.extension() == Some(std::ffi::OsStr::new("svg"))
            && idx.is_some_and(|idx| idx >= pins.len())
            && entry.file_type()?.is_file()
        {
            fs::remove_file(path)?;
        }
    }
    Ok(())
}
fn atomic_write(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file: tempfile::NamedTempFile =
        tempfile::NamedTempFile::new_in(path.parent().context("output has no parent directory")?)?;
    if path.is_file() {
        file.as_file()
            .set_permissions(path.metadata()?.permissions())?;
    }
    file.write_all(bytes)?;
    file.flush()?;
    file.persist(path)?;
    Ok(())
}
pub fn write_git_credentials(user: &User, dest: Option<&Path>) -> Result<()> {
    let Some(dest) = dest else {
        return Ok(());
    };
    let name: String = user
        .name
        .as_deref()
        .unwrap_or(&user.login)
        .replace(['\r', '\n'], " ");
    let mut file: fs::File = OpenOptions::new().create(true).append(true).open(dest)?;
    writeln!(
        file,
        "GH_USER_NAME={name}\nGH_USER_ID={}",
        user.db_id.unwrap_or(0)
    )?;
    Ok(())
}
