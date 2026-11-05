use crate::Result;
use anyhow::{Context, ensure};
use std::collections::BTreeMap;

pub(super) struct Icon {
    svg: String,
    bounds: resvg::usvg::Rect,
}
impl Icon {
    pub fn load() -> Result<BTreeMap<String, Self>> {
        let paths: BTreeMap<String, String> =
            serde_json::from_str(include_str!("../../files/icons.json"))?;
        paths.iter().map(|(name, path)| {
            let mut parts: Vec<&str> = vec![path];
            if name == "icon_issue_outer" {
                parts.push(paths.get("icon_issue_inner").context("missing issue icon center")?);
            }
            let geometry: String = parts.iter().map(|path| format!(r#"<path d="{path}"/>"#)).collect();
            let source: String = format!(r#"<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">{geometry}</svg>"#);
            let tree: resvg::usvg::Tree = resvg::usvg::Tree::from_str(&source, &resvg::usvg::Options::default())
                .with_context(|| format!("could not parse {name}"))?;
            let bounds: resvg::usvg::Rect = tree.root().bounding_box();
            ensure!(bounds.width() > 0.0 && bounds.height() > 0.0, "empty icon: {name}");
            let svg: String = parts.iter().map(|path| format!(r#"<path d="{path}" fill="var(--text)" fill-rule="evenodd"/>"#)).collect();
            Ok((name.clone(), Self { svg, bounds }))
        }).collect()
    }
    pub fn at(&self, x: f64, y: f64, size: f64) -> String {
        self.transformed(x, y, size / 17.0)
    }
    pub fn centered_at(&self, x: f64, center_y: f64, size: f64) -> String {
        let width: f64 = f64::from(self.bounds.width());
        let height: f64 = f64::from(self.bounds.height());
        let scale: f64 = size / width.max(height);
        let center_x: f64 = f64::from(self.bounds.x()) + width / 2.0;
        let center_y_offset: f64 = f64::from(self.bounds.y()) + height / 2.0;
        self.transformed(
            x + size / 2.0 - center_x * scale,
            center_y - center_y_offset * scale,
            scale,
        )
    }
    fn transformed(&self, x: f64, y: f64, scale: f64) -> String {
        format!(
            r#"<g transform="translate({x},{y}) scale({scale})">{}</g>"#,
            self.svg
        )
    }
}
