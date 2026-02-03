//! Configuration management for InsightBot
//!
//! Loads settings from environment variables (.env file)

use std::env;
use std::path::PathBuf;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Missing required environment variable: {0}")]
    MissingEnvVar(String),
    #[error("Invalid value for {0}: {1}")]
    InvalidValue(String, String),
}

/// Application configuration
#[derive(Debug, Clone)]
pub struct Config {
    /// Discord bot token
    pub discord_token: String,
    /// Gemini API key
    pub gemini_api_key: String,
    /// Optional guild ID for development (faster command sync)
    pub guild_id: Option<u64>,
    /// Audio sample rate (Discord uses 48kHz)
    pub sample_rate: u32,
    /// Audio channels (Discord uses stereo)
    pub channels: u16,
    /// Temporary audio directory
    pub temp_audio_dir: PathBuf,
    /// Default recording interval in seconds
    pub default_recording_interval: u64,
}

impl Config {
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self, ConfigError> {
        // Load .env file if present (ignore errors if not found)
        let _ = dotenvy::dotenv();

        let discord_token = env::var("DISCORD_TOKEN")
            .map_err(|_| ConfigError::MissingEnvVar("DISCORD_TOKEN".to_string()))?;

        let gemini_api_key = env::var("GEMINI_API_KEY")
            .map_err(|_| ConfigError::MissingEnvVar("GEMINI_API_KEY".to_string()))?;

        let guild_id = env::var("GUILD_ID")
            .ok()
            .filter(|s| !s.is_empty())
            .map(|s| {
                s.parse::<u64>()
                    .map_err(|_| ConfigError::InvalidValue("GUILD_ID".to_string(), s))
            })
            .transpose()?;

        let temp_audio_dir = env::var("TEMP_AUDIO_DIR")
            .unwrap_or_else(|_| "temp_audio".to_string())
            .into();

        let default_recording_interval = env::var("RECORDING_INTERVAL")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(300);

        Ok(Self {
            discord_token,
            gemini_api_key,
            guild_id,
            sample_rate: 48000,
            channels: 2,
            temp_audio_dir,
            default_recording_interval,
        })
    }
}

/// Gemini model identifiers
pub mod models {
    pub const GEMINI_FLASH: &str = "gemini-2.0-flash";
    pub const GEMINI_PRO: &str = "gemini-2.0-pro";
}
