#[path = "translation/cache.rs"]
mod cache;
#[path = "translation/hy_mt2.rs"]
mod hy_mt2;
#[path = "translation/nllb.rs"]
mod nllb;

use super::{Translations, Translator};
use crate::Result;
use anyhow::{Context, ensure};
use cache::ModelCache;
use hy_mt2::HyMt2;
use nllb::Nllb;
use std::{collections::BTreeMap, path::PathBuf};

trait TranslationEngine {
    fn translate(&mut self, text: &str, src: &str, target: &str) -> Result<String>;
}
#[derive(Clone, Copy)]
enum Family {
    HyMt2,
    Nllb,
}

pub(super) struct NativeTranslator {
    translations: Translations,
    cache: ModelCache,
    is_nllb_on_failure: bool,
    hy_mt2: Option<Box<dyn TranslationEngine>>,
    nllb: Option<Box<dyn TranslationEngine>>,
    is_hy_unavailable: bool,
    results: BTreeMap<String, BTreeMap<String, String>>,
}
impl NativeTranslator {
    pub fn new(
        is_nllb_on_failure: bool,
        cache: Option<PathBuf>,
        locales: Option<&str>,
    ) -> Result<Self> {
        let mut translations: Translations =
            serde_json::from_str(include_str!("../files/i18n.json"))?;
        if let Some(locales) = locales {
            translations.supported_dynamic_locales = locales
                .split(',')
                .map(str::trim)
                .filter(|locale| !locale.is_empty())
                .map(str::to_owned)
                .collect();
            for locale in &translations.supported_dynamic_locales {
                ensure!(
                    translations.hy_mt2_langs.contains_key(locale)
                        || translations.nllb_codes.contains_key(locale),
                    "unsupported translation locale: {locale}"
                );
            }
        }
        let dir: PathBuf = cache
            .or_else(|| {
                std::env::var_os("XDG_CACHE_HOME")
                    .map(PathBuf::from)
                    .map(|dir| dir.join("repo-pins"))
            })
            .unwrap_or_else(|| PathBuf::from(".repo-pins-cache"));
        Ok(Self {
            translations,
            cache: ModelCache::new(dir)?,
            is_nllb_on_failure,
            hy_mt2: None,
            nllb: None,
            is_hy_unavailable: false,
            results: BTreeMap::new(),
        })
    }
    fn translate(
        &mut self,
        text: &str,
        src: &str,
        target: &str,
        family: Family,
    ) -> Result<Option<String>> {
        let codes: &BTreeMap<String, String> = match family {
            Family::HyMt2 => &self.translations.hy_mt2_langs,
            Family::Nllb => &self.translations.nllb_codes,
        };
        let Some((src, target)) = codes.get(src).zip(codes.get(target)) else {
            return Ok(None);
        };
        if src == target {
            return Ok(None);
        }
        let slot: &mut Option<Box<dyn TranslationEngine>> = match family {
            Family::HyMt2 => &mut self.hy_mt2,
            Family::Nllb => &mut self.nllb,
        };
        if slot.is_none() {
            *slot = Some(match family {
                Family::HyMt2 => Box::new(HyMt2::load(&self.cache)?) as Box<dyn TranslationEngine>,
                Family::Nllb => Box::new(Nllb::load(&self.cache)?) as Box<dyn TranslationEngine>,
            });
        }
        let translated: String = slot
            .as_mut()
            .context("translation engine was not initialized")?
            .translate(text, src, target)?;
        ensure!(
            !translated.trim().is_empty(),
            "translation engine returned empty text"
        );
        Ok(Some(translated.trim().to_owned()))
    }
    fn detect(&self, text: &str) -> String {
        let code: &str = whatlang::detect(text)
            .map(|info| info.lang().code())
            .unwrap_or("eng");
        if code == "cmn" {
            return "zh".to_owned();
        }
        if code == "ara" {
            return "ar".to_owned();
        }
        self.translations
            .nllb_codes
            .iter()
            .find(|(_, val)| val.split('_').next() == Some(code))
            .map(|(locale, _)| locale.clone())
            .unwrap_or_else(|| "en".to_owned())
    }
}
impl Translator for NativeTranslator {
    fn translations(&mut self, text: &str) -> Result<BTreeMap<String, String>> {
        if let Some(translations) = self
            .translations
            .static_translations
            .get(&text.trim().to_lowercase())
        {
            return Ok(translations.clone());
        }
        if text.trim().is_empty() {
            return Ok(BTreeMap::new());
        }
        if let Some(translations) = self.results.get(text) {
            return Ok(translations.clone());
        }
        let src: String = self.detect(text);
        let mut res: BTreeMap<String, String> = BTreeMap::from([(src.clone(), text.to_owned())]);
        for target in self.translations.supported_dynamic_locales.clone() {
            if target == src {
                continue;
            }
            let primary_supported: bool = self.translations.hy_mt2_langs.contains_key(&src)
                && self.translations.hy_mt2_langs.contains_key(&target);
            let mut translated: Option<String> = None;
            if primary_supported && !self.is_hy_unavailable {
                match self.translate(text, &src, &target, Family::HyMt2) {
                    Ok(val) => translated = val,
                    Err(err) if self.is_nllb_on_failure => {
                        self.is_hy_unavailable = true;
                        eprintln!("Hy-MT2 unavailable; trying NLLB: {err:#}");
                    }
                    Err(err) => {
                        return Err(err).with_context(|| format!("Hy-MT2 {src} -> {target}"));
                    }
                }
            }
            if translated.is_none() && (!primary_supported || self.is_nllb_on_failure) {
                translated = self
                    .translate(text, &src, &target, Family::Nllb)
                    .with_context(|| format!("NLLB fallback {src} -> {target}"))?;
            }
            if let Some(translated) = translated {
                res.insert(target, translated);
            }
        }
        self.results.insert(text.to_owned(), res.clone());
        Ok(res)
    }
}
