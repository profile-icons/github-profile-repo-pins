use super::{
    icons::Icon,
    media::MediaStore,
    theme::{Theme, valid_color},
};
use crate::{
    Result,
    config::ImgOptions,
    i18n::Translator,
    model::{Contributor, Repo},
};
use anyhow::{Context, ensure};
use std::{collections::BTreeMap, fmt::Write, sync::Arc};

const SCALE: f64 = 0.937;
const WIDTH: f64 = 412.0;
const PADDING: f64 = 16.0;
const NAME_SIZE: f64 = 14.0 * SCALE;
const META_SIZE: f64 = 13.0 * SCALE;
const FOOTER_CENTER_Y: f64 = -META_SIZE * 0.35;
const DESC_SIZE: f64 = 13.0 * SCALE;
const AVATAR_SIZE: f64 = META_SIZE * 2.0;
const AVATAR_STEP: f64 = AVATAR_SIZE * 0.65;
const MAX_AVATARS: usize = 4;
const WEIGHTED_MIN_CONTRIBUTORS: usize = 3;
const SUBSCRIPT_GAP: f64 = META_SIZE * 0.15;
const SUBSCRIPT_RESERVED_GAP: f64 = META_SIZE * 0.15;
const WEIGHTED_TRAILING_SPACE: f64 = SUBSCRIPT_RESERVED_GAP + META_SIZE * 0.1;

