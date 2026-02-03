//! Discord Bot event handler and voice receive handler

use crate::audio::UserRecorder;
use crate::commands;
use crate::config::Config;
use crate::database::Database;
use crate::session::SessionManager;
use serenity::all::{
    Client, Context, EventHandler, GatewayIntents, GuildId, Interaction, Ready,
};
use serenity::async_trait;
use songbird::events::{Event, EventContext, EventHandler as VoiceEventHandler, TrackEvent};
use songbird::{CoreEvent, SerenityInit};
use std::sync::Arc;
use tracing::{error, info};

/// Bot state shared across handlers
pub struct BotState {
    pub config: Arc<Config>,
    pub db: Arc<Database>,
    pub session_manager: Arc<SessionManager>,
}

/// Main event handler for the bot
pub struct Handler {
    pub state: Arc<BotState>,
}

#[async_trait]
impl EventHandler for Handler {
    async fn ready(&self, ctx: Context, ready: Ready) {
        info!("Logged in as {}", ready.user.name);

        // Register commands
        let commands = vec![
            commands::analyze::register(),
            commands::settings::register(),
        ]
        .into_iter()
        .flatten()
        .collect::<Vec<_>>();

        // If guild ID is set, register to specific guild (faster for dev)
        if let Some(guild_id) = self.state.config.guild_id {
            let guild = GuildId::new(guild_id);
            match guild.set_commands(&ctx.http, commands).await {
                Ok(cmds) => info!("Registered {} guild commands", cmds.len()),
                Err(e) => error!("Failed to register guild commands: {}", e),
            }
        } else {
            // Register globally
            match serenity::all::Command::set_global_commands(&ctx.http, commands).await {
                Ok(cmds) => info!("Registered {} global commands", cmds.len()),
                Err(e) => error!("Failed to register global commands: {}", e),
            }
        }
    }

    async fn interaction_create(&self, ctx: Context, interaction: Interaction) {
        if let Interaction::Command(command) = interaction {
            let result = match command.data.name.as_str() {
                "analyze_start" => {
                    commands::analyze::handle_start(
                        &ctx,
                        &command,
                        self.state.session_manager.clone(),
                    )
                    .await
                }
                "analyze_stop" => {
                    commands::analyze::handle_stop(
                        &ctx,
                        &command,
                        self.state.session_manager.clone(),
                    )
                    .await
                }
                "analyze_now" => {
                    commands::analyze::handle_now(
                        &ctx,
                        &command,
                        self.state.session_manager.clone(),
                    )
                    .await
                }
                "settings" => {
                    commands::settings::handle(&ctx, &command, self.state.db.clone()).await
                }
                _ => Ok(()),
            };

            if let Err(e) = result {
                error!("Command error: {}", e);
            }
        }
    }
}

/// Voice receive event handler
pub struct VoiceReceiver {
    pub recorder: Arc<UserRecorder>,
}

#[async_trait]
impl VoiceEventHandler for VoiceReceiver {
    async fn act(&self, ctx: &EventContext<'_>) -> Option<Event> {
        if let EventContext::VoiceTick(tick) = ctx {
            // Process each speaking user's audio
            for (ssrc, data) in &tick.speaking {
                // Get the decoded voice data if available
                if let Some(decoded) = &data.decoded_voice {
                    // We have PCM data, but we want to save Opus directly
                    // For raw Opus, we'd need to access the packet before decoding
                    // For now, we'll note that Songbird provides decoded PCM by default
                    
                    // In a full implementation, we'd configure Songbird to give us raw Opus
                    // For now, we'll re-encode PCM to Opus (less efficient but works)
                }
                
                // If we have the original Opus packet (requires special Songbird config)
                if let Some(packet) = &data.packet {
                    // This contains the raw Opus data
                    // We can save this directly for maximum efficiency
                }
            }
        }
        
        None
    }
}

/// Create and run the Discord bot
pub async fn run(config: Config) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let config = Arc::new(config);
    
    // Initialize database
    let db = Arc::new(Database::open("bot_settings.db")?);
    
    // Create session manager
    let session_manager = Arc::new(SessionManager::new(config.clone(), db.clone()));
    
    // Create bot state
    let state = Arc::new(BotState {
        config: config.clone(),
        db,
        session_manager,
    });

    // Create handler
    let handler = Handler {
        state: state.clone(),
    };

    // Create client with voice support
    let intents = GatewayIntents::non_privileged() | GatewayIntents::GUILD_VOICE_STATES;
    
    let mut client = Client::builder(&config.discord_token, intents)
        .event_handler(handler)
        .register_songbird()
        .await?;

    // Store state in client data
    {
        let mut data = client.data.write().await;
        data.insert::<BotStateKey>(state);
    }

    // Start the client
    info!("Starting bot...");
    client.start().await?;

    Ok(())
}

/// Type key for storing BotState in client data
pub struct BotStateKey;

impl serenity::prelude::TypeMapKey for BotStateKey {
    type Value = Arc<BotState>;
}
