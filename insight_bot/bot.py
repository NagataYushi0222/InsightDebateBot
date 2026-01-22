import discord
from discord.ext import commands
import os
from .config import DISCORD_TOKEN, GUILD_ID
from .database import init_db, update_guild_setting, get_guild_settings
from .session_manager import SessionManager

import sys
import tkinter as tk
from tkinter import simpledialog, messagebox

# Initialize Database
init_db()

intents = discord.Intents.default()
intents.voice_states = True

# Resource Path Helper
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

import webbrowser

def get_discord_token():
    # 1. Try Environment Variable
    token = DISCORD_TOKEN
    
    # 2. Try Local File (token.txt)
    if not token and os.path.exists("token.txt"):
        with open("token.txt", "r") as f:
            token = f.read().strip()
            
    # 3. Prompt User (Custom GUI)
    if not token:
        try:
            # Create a custom setup window
            root = tk.Tk()
            root.title("InsightDebateBot - Initial Setup")
            
            # Center window
            window_width = 500
            window_height = 350
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            center_x = int(screen_width/2 - window_width/2)
            center_y = int(screen_height/2 - window_height/2)
            root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
            
            token_var = tk.StringVar()
            
            def open_portal():
                webbrowser.open("https://discord.com/developers/applications")
                
            def open_guide():
                # Replace with your actual guide URL if available
                webbrowser.open("https://github.com/osadayuushi/InsightDebateBot/blob/main/SELF_HOSTING_GUIDE.md")

            def save_and_start():
                input_token = token_var.get().strip()
                if not input_token:
                    messagebox.showerror("Error", "トークンが入力されていません。")
                    return
                
                with open("token.txt", "w") as f:
                    f.write(input_token)
                
                messagebox.showinfo("Success", "設定完了！アプリを起動します。")
                root.destroy()

            # UI Elements
            tk.Label(root, text="InsightDebateBot へようこそ！", font=("Helvetica", 16, "bold")).pack(pady=10)
            
            intro_text = (
                "このアプリを利用するには、あなた自身のDiscord Botを作成し、\n"
                "その「Bot Token」を入力する必要があります。\n\n"
                "サーバー代はかかりません。無料で利用できます。"
            )
            tk.Label(root, text=intro_text, justify="center").pack(pady=5)
            
            # Buttons Frame
            btn_frame = tk.Frame(root)
            btn_frame.pack(pady=10)
            
            tk.Button(btn_frame, text="1. 作り方を見る (ガイド)", command=open_guide, bg="#e0e0e0").pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="2. Developer Portalを開く", command=open_portal, bg="#5865F2", fg="white").pack(side=tk.LEFT, padx=5)
            
            # Input
            tk.Label(root, text="Bot Tokenを貼り付けてください:", font=("Helvetica", 10, "bold")).pack(pady=(15, 5))
            entry = tk.Entry(root, textvariable=token_var, width=50)
            entry.pack(pady=5)
            
            # Submit
            tk.Button(root, text="保存して起動", command=save_and_start, bg="#43B581", fg="white", font=("Helvetica", 12, "bold")).pack(pady=20)
            
            # Main Loop
            root.mainloop()
            
            # Retrieve token after window closes
            if os.path.exists("token.txt"):
                with open("token.txt", "r") as f:
                    token = f.read().strip()
            
        except Exception as e:
            print(f"GUI Error: {e}")
            token = input("GUI Failed. Please enter your Discord Bot Token: ")
            if token:
                with open("token.txt", "w") as f:
                    f.write(token.strip())
    
    return token

# Load Opus
if not discord.opus.is_loaded():
    # Try local bundle first (for PyInstaller)
    bundled_opus = resource_path("libopus.dylib")
    if os.path.exists(bundled_opus):
         try:
             discord.opus.load_opus(bundled_opus)
             print(f"Loaded bundled opus from {bundled_opus}")
         except Exception as e:
             print(f"Failed to load bundled opus: {e}")
    else:
        # Fallback to system env
        try:
            discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
        except Exception as e:
            print(f"Could not load opus from default path: {e}")

# If you want Global Commands for public release, remove debug_guilds or make it None.
# For now, we keep it if GUILD_ID is set for testing, but typically for public bot you pass None.
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
            print("Synced commands (no list returned).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# --- Settings Commands ---
settings_group = bot.create_group("settings", "Botの設定を変更します")

@settings_group.command(name="set_key", description="Gemini APIキーを設定します（BYOK）")
async def set_key(ctx, key: str):
    # Security note: In a real public bot, you might want to validate the key first.
    update_guild_setting(ctx.guild.id, 'api_key', key)
    await ctx.respond("✅ APIキーを更新しました。次回分析からこのキーが使用されます。", ephemeral=True)

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

@bot.slash_command(name="analyze_stop", description="分析を終了し、ボイスチャットから退出します")
async def analyze_stop(ctx):
    session = session_manager.get_session(ctx.guild.id)
    
    if session.voice_client and session.voice_client.is_connected():
        await session.stop_recording()
        # Clean up session from manager
        await session_manager.cleanup_session(ctx.guild.id)
        await ctx.respond("分析を終了しました。")
    else:
        await ctx.respond("分析は実行されていません。", ephemeral=True)

def run_bot():
    token = get_discord_token()
    if token:
        bot.run(token)
    else:
        print("No token provided. Exiting.")

if __name__ == "__main__":
    run_bot()
