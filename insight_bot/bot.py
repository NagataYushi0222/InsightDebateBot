import discord
from discord.ext import commands
import os
import sys
import webbrowser
import requests
import google.genai as genai_sdk # Rename to avoid conflict if any, though actually it's a module
from google import genai

from .config import DISCORD_TOKEN, GUILD_ID
from .database import init_db, update_guild_setting, get_guild_settings
from .session_manager import SessionManager

# Initialize Database
init_db()

intents = discord.Intents.default()
intents.voice_states = True

# Resource Path Helper
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        else:
            return os.path.join(os.path.dirname(sys.executable), relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def validate_discord_token(token):
    headers = {"Authorization": f"Bot {token}"}
    try:
        response = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
        return response.status_code == 200
    except:
        return False

def validate_gemini_key(key):
    try:
        client = genai.Client(api_key=key)
        # Try listing models to verify key (fetching first page is enough)
        # The new SDK returns an iterator/generator
        next(client.models.list(), None) 
        return True
    except:
        # In case next() fails because list is empty (unlikely) or auth fails
        return False

def setup_credentials():
    # 1. Try Environment Variables (from .env or system)
    token = os.getenv("DISCORD_TOKEN") or DISCORD_TOKEN
    api_key = os.getenv("GEMINI_API_KEY")

    # If both exist and appear valid-ish (basic check), skip setup
    if token and api_key:
        return token

    # 2. CLI Setup (Unified for App/Docker)
    print("Credentials not found. Launching setup...")
    print("GUI is disabled to ensure consistent behavior with Docker.")
    
    while True:
        print("\n=== InsightDebateBot Setup ===")
        print("Please enter your credentials.")
        
        i_token = input("Discord Bot Token: ").strip()
        if not i_token: continue
        
        if not validate_discord_token(i_token):
            print("❌ Invalid Discord Token. Please try again.")
            continue
            
        i_key = input("Gemini API Key: ").strip()
        if not i_key: continue
        
        if not validate_gemini_key(i_key):
            print("❌ Invalid Gemini API Key. Please try again.")
            continue
        
        # Save
        with open(".env", "w") as f:
            f.write(f"DISCORD_TOKEN={i_token}\n")
            f.write(f"GEMINI_API_KEY={i_key}\n")
        
        os.environ["DISCORD_TOKEN"] = i_token
        os.environ["GEMINI_API_KEY"] = i_key
        print("✅ Credentials saved to .env. Starting bot...")
        return i_token

# Load Opus
if not discord.opus.is_loaded():
    opus_filename = ""
    match sys.platform:
        case "win32":
            opus_filename = "libopus.dll"
        case "darwin":
            opus_filename = "libopus.dylib"
        case "linux":
            opus_filename = "libopus.so"

    bundled_opus = resource_path(opus_filename)
    if os.path.exists(bundled_opus):
        try:
            discord.opus.load_opus(bundled_opus)
            print(f"Loaded bundled opus from {bundled_opus}")
        except Exception as e:
            print(f"Failed to load bundled opus: {e}")
    else:
        try:
            if sys.platform == 'darwin':
                discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
            elif sys.platform == 'win32':
                discord.opus.load_opus("libopus-0.dll")
            elif sys.platform == 'linux':
                import ctypes.util

                lib_name = "opus"
                lib_path = ctypes.util.find_library(lib_name)
                if lib_path:
                    discord.opus.load_opus(lib_path)
                else:
                    print("Could not find opus library using ctypes.util.find_library")
        except Exception as e:
            print(f"Could not load opus from default path: {e}")

debug_guilds = [int(GUILD_ID)] if GUILD_ID else None
bot = commands.Bot(command_prefix='/', intents=intents, debug_guilds=debug_guilds)
session_manager = SessionManager(bot)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.sync_commands()
        if synced:
            print(f"Synced {len(synced)} commands.")
        else:
            print("Synced commands (global).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    """Auto-stop when all users leave the voice channel (only bot remains)."""
    # Only care about users leaving a channel
    if before.channel is None:
        return
    
    # Check if the bot is in the channel the user left
    session = session_manager.get_session(member.guild.id)
    if not session.voice_client or not session.voice_client.is_connected():
        return
    
    if session.voice_client.channel != before.channel:
        return
    
    # Count non-bot members remaining in the channel
    remaining_members = [m for m in before.channel.members if not m.bot]
    
    if len(remaining_members) == 0:
        print(f"[{member.guild.id}] All users left voice channel. Auto-stopping...")
        if session.target_text_channel:
            await session.target_text_channel.send("👋 全員がボイスチャンネルから退出したため、自動的に分析を終了しました。")
        await session_manager.cleanup_session(member.guild.id, skip_final=True)

# --- Settings Commands ---
settings_group = bot.create_group("settings", "Botの設定を変更します")

@settings_group.command(name="set_mode", description="分析モードを変更します (debate / summary)")
async def set_mode(ctx, mode: str):
    if mode not in ['debate', 'summary']:
        await ctx.respond("❌ モードは 'debate' または 'summary' を指定してください。", ephemeral=True)
        return
    update_guild_setting(ctx.guild.id, 'analysis_mode', mode)
    await ctx.respond(f"✅ 分析モードを '{mode}' に変更しました。")

@settings_group.command(name="set_interval", description="分析間隔（秒）を変更します")
async def set_interval(ctx, seconds: int):
    # Minimum 60 seconds to prevent abuse
    if seconds < 60:
         await ctx.respond("❌ 間隔は最短60秒です。", ephemeral=True)
         return
    update_guild_setting(ctx.guild.id, 'recording_interval', seconds)
    await ctx.respond(f"✅ 分析間隔を {seconds}秒 ({seconds/60:.1f}分) に変更しました。")

# --- Analysis Commands ---

@bot.slash_command(name="analyze_start", description="ボイスチャットの分析を開始します")
async def analyze_start(ctx):
    voice_state = ctx.author.voice
    if not voice_state or not voice_state.channel:
        await ctx.respond("ボイスチャットに参加してからコマンドを実行してください。", ephemeral=True)
        return

    await ctx.defer()
    
    # Get Session
    session = session_manager.get_session(ctx.guild.id)
    
    # Check if already recording
    if session.voice_client and session.voice_client.recording:
         await ctx.followup.send("既に分析を実行中です。")
         return

    # Join Voice Channel
    try:
        channel = voice_state.channel
        voice_client = await channel.connect()
        await ctx.respond(f"{channel.name} の分析を開始しました。プライバシー保護のため、録音・分析が行われることを参加者に周知してください。")
        
        # Start Recording via Session
        await session.start_recording(voice_client, ctx.channel)
            
    except Exception as e:
        # Cleanup if connection failed
        if session.voice_client:
             await session.stop_recording()
        await ctx.followup.send(f"エラーが発生しました: {e}")

@bot.slash_command(name="analyze_now", description="すぐにレポートを作成します（分析間隔を待たずに実行）")
async def analyze_now(ctx):
    session = session_manager.get_session(ctx.guild.id)
    
    if session.voice_client and session.voice_client.is_connected():
        await ctx.respond("🔄 手動分析を開始しました...")
        await session.force_analysis()
    else:
        await ctx.respond("分析は実行されていません。先に /analyze_start を実行してください。", ephemeral=True)

@bot.slash_command(name="analyze_stop", description="分析を終了します（最終レポートなし）")
async def analyze_stop(ctx):
    await ctx.defer()
    session = session_manager.get_session(ctx.guild.id)
    
    if session.active_sink:
        await session_manager.cleanup_session(ctx.guild.id, skip_final=True)
        await ctx.followup.send("✅ 分析を終了しました。お疲れ様でした！")
    else:
        await ctx.followup.send("分析は実行されていません。")

@bot.slash_command(name="analyze_stop_final", description="最終レポートを作成してから分析を終了します")
async def analyze_stop_final(ctx):
    await ctx.defer()
    session = session_manager.get_session(ctx.guild.id)
    
    if session.active_sink:
        await ctx.followup.send("🔄 最終レポートを作成して終了します。しばらくお待ちください...")
        await session_manager.cleanup_session(ctx.guild.id, skip_final=False)
        await ctx.followup.send("✅ 最終レポートを作成し、分析を終了しました。お疲れ様でした！")
    else:
        await ctx.followup.send("分析は実行されていません。")

def run_bot():
    token = setup_credentials()
    if token:
        bot.run(token)
    else:
        print("No token provided. Exiting.")

if __name__ == "__main__":
    run_bot()
