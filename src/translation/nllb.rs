use super::{
    TranslationEngine,
    cache::{AssetSpec, ModelCache, ModelSpec},
};
use crate::Result;
use anyhow::{Context, ensure};
use ort::{
    session::{Session, SessionInputValue as SessionInputVal},
    value::{DynValue as DynVal, Tensor},
};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};

const MAX_INPUT_TOKENS: usize = 128;
const MAX_NEW_TOKENS: usize = 128;
const EOS: i64 = 2;
const MODEL: ModelSpec = ModelSpec {
    repo: "TigreGotico/nllb-200-distilled-600M-onnx",
    revision: "9ca4d234e9a6d46fb36136d4c4fc40cab41b51ab",
    dir: "nllb",
};

pub(super) struct Nllb {
    tokenizer: tokenizers::Tokenizer,
    engine: Seq2Seq,
}
impl Nllb {
    pub fn load(cache: &ModelCache) -> Result<Self> {
        init_runtime()?;
        let tokenizer_file: PathBuf =
            cache.file(MODEL, AssetSpec::new("tokenizer.json", "tokenizer.json"))?;
        let tokenizer: tokenizers::Tokenizer = tokenizers::Tokenizer::from_file(tokenizer_file)
            .map_err(|error| anyhow::anyhow!("NLLB tokenizer: {error}"))?;
        for (remote, local) in [
            ("int8/encoder_model.onnx", "encoder_model.onnx"),
            ("int8/decoder_model.onnx", "decoder_model.onnx"),
            ("int8/decoder_model.onnx_data", "decoder_model.onnx_data"),
            (
                "int8/decoder_with_past_model.onnx",
                "decoder_with_past_model.onnx",
            ),
            (
                "int8/decoder_with_past_model.onnx_data",
                "decoder_with_past_model.onnx_data",
            ),
        ] {
            cache.file(MODEL, AssetSpec::new(remote, local))?;
        }
        Ok(Self {
            tokenizer,
            engine: Seq2Seq::load(&cache.dir(MODEL))?,
        })
    }
}
impl TranslationEngine for Nllb {
    fn translate(&mut self, text: &str, src: &str, target: &str) -> Result<String> {
        let lang: u32 = self
            .tokenizer
            .token_to_id(src)
            .context("NLLB source language token not found")?;
        let target: i64 = self
            .tokenizer
            .token_to_id(target)
            .map(i64::from)
            .context("NLLB target language token not found")?;
        let encoded: tokenizers::Encoding = self
            .tokenizer
            .encode(text, false)
            .map_err(|err| anyhow::anyhow!("NLLB tokenization: {err}"))?;
        let input: Vec<i64> = std::iter::once(i64::from(lang))
            .chain(
                encoded
                    .get_ids()
                    .iter()
                    .copied()
                    .map(i64::from)
                    .take(MAX_INPUT_TOKENS - 2),
            )
            .chain(std::iter::once(EOS))
            .collect();
        let tokens: Vec<i64> = self.engine.generate(input, target, MAX_NEW_TOKENS)?;
        let ids: Vec<u32> = tokens
            .into_iter()
            .skip(2)
            .take_while(|token| *token != EOS)
            .map(u32::try_from)
            .collect::<std::result::Result<Vec<u32>, _>>()?;
        self.tokenizer
            .decode(&ids, true)
            .map_err(|err| anyhow::anyhow!("NLLB decoding: {err}"))
    }
}
fn init_runtime() -> Result<()> {
    let path: PathBuf = std::env::var_os("ORT_DYLIB_PATH").map(PathBuf::from).context("NLLB coverage fallback requires ONNX Runtime 1.22: set ORT_DYLIB_PATH to its shared library")?;
    ensure!(
        path.is_file(),
        "ORT_DYLIB_PATH must point to an existing ONNX Runtime shared library"
    );
    std::panic::catch_unwind(|| {
        ort::init_from(path.to_string_lossy())
            .with_name("repo-pins")
            .commit()
    })
    .map_err(|_| {
        anyhow::anyhow!("could not load a compatible ONNX Runtime 1.22 shared library")
    })??;
    Ok(())
}

