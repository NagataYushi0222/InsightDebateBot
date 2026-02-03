//! Analyze commands: /analyze_start, /analyze_stop, /analyze_now

use serenity::all::{
    CommandInteraction, Context, CreateCommand, CreateInteractionResponse,
    CreateInteractionResponseMessage, EditInteractionResponse, CreateMessage,
};
use std::sync::Arc;
use tracing::info;

use crate::session::SessionManager;

/// Register analyze commands
pub fn register() -> Vec<CreateCommand> {
    vec![
        CreateCommand::new("analyze_start")
            .description("ボイスチャットの分析を開始します"),
        CreateCommand::new("analyze_stop")
            .description("分析を終了し、ボイスチャットから退出します"),
        CreateCommand::new("analyze_now")
            .description("すぐにレポートを作成します（分析間隔を待たずに実行）"),
    ]
}

/// Handle /analyze_start command
pub async fn handle_start(
    ctx: &Context,
    command: &CommandInteraction,
    session_manager: Arc<SessionManager>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let guild_id = command.guild_id.ok_or("Must be used in a guild")?;
    
    // Get user's voice channel from guild cache
    let voice_channel_id = {
        let guild = ctx.cache.guild(guild_id).ok_or("Guild not in cache")?;
        guild
            .voice_states
            .get(&command.user.id)
            .and_then(|vs| vs.channel_id)
            .ok_or("ボイスチャットに参加してからコマンドを実行してください。")?
    };

    // Check if already recording
    if session_manager.get_session(guild_id).is_some() {
        respond(ctx, command, "既に分析を実行中です。").await?;
        return Ok(());
    }

    // Defer response
    command.defer(&ctx.http).await?;

    // Get songbird manager
    let manager = songbird::get(ctx).await.ok_or("Songbird not registered")?;

    // Join voice channel
    let call = manager.join(guild_id, voice_channel_id).await?;

    // Create session
    let _session = session_manager.create_session(guild_id, command.channel_id, call).await?;
    
    // Start analysis loop
    session_manager.start_analysis_loop(guild_id, ctx.http.clone());

    // Get channel name for response
    let channel_name = ctx.cache.channel(voice_channel_id)
        .map(|c| c.name.clone())
        .unwrap_or_else(|| "Unknown".to_string());

    let response = EditInteractionResponse::new()
        .content(format!(
            "{} の分析を開始しました。プライバシー保護のため、録音・分析が行われることを参加者に周知してください。",
            channel_name
        ));
    command.edit_response(&ctx.http, response).await?;

    info!("Started recording in guild {} channel {}", guild_id, voice_channel_id);
    Ok(())
}

/// Handle /analyze_stop command
pub async fn handle_stop(
    ctx: &Context,
    command: &CommandInteraction,
    session_manager: Arc<SessionManager>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let guild_id = command.guild_id.ok_or("Must be used in a guild")?;

    // Check if recording
    if session_manager.get_session(guild_id).is_none() {
        respond(ctx, command, "分析は実行されていません。").await?;
        return Ok(());
    }

    respond(ctx, command, "🔄 最終レポートを作成して終了します。しばらくお待ちください...").await?;

    // Cleanup session (runs final analysis)
    session_manager.cleanup_session(guild_id, ctx.http.clone()).await?;

    // Leave voice channel
    let manager = songbird::get(ctx).await.ok_or("Songbird not registered")?;
    let _ = manager.leave(guild_id).await;

    let msg = CreateMessage::new().content("✅ 分析を終了しました。お疲れ様でした！");
    command.channel_id.send_message(&ctx.http, msg).await?;

    info!("Stopped recording in guild {}", guild_id);
    Ok(())
}

/// Handle /analyze_now command
pub async fn handle_now(
    ctx: &Context,
    command: &CommandInteraction,
    session_manager: Arc<SessionManager>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let guild_id = command.guild_id.ok_or("Must be used in a guild")?;

    // Check if recording
    if session_manager.get_session(guild_id).is_none() {
        respond(ctx, command, "分析は実行されていません。先に /analyze_start を実行してください。").await?;
        return Ok(());
    }

    respond(ctx, command, "🔄 手動分析を開始しました...").await?;

    // Force analysis
    if let Err(e) = session_manager.force_analysis(guild_id, ctx.http.clone()).await {
        let msg = CreateMessage::new().content(format!("⚠️ エラー: {}", e));
        command.channel_id.send_message(&ctx.http, msg).await?;
    }

    Ok(())
}

/// Helper to send a response
async fn respond(
    ctx: &Context,
    command: &CommandInteraction,
    content: &str,
) -> Result<(), serenity::Error> {
    command.create_response(&ctx.http, CreateInteractionResponse::Message(
        CreateInteractionResponseMessage::new().content(content)
    )).await
}
