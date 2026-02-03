//! InsightDebateBot - Rust Edition
//!
//! A Discord bot for recording and analyzing voice discussions using Gemini AI.
//! Features Opus audio encoding for efficient storage.

mod analyzer;
mod audio;
mod bot;
mod commands;
mod config;
mod database;
mod session;

use config::Config;
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| "info,insight_bot=debug".into()))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("InsightDebateBot starting...");

    // Load configuration
    let config = match Config::from_env() {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to load configuration: {}", e);
            error!("Please ensure DISCORD_TOKEN and GEMINI_API_KEY are set in .env file");
            std::process::exit(1);
        }
    };

    info!("Configuration loaded successfully");
    if let Some(guild_id) = config.guild_id {
        info!("Development mode: Commands will be registered to guild {}", guild_id);
    }

    // Create temp audio directory
    if let Err(e) = std::fs::create_dir_all(&config.temp_audio_dir) {
        error!("Failed to create temp audio directory: {}", e);
        std::process::exit(1);
    }

    // Run the bot
    if let Err(e) = bot::run(config).await {
        error!("Bot error: {}", e);
        std::process::exit(1);
    }
}
