use super::{
    TranslationEngine,
    cache::{AssetSpec, ModelCache, ModelSpec},
};
use crate::Result;
use anyhow::{Context, ensure};
use llama_cpp_2::{
    context::{LlamaContext, params::LlamaContextParams},
    llama_backend::LlamaBackend,
    llama_batch::LlamaBatch,
    model::{LlamaModel, params::LlamaModelParams},
    sampling::LlamaSampler,
    token::LlamaToken,
};
use std::{
    num::NonZeroU32,
    path::{Path, PathBuf},
    sync::OnceLock,
};

const CONTEXT_TOKENS: u32 = 2048;
const BATCH_TOKENS: u32 = 512;
const MAX_NEW_TOKENS: usize = 512;
const MODEL: ModelSpec = ModelSpec {
    repo: "tencent/Hy-MT2-1.8B-GGUF",
    revision: "a0c709d9fac510f2c807aa3af52872340dc37a4a",
    dir: "hy-mt2",
};
const WEIGHTS: AssetSpec = AssetSpec {
    bytes: Some(1_133_080_448),
    checksum: Some([
        0xdc, 0x5f, 0x44, 0xfc, 0xf1, 0xfa, 0x49, 0x6e, 0xe7, 0xad, 0x72, 0x59, 0x82, 0xc0, 0xc8,
        0xc5, 0x53, 0xa4, 0xde, 0x00, 0x25, 0x9b, 0x53, 0xaf, 0x84, 0xc4, 0xb8, 0x9f, 0xb0, 0xc0,
        0x66, 0x99,
    ]),
    ..AssetSpec::new("Hy-MT2-1.8B-Q4_K_M.gguf", "Hy-MT2-1.8B-Q4_K_M.gguf")
};
static BACKEND: OnceLock<std::result::Result<LlamaBackend, String>> = OnceLock::new();

pub(super) struct HyMt2 {
    model: LlamaModel,
    backend: &'static LlamaBackend,
    threads: i32,
    chat_template: String,
}
impl HyMt2 {
    pub fn load(cache: &ModelCache) -> Result<Self> {
        let override_path: Option<PathBuf> =
            std::env::var_os("REPO_PINS_MODEL_FILE").map(PathBuf::from);
        let path: PathBuf = match override_path {
            Some(path) => path,
            None => cache.file(MODEL, WEIGHTS)?,
        };
        Self::from_file(&path)
    }
    fn from_file(path: &Path) -> Result<Self> {
        let backend: &'static LlamaBackend = BACKEND
            .get_or_init(|| {
                let mut backend: LlamaBackend =
                    LlamaBackend::init().map_err(|err| err.to_string())?;
                backend.void_logs();
                Ok(backend)
            })
            .as_ref()
            .map_err(|err| anyhow::anyhow!("llama.cpp initialization: {err}"))?;
        let threads: i32 = match std::env::var("REPO_PINS_TRANSLATION_THREADS") {
            Ok(val) => val
                .parse()
                .context("REPO_PINS_TRANSLATION_THREADS must be an integer")?,
            Err(std::env::VarError::NotPresent) => i32::try_from(
                std::thread::available_parallelism()
                    .map_or(1, |count| count.get())
                    .min(8),
            )?,
            Err(err) => return Err(err.into()),
        };
        ensure!(
            (1..=128).contains(&threads),
            "translation thread count must be between 1 and 128"
        );
        eprintln!("Loading Hy-MT2 1.8B with {threads} CPU threads");
        let params: LlamaModelParams = LlamaModelParams::default().with_n_gpu_layers(0);
        let model: LlamaModel = LlamaModel::load_from_file(backend, path, &params)
            .context("could not load Hy-MT2 GGUF weights")?;
        ensure!(
            model.meta_val_str("general.architecture")? == "hunyuan-dense",
            "REPO_PINS_MODEL_FILE must contain a Hy-MT2 compatible hunyuan-dense model"
        );
        let chat_template: String = model.chat_template(None)?.to_string()?;
        Ok(Self {
            model,
            backend,
            threads,
            chat_template,
        })
    }
}
impl TranslationEngine for HyMt2 {
    fn translate(&mut self, text: &str, src: &str, target: &str) -> Result<String> {
        let prompt: String = render_prompt(&self.chat_template, text, src, target)?;
        let tokens: Vec<LlamaToken> = self.model.vocab().tokenize(prompt.as_bytes(), false, true);
        ensure!(!tokens.is_empty(), "Hy-MT2 prompt contains no tokens");
        ensure!(
            tokens.len() + MAX_NEW_TOKENS <= CONTEXT_TOKENS as usize,
            "description exceeds the Hy-MT2 context budget"
        );
        let params: LlamaContextParams = LlamaContextParams::default()
            .with_n_ctx(NonZeroU32::new(CONTEXT_TOKENS))
            .with_n_batch(BATCH_TOKENS)
            .with_n_threads(self.threads)
            .with_n_threads_batch(self.threads);
        let mut context: LlamaContext<'_> = self.model.new_context(self.backend, params)?;
        let mut batch: LlamaBatch<'_> = LlamaBatch::new(BATCH_TOKENS as usize, 1);
        let mut pos: usize = 0;
        for chunk in tokens.chunks(BATCH_TOKENS as usize) {
            batch.clear();
            for token in chunk {
                batch.add(*token, i32::try_from(pos)?, &[0], pos + 1 == tokens.len())?;
                pos += 1;
            }
            context.decode(&mut batch)?;
        }
        let mut sampler: LlamaSampler = LlamaSampler::greedy();
        let mut bytes: Vec<u8> = Vec::new();
        let mut ended: bool = false;
        for _ in 0..MAX_NEW_TOKENS {
            let token: LlamaToken = sampler.sample(&context, -1);
            if self.model.vocab().is_eog(token) {
                ended = true;
                break;
            }
            bytes.extend(self.model.vocab().token_to_piece(token, false, None));
            batch.clear();
            batch.add(token, i32::try_from(pos)?, &[0], true)?;
            context.decode(&mut batch)?;
            pos += 1;
        }
        ensure!(ended, "Hy-MT2 translation exceeded its output budget");
        let translated: String =
            String::from_utf8(bytes).context("Hy-MT2 returned invalid UTF-8")?;
        ensure!(
            !translated.trim().is_empty(),
            "Hy-MT2 returned an empty translation"
        );
        Ok(translated.trim().to_owned())
    }
}
fn instruction(text: &str, src: &str, target: &str) -> String {
    format!(
        "Translate the following text from {src} into {target}. Output only the translated text, without explanations. Preserve code identifiers and URLs.\n\n{text}"
    )
}
#[derive(serde::Serialize)]
struct ChatMessage {
    role: &'static str,
    content: String,
}
fn render_prompt(template: &str, text: &str, src: &str, target: &str) -> Result<String> {
    let msgs: [ChatMessage; 1] = [ChatMessage {
        role: "user",
        content: instruction(text, src, target),
    }];
    let env: minijinja::Environment<'_> = minijinja::Environment::new();
    env.render_str(
        template,
        minijinja::context! { messages => msgs, add_generation_prompt => true },
    )
    .context("could not render the Hy-MT2 chat template")
}
