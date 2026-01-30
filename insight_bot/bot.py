import discord
from discord.ext import commands
import os
import sys
import webbrowser
import requests
import google.generativeai as genai
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
        genai.configure(api_key=key)
        # Try listing models to verify key
        list(genai.list_models())
        return True
    except:
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
    opus_filename = "libopus.dll" if os.name == 'nt' else "libopus.dylib"
    bundled_opus = resource_path(opus_filename)
    if os.path.exists(bundled_opus):
         try:
             discord.opus.load_opus(bundled_opus)
             print(f"Loaded bundled opus from {bundled_opus}")
         except Exception as e:
             print(f"Failed to load bundled opus: {e}")
    else:
        try:
             if os.name != 'nt':
                discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
             else:
                discord.opus.load_opus("libopus-0.dll")
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
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

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

@bot.slash_command(name="analyze_stop", description="分析を終了し、ボイスチャットから退出します")
async def analyze_stop(ctx):
    session = session_manager.get_session(ctx.guild.id)
    
    if session.voice_client and session.voice_client.is_connected():
        await ctx.respond("🔄 最終レポートを作成して終了します。しばらくお待ちください...")
        await session.stop_recording()
        # Clean up session from manager
        await session_manager.cleanup_session(ctx.guild.id)
        await ctx.followup.send("✅ 分析を終了しました。お疲れ様でした！")
    else:
        await ctx.respond("分析は実行されていません。", ephemeral=True)

def run_bot():
    token = setup_credentials()
    if token:
        bot.run(token)
    else:
        print("No token provided. Exiting.")

if __name__ == "__main__":
    run_bot()