pub(crate) struct Seq2Seq {
    encoder: Session,
    decoder: Session,
    cached_decoder: Session,
}
impl Seq2Seq {
    pub(crate) fn load(dir: &Path) -> Result<Self> {
        Ok(Self {
            encoder: Session::builder()?.commit_from_file(dir.join("encoder_model.onnx"))?,
            decoder: Session::builder()?.commit_from_file(dir.join("decoder_model.onnx"))?,
            cached_decoder: Session::builder()?
                .commit_from_file(dir.join("decoder_with_past_model.onnx"))?,
        })
    }
    pub(crate) fn generate(
        &mut self,
        input: Vec<i64>,
        target: i64,
        max: usize,
    ) -> Result<Vec<i64>> {
        ensure!(
            !input.is_empty() && max > 0,
            "translation needs input tokens and a positive output limit"
        );
        let len: usize = input.len();
        let attention: Tensor<i64> = Tensor::from_array(([1, len], vec![1_i64; len]))?;
        let output: ort::session::SessionOutputs<'_> = self.encoder.run(ort::inputs!["input_ids" => Tensor::from_array(([1, len], input))?, "attention_mask" => attention.view()])?;
        let mut encoder: BTreeMap<String, DynVal> = output
            .into_iter()
            .map(|(name, val)| (name.to_owned(), val))
            .collect();
        let hidden: DynVal = encoder
            .remove("last_hidden_state")
            .or_else(|| encoder.into_values().next())
            .context("encoder returned no hidden state")?;
        let mut cache: BTreeMap<String, DynVal> = BTreeMap::new();
        let mut tokens: Vec<i64> = vec![EOS];
        for step in 0..max {
            let session: &mut Session = if step == 0 {
                &mut self.decoder
            } else {
                &mut self.cached_decoder
            };
            let token: i64 = *tokens.last().context("decoder sequence is empty")?;
            let ids: Tensor<i64> = Tensor::from_array(([1, 1], vec![token]))?;
            let mut vals: Vec<(String, SessionInputVal<'_>)> = Vec::new();
            for input in &session.inputs {
                let val: SessionInputVal<'_> = match input.name.as_str() {
                    "input_ids" | "decoder_input_ids" => (&ids).into(),
                    "encoder_attention_mask" | "attention_mask" => (&attention).into(),
                    "encoder_hidden_states" => (&hidden).into(),
                    name => cache
                        .get(name)
                        .with_context(|| format!("decoder input {name} has no cached value"))?
                        .into(),
                };
                vals.push((input.name.clone(), val));
            }
            let outputs: ort::session::SessionOutputs<'_> = session.run(vals)?;
            let logits: &DynVal = outputs
                .get("logits")
                .context("decoder returned no logits")?;
            let (shape, logits): (&ort::tensor::Shape, &[f32]) =
                logits.try_extract_tensor::<f32>()?;
            let width: usize =
                usize::try_from(*shape.last().context("decoder logits have no dimensions")?)?;
            ensure!(
                width > 0 && width <= logits.len(),
                "invalid decoder vocabulary dimension"
            );
            let next: i64 = if step == 0 {
                target
            } else {
                i64::try_from(
                    logits[logits.len() - width..]
                        .iter()
                        .enumerate()
                        .filter(|(_, val)| val.is_finite())
                        .max_by(|(left_idx, left), (right_idx, right)| {
                            left.total_cmp(right).then_with(|| right_idx.cmp(left_idx))
                        })
                        .map(|(idx, _)| idx)
                        .context("decoder logits contain no finite values")?,
                )?
            };
            for (name, val) in outputs {
                if let Some(suffix) = name.strip_prefix("present.") {
                    cache.insert(format!("past_key_values.{suffix}"), val);
                }
            }
            tokens.push(next);
            if next == EOS {
                break;
            }
        }
        Ok(tokens)
    }
}
