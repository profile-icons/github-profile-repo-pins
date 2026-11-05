use crate::Result;
use anyhow::{Context, ensure};
use serde::Deserialize;
use std::{collections::BTreeMap, path::Path};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Palette {
    pub canvas: String,
    pub border: String,
    pub text: String,
    pub danger: String,
    pub link: String,
    pub user_border: Option<String>,
}
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Theme {
    pub light: Palette,
    pub dark: Palette,
}
pub struct Themes {
    vals: BTreeMap<String, Theme>,
}
impl Themes {
    pub fn load(path: Option<&Path>) -> Result<Self> {
        let src: String = match path {
            Some(path) => std::fs::read_to_string(path)?,
            None => include_str!("../../files/themes.json").to_owned(),
        };
        let vals: BTreeMap<String, Theme> =
            serde_json::from_str(&src).context("invalid themes JSON")?;
        ensure!(!vals.is_empty(), "themes database is empty");
        for theme in vals.values() {
            for palette in [&theme.light, &theme.dark] {
                for color in [
                    &palette.canvas,
                    &palette.border,
                    &palette.text,
                    &palette.danger,
                    &palette.link,
                ]
                .into_iter()
                .chain(palette.user_border.iter())
                {
                    ensure!(valid_color(color), "unsupported theme color: {color}");
                }
            }
        }
        Ok(Self { vals })
    }
    pub fn get(&self, name: &str) -> Result<&Theme> {
        self.vals
            .get(&name.to_lowercase())
            .with_context(|| format!("unknown theme: {name}"))
    }
}
pub fn valid_color(val: &str) -> bool {
    (val.starts_with('#')
        && matches!(val.len(), 4 | 5 | 7 | 9)
        && val[1..].bytes().all(|byte| byte.is_ascii_hexdigit()))
        || matches!(val, "transparent" | "white" | "black")
}
impl Palette {
    fn css(&self) -> String {
        format!(
            ":root{{--canvas:{};--border:{};--text:{};--danger:{};--link:{};--user-border:{};}}",
            self.canvas,
            self.border,
            self.text,
            self.danger,
            self.link,
            self.user_border.as_ref().unwrap_or(&self.link)
        )
    }
}
impl Theme {
    pub fn css(&self) -> String {
        format!(
            "<style>svg{{background:transparent}}{}@media(prefers-color-scheme:dark){{{}}}text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif}}</style>",
            self.light.css(),
            self.dark.css()
        )
    }
}