pub struct Renderer<'a> {
    icons: BTreeMap<String, Icon>,
    media: &'a mut dyn MediaStore,
    translator: &'a mut dyn Translator,
    subscript_gap: f64,
}
struct Group {
    width: f64,
    svg: String,
}
struct MetricText {
    width: f64,
    svg: String,
    tooltip: Option<String>,
    sizing: TextSizing,
}
enum TextSizing {
    Label,
    Spans,
}
impl MetricText {
    fn plain(text: &str) -> Self {
        Self {
            width: measure(text, META_SIZE),
            svg: escape(text),
            tooltip: None,
            sizing: TextSizing::Label,
        }
    }
    fn contribution(perc: f64, weighted: Option<f64>, subscript_gap: f64) -> Self {
        let perc: String = trim_decimal(perc);
        let Some(weighted) = weighted else {
            return Self::plain(&format!("{perc}%"));
        };
        let weighted: String = trim_decimal(weighted);
        let prefix: String = format!("{perc}% ({weighted}%");
        let prefix_width: f64 = measure(&prefix, META_SIZE);
        let subscript_width: f64 = measure("w", META_SIZE * 0.7);
        let suffix_width: f64 = measure(")", META_SIZE);
        let subscript_x: f64 = PADDING + prefix_width + subscript_gap;
        let suffix_x: f64 = PADDING + prefix_width + SUBSCRIPT_RESERVED_GAP + subscript_width;
        Self {
            width: prefix_width + SUBSCRIPT_RESERVED_GAP + subscript_width + suffix_width,
            svg: format!(
                r#"<tspan textLength="{prefix_width}" lengthAdjust="spacingAndGlyphs">{prefix}</tspan><tspan x="{subscript_x}" textLength="{subscript_width}" lengthAdjust="spacingAndGlyphs" baseline-shift="sub" font-size="70%">w</tspan><tspan x="{suffix_x}" textLength="{suffix_width}" lengthAdjust="spacingAndGlyphs">)</tspan>"#
            ),
            tooltip: Some(format!(
                "Actual contribution: {perc}%. Weighted contribution score (0–100): {weighted}%."
            )),
            sizing: TextSizing::Spans,
        }
    }
}
impl<'a> Renderer<'a> {
    pub fn new(media: &'a mut dyn MediaStore, translator: &'a mut dyn Translator) -> Result<Self> {
        Ok(Self {
            icons: Icon::load()?,
            media,
            translator,
            subscript_gap: SUBSCRIPT_GAP,
        })
    }
    pub fn render(
        &mut self,
        repo: &Repo,
        name: &str,
        contributors: &[Contributor],
        show_stats: bool,
        theme: &Theme,
        background: Option<&ImgOptions>,
    ) -> Result<String> {
        let link: reqwest::Url = reqwest::Url::parse(&repo.display_url())
            .context("repository link must be an absolute HTTPS URL")?;
        ensure!(
            link.scheme() == "https" && link.host_str().is_some(),
            "repository link must be an HTTPS URL"
        );
        let mut svg: String = format!(
            r##"<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="412" height="134" viewBox="0 0 412 134" role="img" aria-label="{}"><title>{}</title>{}<defs><clipPath id="canvas-clip"><rect width="412" height="134" rx="6"/></clipPath></defs><g clip-path="url(#canvas-clip)"><rect width="412" height="134" fill="var(--canvas)"/>"##,
            escape(name),
            escape(name),
            theme.css()
        );
        if let Some(background) = background {
            let data: Arc<str> = self
                .media
                .load(&background.img)
                .context("could not load background image")?;
            write!(
                svg,
                r#"<image href="{}" width="412" height="134" preserveAspectRatio="{}" opacity="{}"/>"#,
                escape(&data),
                background.aspect_ratio()?,
                background.opacity
            )?;
        }
        let icon: &str = if repo.is_private {
            "repo_private_outer"
        } else if repo.is_archived {
            "repo_archive"
        } else if repo.is_template {
            "repo_template"
        } else {
            "repo"
        };
        svg.push_str(&self.icon(icon, PADDING, 18.0, PADDING));
        if repo.is_private {
            svg.push_str(&self.icon("repo_private_inner", PADDING, 18.0, PADDING));
        }
        let badge: String = format!(
            "{}{}",
            if repo.is_private { "Private" } else { "Public" },
            if repo.is_archived {
                " archive"
            } else if repo.is_template {
                " template"
            } else {
                ""
            }
        );
        let badge_size: f64 = NAME_SIZE * 0.7;
        let badge_width: f64 = measure(&badge, badge_size).round() + PADDING;
        let badge_x: f64 = WIDTH - PADDING - badge_width;
        let display_name: String = truncate(name, (badge_x - 42.0).max(0.0), NAME_SIZE);
        let target: String = escape(&repo.display_url());
        let name_width: f64 = measure(&display_name, NAME_SIZE);
        write!(
            svg,
            r#"<a href="{target}" target="_blank"><text x="33" y="29.118" font-size="{NAME_SIZE}" font-weight="700" fill="var(--link)" textLength="{name_width}" lengthAdjust="spacingAndGlyphs">{}</text></a>"#,
            escape(&display_name)
        )?;
        let badge_translations: BTreeMap<String, String> = self.translator.translations(&badge)?;
        let color: &str = if repo.is_archived {
            "var(--danger)"
        } else {
            "var(--text)"
        };
        svg.push_str(&lang_switch(&badge, &badge_translations, |text, _| format!(r#"<g transform="translate({badge_x},17.118)"><rect width="{badge_width}" height="16" rx="8" fill="transparent" stroke="var(--border)"/><text x="8" y="11.5" font-size="{badge_size}" textLength="{}" lengthAdjust="spacingAndGlyphs" fill="{color}">{}</text></g>"#, badge_width - PADDING, escape(text))));
        if let Some(description) = repo.description.as_ref().filter(|val| !val.is_empty()) {
            let translations: BTreeMap<String, String> =
                self.translator.translations(description)?;
            svg.push_str(&lang_switch(description, &translations, |text, locale| {
                let rtl: bool = locale.is_some_and(is_rtl);
                let x: f64 = if rtl { WIDTH - PADDING } else { PADDING };
                let dir: &str = if rtl { "direction=\"rtl\" unicode-bidi=\"plaintext\" text-anchor=\"start\"" } else { "" };
                wrap(text, WIDTH - PADDING * 2.0, 3).iter().enumerate().map(|(idx, line)| format!(r#"<text x="{x}" y="{}" font-size="{DESC_SIZE}" fill="var(--text)" textLength="{}" lengthAdjust="spacingAndGlyphs" {dir}>{}</text>"#, 57.299 + idx as f64 * DESC_SIZE * 1.35, measure(line, DESC_SIZE).min(WIDTH - PADDING * 2.0), escape(line))).collect::<String>()
            }));
        }
        let groups: Vec<Group> = self.footer(repo, contributors, show_stats)?;
        let total: f64 = groups.iter().map(|group| group.width).sum();
        let available: f64 = WIDTH - PADDING * 2.0;
        let gap: f64 = if groups.len() <= 1 {
            0.0
        } else {
            ((available - total) / (groups.len() - 1) as f64).clamp(0.0, META_SIZE * 0.65)
        };
        let natural: f64 = total + groups.len().saturating_sub(1) as f64 * gap;
        let scale: f64 = if natural > available {
            available / natural
        } else {
            1.0
        };
        write!(
            svg,
            r#"<g transform="translate({PADDING},118) scale({scale},1)">"#
        )?;
        let mut x: f64 = 0.0;
        for group in groups {
            write!(svg, r#"<g transform="translate({x},0)">{}</g>"#, group.svg)?;
            x += group.width + gap;
        }
        svg.push_str(r#"</g></g><rect x="0.5" y="0.5" width="411" height="133" rx="6" fill="none" stroke="var(--border)"/></svg>"#);
        Ok(svg)
    }
    fn icon(&self, name: &str, x: f64, y: f64, size: f64) -> String {
        self.icons
            .get(&format!("icon_{name}"))
            .map_or_else(String::new, |icon| icon.at(x, y, size))
    }
    fn footer_icon(&self, name: &str) -> String {
        self.icons
            .get(&format!("icon_{name}"))
            .map_or_else(String::new, |icon| {
                icon.centered_at(0.0, FOOTER_CENTER_Y, META_SIZE)
            })
    }
    fn metric(&self, repo: &Repo, icon: &str, suffix: &str, text: &str) -> Group {
        self.metric_text(repo, icon, suffix, MetricText::plain(text))
    }
    fn metric_text(&self, repo: &Repo, icon: &str, suffix: &str, text: MetricText) -> Group {
        let target: String = if repo.is_private {
            repo.display_url()
        } else {
            format!("{}/{}", repo.url.trim_end_matches('/'), suffix)
        };
        let text_width: f64 = text.width;
        let sizing: String = match text.sizing {
            TextSizing::Label => {
                format!(r#" textLength="{text_width}" lengthAdjust="spacingAndGlyphs""#)
            }
            TextSizing::Spans => String::new(),
        };
        let tooltip: String = text.tooltip.as_deref().map_or_else(String::new, |tooltip| {
            format!("<title>{}</title>", escape(tooltip))
        });
        Group {
            width: PADDING + text_width,
            svg: format!(
                r#"<a href="{}" target="_blank">{tooltip}{}<text x="16" y="{FOOTER_CENTER_Y}" dominant-baseline="central" font-size="{META_SIZE}" fill="var(--text)"{sizing}>{}</text></a>"#,
                escape(&target),
                self.footer_icon(icon),
                text.svg
            ),
        }
    }
    fn footer(
        &mut self,
        repo: &Repo,
        contributors: &[Contributor],
        show_stats: bool,
    ) -> Result<Vec<Group>> {
        let mut groups: Vec<Group> = Vec::new();
        if let Some(lang) = &repo.primary_lang {
            let color: &str = lang
                .color
                .as_deref()
                .filter(|color| valid_color(color))
                .unwrap_or("var(--text)");
            let text_width: f64 = measure(&lang.name, META_SIZE);
            groups.push(Group { width: PADDING + text_width, svg: format!(r#"<circle cx="5" cy="{FOOTER_CENTER_Y}" r="4.5" fill="{color}"/><text x="16" y="{FOOTER_CENTER_Y}" dominant-baseline="central" font-size="{META_SIZE}" fill="var(--text)" textLength="{text_width}" lengthAdjust="spacingAndGlyphs">{}</text>"#, escape(&lang.name)) });
        }
        for (count, icon, suffix) in [
            (repo.stargazer_count, "star", "stargazers"),
            (repo.fork_count, "fork", "forks"),
        ] {
            if count > 0 {
                groups.push(self.metric(repo, icon, suffix, &format_count(count)));
            }
        }
        if repo.issues.total_count > 0 || repo.issues_help.total_count > 0 {
            let text: String = format!(
                "{}{}",
                format_count(repo.issues.total_count),
                if repo.issues_help.total_count > 0 {
                    format!(" ({})", format_count(repo.issues_help.total_count))
                } else {
                    String::new()
                }
            );
            groups.push(self.metric(repo, "issue_outer", "issues", &text));
        }
        if repo.pull_requests.total_count > 0 {
            groups.push(self.metric(
                repo,
                "pr",
                "pulls",
                &format_count(repo.pull_requests.total_count),
            ));
        }
        if !contributors.is_empty() {
            groups.push(self.contributors(repo, contributors));
        }
        let total: f64 = contributors
            .iter()
            .map(|contributor| contributor.additions)
            .sum();
        if show_stats
            && contributors.len() > 1
            && total > 0.0
            && let Some(user) = contributors
                .iter()
                .find(|contributor| contributor.is_user && contributor.additions > 0.0)
        {
            let share: f64 = user.additions / total;
            let contributor_count: usize = contributors
                .iter()
                .filter(|contributor| contributor.additions > 0.0)
                .count();
            let weighted: Option<f64> = weighted_contribution(share, contributor_count);
            let mut text: MetricText =
                MetricText::contribution(share * 100.0, weighted, self.subscript_gap);
            let mut avatar_gap: f64 = if weighted.is_some() {
                WEIGHTED_TRAILING_SPACE - SUBSCRIPT_RESERVED_GAP
            } else {
                META_SIZE * 0.3
            };
            let available: f64 =
                WIDTH - PADDING * 2.0 - groups.iter().map(|group| group.width).sum::<f64>();
            if weighted.is_some() && PADDING + text.width + avatar_gap + AVATAR_SIZE > available {
                text = MetricText::contribution(share * 100.0, None, self.subscript_gap);
                avatar_gap = META_SIZE * 0.3;
            }
            let mut group: Group = self.metric_text(repo, "stats", "graphs/contributors", text);
            group
                .svg
                .push_str(&self.avatar(user, group.width + avatar_gap, "stats-user"));
            group.width += avatar_gap + AVATAR_SIZE;
            groups.push(group);
        }
        Ok(groups)
    }
    fn contributors(&mut self, repo: &Repo, contributors: &[Contributor]) -> Group {
        let mut indices: Vec<usize> = (0..contributors.len().min(MAX_AVATARS)).collect();
        let user_idx: Option<usize> = contributors
            .iter()
            .position(|contributor| contributor.is_user);
        let outside: bool = user_idx.is_some_and(|idx| idx >= MAX_AVATARS);
        if outside {
            indices.truncate(3);
            if let Some(idx) = user_idx {
                indices.push(idx);
            }
        }
        let count: String = if contributors.len() > MAX_AVATARS {
            format_count(contributors.len() as u64)
        } else {
            String::new()
        };
        let mut group: Group = self.metric(
            repo,
            if contributors.len() == 1 {
                "user"
            } else {
                "collab"
            },
            "graphs/contributors",
            &count,
        );
        let mut x: f64 = group.width
            + if count.is_empty() {
                0.0
            } else {
                META_SIZE * 0.3
            };
        for (pos, idx) in indices.iter().enumerate() {
            if outside && pos == 3 {
                group.svg.push_str(&footer_text(x, ".."));
                x += measure("..", META_SIZE) + META_SIZE * 0.1;
            }
            group
                .svg
                .push_str(&self.avatar(&contributors[*idx], x, &format!("contributor-{pos}")));
            x += if pos + 1 == indices.len() || outside && pos == 2 {
                AVATAR_SIZE
            } else {
                AVATAR_STEP
            };
        }
        if indices
            .last()
            .is_some_and(|idx| *idx + 1 < contributors.len())
        {
            group.svg.push_str(&footer_text(x, ".."));
            x += measure("..", META_SIZE);
        }
        group.width = x;
        group
    }
    fn avatar(&mut self, contributor: &Contributor, x: f64, id: &str) -> String {
        let radius: f64 = AVATAR_SIZE / 2.0;
        let y: f64 = FOOTER_CENTER_Y - radius;
        let mut svg: String = format!(
            r#"<g transform="translate({x},{y})"><title>{}</title>"#,
            escape(&contributor.identity.login)
        );
        let img: Option<Arc<str>> = contributor
            .avatar_url
            .as_ref()
            .and_then(|src| self.media.load(src).ok());
        if let Some(img) = img {
            write!(svg, r#"<defs><clipPath id="{id}"><circle cx="{radius}" cy="{radius}" r="{radius}"/></clipPath></defs><image href="{}" width="{AVATAR_SIZE}" height="{AVATAR_SIZE}" clip-path="url(#{id})"/>"#, escape(&img)).expect("writing to a String cannot fail");
        } else {
            write!(svg, r##"<circle cx="{radius}" cy="{radius}" r="{radius}" fill="#d0d7de"/><text x="{radius}" y="{}" text-anchor="middle" font-size="16" fill="#57606a">?</text>"##, radius + 5.0).expect("writing to a String cannot fail");
        }
        let border: &str = if contributor.is_user {
            "var(--user-border)"
        } else {
            "var(--border)"
        };
        let border_width: f64 = if contributor.is_user { 2.25 } else { 1.0 };
        write!(svg, r#"<circle cx="{radius}" cy="{radius}" r="{}" fill="none" stroke="{border}" stroke-width="{border_width}"/></g>"#, radius - border_width / 2.0).expect("writing to a String cannot fail");
        svg
    }
}
fn weighted_contribution(share: f64, contributor_count: usize) -> Option<f64> {
    if contributor_count < WEIGHTED_MIN_CONTRIBUTORS
        || !share.is_finite()
        || !(0.0..=1.0).contains(&share)
    {
        return None;
    }
    let avg_other_share: f64 = (1.0 - share) / (contributor_count - 1) as f64;
    Some(share / (share + avg_other_share) * 100.0)
}
fn footer_text(x: f64, text: &str) -> String {
    let text_width: f64 = measure(text, META_SIZE);
    format!(
        r#"<text x="{x}" y="{FOOTER_CENTER_Y}" dominant-baseline="central" font-size="{META_SIZE}" fill="var(--text)" textLength="{text_width}" lengthAdjust="spacingAndGlyphs">{}</text>"#,
        escape(text)
    )
}
pub fn escape(val: &str) -> String {
    val.chars()
        .filter(|character| {
            *character == '\t'
                || *character == '\n'
                || *character == '\r'
                || *character >= ' ' && !matches!(*character, '\u{fffe}' | '\u{ffff}')
        })
        .map(|character| match character {
            '&' => "&amp;".to_owned(),
            '<' => "&lt;".to_owned(),
            '>' => "&gt;".to_owned(),
            '"' => "&quot;".to_owned(),
            '\'' => "&apos;".to_owned(),
            other => other.to_string(),
        })
        .collect()
}
fn measure(val: &str, size: f64) -> f64 {
    let width: f64 = val
        .chars()
        .map(|character| {
            size * if "mwMW@&%#$".contains(character) {
                0.68
            } else if "il!|:;.,`'".contains(character) {
                0.28
            } else if character == ' ' {
                0.33
            } else {
                0.53
            }
        })
        .sum();
    (width - (width * 0.08).min(val.chars().count().saturating_sub(1) as f64 * 0.02 * size))
        .max(0.0)
}
fn truncate(val: &str, width: f64, size: f64) -> String {
    if measure(val, size) <= width {
        return val.to_owned();
    }
    let mut res: String = String::new();
    for character in val.chars() {
        if measure(&format!("{res}{character}…"), size) > width {
            break;
        }
        res.push(character);
    }
    if measure("…", size) <= width {
        res.push('…');
    }
    res
}
fn wrap(val: &str, width: f64, limit: usize) -> Vec<String> {
    let mut lines: Vec<String> = Vec::new();
    let mut cur: String = String::new();
    for word in val.split_whitespace() {
        if !cur.is_empty() && measure(&format!("{cur} {word}"), DESC_SIZE) <= width {
            cur.push(' ');
            cur.push_str(word);
            continue;
        }
        if !cur.is_empty() {
            lines.push(std::mem::take(&mut cur));
        }
        for character in word.chars() {
            if !cur.is_empty() && measure(&format!("{cur}{character}"), DESC_SIZE) > width {
                lines.push(std::mem::take(&mut cur));
            }
            cur.push(character);
        }
    }
    if !cur.is_empty() {
        lines.push(cur);
    }
    if lines.len() > limit {
        lines.truncate(limit);
        if let Some(last) = lines.last_mut() {
            *last = truncate(&format!("{last}…"), width, DESC_SIZE);
        }
    }
    lines
}
pub fn format_count(val: u64) -> String {
    for (div, suffix) in [(1_000_000_000_u64, "B"), (1_000_000, "M"), (1_000, "K")] {
        if val >= div {
            return format!("{}{suffix}", trim_decimal(val as f64 / div as f64));
        }
    }
    val.to_string()
}
fn trim_decimal(val: f64) -> String {
    format!("{val:.1}")
        .trim_end_matches('0')
        .trim_end_matches('.')
        .to_owned()
}
fn is_rtl(locale: &str) -> bool {
    matches!(
        locale.split('-').next().unwrap_or(locale),
        "ar" | "he" | "fa" | "ur" | "ps" | "sd" | "ug" | "yi" | "ckb" | "dv"
    )
}
fn lang_switch<F: Fn(&str, Option<&str>) -> String>(
    orig: &str,
    translations: &BTreeMap<String, String>,
    render: F,
) -> String {
    if translations.is_empty() {
        return render(orig, None);
    }
    let mut svg: String = "<switch>".to_owned();
    let mut translations: Vec<(&String, &String)> = translations.iter().collect();
    translations.sort_by_key(|(locale, _)| std::cmp::Reverse(locale.len()));
    for (locale, text) in translations {
        svg.push_str(&format!(
            "<g systemLanguage=\"{}\">{}</g>",
            escape(locale),
            render(text, Some(locale))
        ));
    }
    svg.push_str(&format!("<g>{}</g></switch>", render(orig, None)));
    svg
}
