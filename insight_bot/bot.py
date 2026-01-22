import discord
from discord.ext import commands, tasks
import os
import asyncio
from .config import DISCORD_TOKEN, RECORDING_INTERVAL, GUILD_ID
from .recorder import UserSpecificSink
from .audio_processor import convert_to_mp3, cleanup_files
from .analyzer import analyze_discussion

intents = discord.Intents.default()
intents.voice_states = True

# Load Opus
if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
    except Exception as e:
        print(f"Could not load opus from default path: {e}")

debug_guilds = [int(GUILD_ID)] if GUILD_ID else None
bot = commands.Bot(command_prefix='/', intents=intents, debug_guilds=debug_guilds)

# State management
current_voice_client = None
active_sink = None
processing_task = None
last_context = ""
target_text_channel = None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.sync_commands()
        if synced is not None:
            print(f"Synced {len(synced)} commands: {[c.name for c in synced]}")
        else:
            print("Synced commands (no list returned).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.slash_command(name="analyze_start", description="ボイスチャットの分析を開始します")
async def analyze_start(ctx):
    global current_voice_client, active_sink, processing_task, target_text_channel, last_context
    
    voice_state = ctx.author.voice
    if not voice_state or not voice_state.channel:
        await ctx.respond("ボイスチャットに参加してからコマンドを実行してください。", ephemeral=True)
        return

    await ctx.defer()
    
    target_text_channel = ctx.channel
    last_context = "" # Reset context

    # Join Voice Channel
    try:
        channel = voice_state.channel
        current_voice_client = await channel.connect()
        await ctx.respond(f"{channel.name} の分析を開始しました。プライバシー保護のため、録音・分析が行われることを参加者に周知してください。")
        
        # Start Recording
        active_sink = UserSpecificSink()
        current_voice_client.start_recording(active_sink, finished_callback)
        
        # Start Periodic Analysis Task
        if not process_loop.is_running():
            process_loop.start()
            
    except Exception as e:
        await ctx.followup.send(f"エラーが発生しました: {e}")

@bot.slash_command(name="analyze_stop", description="分析を終了し、ボイスチャットから退出します")
async def analyze_stop(ctx):
    global current_voice_client
    
    if current_voice_client and current_voice_client.is_connected():
        current_voice_client.stop_recording()
        await current_voice_client.disconnect()
        current_voice_client = None
        if process_loop.is_running():
            process_loop.stop()
        await ctx.respond("分析を終了しました。")
    else:
        await ctx.respond("分析は実行されていません。", ephemeral=True)

async def finished_callback(sink, channel: discord.TextChannel, *args):
    # This is called when stop_recording is called.
    # We can do a final cleanup or final analysis here.
    # For now, we rely on the periodic loop.
    pass

@tasks.loop(seconds=RECORDING_INTERVAL)
async def process_loop():
    global active_sink, last_context, target_text_channel, current_voice_client
    
    if not active_sink or not target_text_channel or not current_voice_client or not current_voice_client.recording:
        return

    print("Starting periodic analysis...")
    
    # 1. Flush Audio
    # Note: We need to handle this carefully. Discord runs in an event loop.
    # Writing to file is blocking IO, but we do it quickly.
    
    try:
        # Flush the buffer (get files and clear memory)
        # We need to map user IDs to names for the analyzer
        user_files_raw = await active_sink.flush_audio()
        
        if not user_files_raw:
            print("No audio data recorded in this interval.")
            # Even if no audio, check if we need to clean up old context or something?
            # But here we just return
            return

        # 2. Get User Map
        user_map = {}
        try:
            guild = current_voice_client.guild
        except:
            guild = None

        for user_id in user_files_raw.keys():
            member = None
            # Try getting from guild (for nickname)
            if guild:
                member = guild.get_member(user_id)
            
            # Try getting from bot cache
            if not member:
                member = bot.get_user(user_id)
            
            # If still not found, try fetch (async)
            if not member:
                try:
                    member = await bot.fetch_user(user_id)
                except:
                    pass

            if member:
                # Prefer display_name (nickname) -> global_name -> name
                user_map[user_id] = member.display_name
            else:
                user_map[user_id] = f"User_{user_id}"

        # 3. Convert to MP3
        user_files_mp3 = {}
        files_to_cleanup = []
        
        for user_id, raw_path in user_files_raw.items():
            mp3_path = convert_to_mp3(raw_path)
            if mp3_path:
                user_files_mp3[user_id] = mp3_path
                files_to_cleanup.append(raw_path)
                files_to_cleanup.append(mp3_path)
        
        if not user_files_mp3:
            cleanup_files(files_to_cleanup)
        # 4. Analyze
        import datetime
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        thread_name = f"議論分析レポート {timestamp_str}"
        
        try:
            # Create a starter message first
            starter_message = await target_text_channel.send(f"📅 **議論分析を開始します** ({timestamp_str})")
            # Create public thread from message
            report_thread = await starter_message.create_thread(name=thread_name, auto_archive_duration=60)
            
            await report_thread.send("🔄 音声ファイルをアップロードし、Geminiで分析中...")
            
            # Run blocking analysis in executor
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(None, analyze_discussion, user_files_mp3, last_context, user_map)
            
            # 5. Post Report (Split if too long)
            header = f"📊 **議論分析レポート**\n"
            if len(report) + len(header) < 2000:
                await report_thread.send(header + report)
            else:
                await report_thread.send(header)
                # Split
                for i in range(0, len(report), 1900):
                    await report_thread.send(report[i:i+1900])

        except Exception as e:
            print(f"Failed to create thread or send report: {e}")
            if target_text_channel:
                 await target_text_channel.send(f"⚠️ 分析処理またはスレッド作成中にエラー: {e}")
        
        # 6. Update Context
        # We keep the summary as context for the next turn. 
        # Ideally, the analyzer returns the summary separately, but for now we use the whole report.
        # To avoid context window explosion, we might trim it or just keep the "Summary" section.
        last_context = report[-2000:] # Simple truncation for now

        # 7. Cleanup
        cleanup_files(files_to_cleanup)

    except Exception as e:
        print(f"Error in process_loop: {e}")
        if target_text_channel:
            await target_text_channel.send(f"⚠️ 分析処理中にエラーが発生しました: {e}")

@process_loop.before_loop
async def before_process_loop():
    await bot.wait_until_ready()
    # Wait for the first interval to pass
    await asyncio.sleep(RECORDING_INTERVAL)

def run_bot():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    run_bot()
