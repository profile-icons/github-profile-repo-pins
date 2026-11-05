use crate::Result;
use anyhow::{Context, ensure};
use base64::{Engine, engine::general_purpose::STANDARD};
use image as img;
use img::{DynamicImage as DynamicImg, ImageEncoder as ImgEncoder, ImageReader as ImgReader};
use std::{
    collections::HashMap,
    io::{Cursor, Read},
    sync::Arc,
    time::Duration,
};

const MAX_BYTES: u64 = 32 * 1024 * 1024;
const MAX_DIM: u32 = 1600;
pub trait MediaStore {
    fn load(&mut self, src: &str) -> Result<Arc<str>>;
}
pub struct MediaLoader {
    client: reqwest::blocking::Client,
    cache: HashMap<String, Arc<str>>,
    svg_options: Option<resvg::usvg::Options<'static>>,
}
impl MediaLoader {
    pub fn new() -> Result<Self> {
        Ok(Self {
            client: reqwest::blocking::Client::builder()
                .timeout(Duration::from_secs(10))
                .user_agent("github-profile-repo-pins/2.0")
                .redirect(reqwest::redirect::Policy::limited(3))
                .build()?,
            cache: HashMap::new(),
            svg_options: None,
        })
    }
}
impl MediaStore for MediaLoader {
    fn load(&mut self, src: &str) -> Result<Arc<str>> {
        if let Some(cached) = self.cache.get(src) {
            return Ok(Arc::clone(cached));
        }
        let mut bytes: Vec<u8> = Vec::new();
        if let Some(data) = src.strip_prefix("data:") {
            let (_type, encoded): (&str, &str) =
                data.split_once(',').context("invalid image data URL")?;
            ensure!(
                _type.starts_with("image/")
                    && _type.ends_with(";base64")
                    && encoded.len() as u64 <= MAX_BYTES * 4 / 3 + 4,
                "expected a bounded base64 image data URL"
            );
            bytes = STANDARD.decode(encoded)?;
        } else if src.starts_with("https://") || src.starts_with("http://") {
            self.client
                .get(src)
                .send()?
                .error_for_status()?
                .take(MAX_BYTES + 1)
                .read_to_end(&mut bytes)?;
        } else {
            std::fs::File::open(src)
                .with_context(|| format!("image not found: {src}"))?
                .take(MAX_BYTES + 1)
                .read_to_end(&mut bytes)?;
        }
        ensure!(
            bytes.len() as u64 <= MAX_BYTES,
            "image exceeds 32 MiB limit"
        );
        let img: DynamicImg = decode(&bytes, &mut self.svg_options)?;
        let img: DynamicImg = if img.width() > MAX_DIM || img.height() > MAX_DIM {
            img.thumbnail(MAX_DIM, MAX_DIM)
        } else {
            img
        };
        let img: img::RgbaImage = img.into_rgba8();
        let mut encoded: Vec<u8> = Vec::new();
        img::codecs::webp::WebPEncoder::new_lossless(&mut encoded).write_image(
            img.as_raw(),
            img.width(),
            img.height(),
            img::ExtendedColorType::Rgba8,
        )?;
        let res: Arc<str> = Arc::from(format!(
            "data:image/webp;base64,{}",
            STANDARD.encode(encoded)
        ));
        self.cache.insert(src.to_owned(), Arc::clone(&res));
        Ok(res)
    }
}
fn decode(
    bytes: &[u8],
    svg_options: &mut Option<resvg::usvg::Options<'static>>,
) -> Result<DynamicImg> {
    let text: &str = std::str::from_utf8(bytes)
        .unwrap_or("")
        .trim_start_matches('\u{feff}')
        .trim_start();
    if text.starts_with("<svg") || text.starts_with("<?xml") {
        let options: &resvg::usvg::Options<'_> = svg_options.get_or_insert_with(|| {
            let mut options: resvg::usvg::Options<'static> = resvg::usvg::Options::default();
            options.fontdb_mut().load_system_fonts();
            let installed: Vec<String> = options
                .fontdb
                .faces()
                .flat_map(|face| face.families.iter().map(|(name, _)| name.clone()))
                .collect();
            let family: Option<String> = ["Arial", "Noto Sans", "Liberation Sans", "DejaVu Sans"]
                .iter()
                .find(|candidate| installed.iter().any(|name| name == **candidate))
                .map(|name| (*name).to_owned())
                .or_else(|| installed.first().cloned());
            if let Some(family) = family {
                options.fontdb_mut().set_sans_serif_family(family.clone());
                options.fontdb_mut().set_serif_family(family.clone());
                options.font_family = family;
            }
            options
        });
        let tree: resvg::usvg::Tree = resvg::usvg::Tree::from_data(bytes, options)?;
        let size: resvg::usvg::Size = tree.size();
        let scale: f32 = (MAX_DIM as f32 / size.width().max(size.height())).min(1.0);
        let width: u32 = (size.width() * scale).ceil().max(1.0) as u32;
        let height: u32 = (size.height() * scale).ceil().max(1.0) as u32;
        let mut pixmap: resvg::tiny_skia::Pixmap =
            resvg::tiny_skia::Pixmap::new(width, height).context("invalid SVG size")?;
        resvg::render(
            &tree,
            resvg::tiny_skia::Transform::from_scale(scale, scale),
            &mut pixmap.as_mut(),
        );
        let mut rgba: Vec<u8> = pixmap.take();
        for pixel in rgba.as_chunks_mut::<4>().0 {
            let alpha: u32 = u32::from(pixel[3]);
            for channel in &mut pixel[..3] {
                let straight: u32 = (u32::from(*channel) * 255 + alpha / 2)
                    .checked_div(alpha)
                    .unwrap_or(0);
                *channel = straight.min(255) as u8;
            }
        }
        return Ok(DynamicImg::ImageRgba8(
            img::RgbaImage::from_raw(width, height, rgba).context("invalid SVG pixel buffer")?,
        ));
    }
    let mut reader: ImgReader<Cursor<&[u8]>> =
        ImgReader::new(Cursor::new(bytes)).with_guessed_format()?;
    let mut limits: img::Limits = img::Limits::default();
    limits.max_alloc = Some(128 * 1024 * 1024);
    reader.limits(limits);
    let mut decoder: Box<dyn img::ImageDecoder> = Box::new(reader.into_decoder()?);
    let orientation: img::metadata::Orientation = decoder.orientation()?;
    let mut img: DynamicImg = DynamicImg::from_decoder(decoder)?;
    img.apply_orientation(orientation);
    Ok(img)
}
