pub mod app;
pub mod config;
pub mod contributors;
pub mod github;
mod hash;
pub mod i18n;
pub mod model;
pub mod output;
pub mod render;
pub mod stats;

pub type Result<T> = anyhow::Result<T>;
