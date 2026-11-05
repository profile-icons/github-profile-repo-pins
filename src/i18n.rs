use crate::Result;
#[cfg(feature = "translation")]
use serde::Deserialize;
use std::collections::BTreeMap;
#[cfg(feature = "translation")]
#[path = "translation.rs"]
mod native;

pub trait Translator {
    fn translations(&mut self, text: &str) -> Result<BTreeMap<String, String>>;
}
pub struct NoTranslation;
impl Translator for NoTranslation {
    fn translations(&mut self, _text: &str) -> Result<BTreeMap<String, String>> {
        Ok(BTreeMap::new())
    }
}
#[cfg(feature = "translation")]
#[derive(Deserialize)]
struct Translations {
    static_translations: BTreeMap<String, BTreeMap<String, String>>,
    supported_dynamic_locales: Vec<String>,
    #[serde(rename = "hy_mt2_languages", alias = "hy_mt2_langs")]
    hy_mt2_langs: BTreeMap<String, String>,
    nllb_codes: BTreeMap<String, String>,
}
pub fn create(
    is_enabled: bool,
    is_nllb: bool,
    cache: Option<std::path::PathBuf>,
    locales: Option<&str>,
) -> Result<Box<dyn Translator>> {
    if !is_enabled {
        return Ok(Box::new(NoTranslation));
    }
    #[cfg(feature = "translation")]
    {
        Ok(Box::new(native::NativeTranslator::new(
            is_nllb, cache, locales,
        )?))
    }
    #[cfg(not(feature = "translation"))]
    {
        let _ = (is_nllb, cache, locales);
        anyhow::bail!(
            "this binary was built without translation; rebuild with the translation feature"
        );
    }
}
