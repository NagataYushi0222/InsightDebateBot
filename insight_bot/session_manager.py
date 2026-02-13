import os
import asyncio
from typing import Dict, Optional
import discord
from discord.ext import tasks
from .recorder import UserSpecificSink
from .audio_processor import convert_to_mp3, cleanup_files
from .analyzer import analyze_discussion
from .database import get_guild_settings

class GuildSession:
    def __init__(self, guild_id: int, bot):
        self.guild_id = guild_id
        self.bot = bot
        self.voice_client: Optional[discord.VoiceClient] = None
        self.active_sink: Optional[UserSpecificSink] = None
        self.target_text_channel: Optional[discord.TextChannel] = None
        self.last_context = ""
        self.task: Optional[asyncio.Task] = None
        self.settings = get_guild_settings(guild_id)

    async def start_recording(self, voice_client, channel):
        self.voice_client = voice_client
        self.target_text_channel = channel
        self.active_sink = UserSpecificSink()
        self.voice_client.start_recording(self.active_sink, self.finished_callback)
        
        # Start periodic task
        self.task = asyncio.create_task(self.process_loop())

    async def stop_recording(self, skip_final=False):
        # 1. Cancel periodic task first to prevent double execution
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        # 2. Perform Final Analysis (unless skipped)
        if not skip_final and self.voice_client and self.voice_client.is_connected() and self.active_sink:
            if self.target_text_channel:
                 await self.target_text_channel.send("🔄 終了前の最終分析を行っています...しばらくお待ちください。")
            await self.perform_analysis(is_final=True)

        # 3. Stop recording and disconnect
        if self.voice_client:
            if self.voice_client.recording:
                self.voice_client.stop_recording()
            if self.voice_client.is_connected():
                await self.voice_client.disconnect()
        
        self.voice_client = None
        self.active_sink = None

    async def finished_callback(self, sink, *args):
        # Ensure any remaining audio is flushed (best effort)
        try:
             await sink.flush_audio()
        except:
             pass

    async def process_loop(self):
        await self.bot.wait_until_ready()
        
        while True:
            # Dynamic interval from settings
            self.settings = get_guild_settings(self.guild_id)
            interval = self.settings.get('recording_interval', 300)
            
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

            await self.perform_analysis(is_final=False)

    async def force_analysis(self):
        """Manually trigger an analysis right now."""
        # Simple implementation: just run perform_analysis.
        # This acts independently of the periodic loop.
        await self.perform_analysis(is_final=False)

    async def perform_analysis(self, is_final=False):
        """
        Manual/Periodic analysis trigger.
        is_final: If True, indicates this is the last analysis before stop.
        """
        if not self.active_sink or not self.voice_client or not self.voice_client.recording:
            return

        print(f"[{self.guild_id}] Starting analysis (Final: {is_final})...")
        
        try:
            user_files_raw = await self.active_sink.flush_audio()
            
            if not user_files_raw:
                if is_final:
                    print(f"[{self.guild_id}] No audio to analyze for final report.")
                return

            # User Mapping
            user_map = {}
            try:
                guild = self.voice_client.guild
            except:
                guild = None 
            
            for user_id in user_files_raw.keys():
                member = None
                if guild:
                    member = guild.get_member(user_id)
                
                if not member:
                    member = self.bot.get_user(user_id)
                if not member:
                    try:
                        member = await self.bot.fetch_user(user_id)
                    except:
                        pass
                
                if member:
                    user_map[user_id] = member.display_name
                else:
                    user_map[user_id] = f"User_{user_id}"

            # Convert
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
                return

            # Thread Setup
            import datetime
            # JST is UTC+9
            jst_delta = datetime.timedelta(hours=9)
            now_jst = datetime.datetime.now(datetime.timezone.utc) + jst_delta
            timestamp_str = now_jst.strftime("%Y-%m-%d %H:%M")
            
            if is_final:
                thread_name = f"議論分析レポート (最終) {timestamp_str}"
                header_prefix = "🏁 **最終分析レポート**"
            else:
                thread_name = f"議論分析レポート {timestamp_str}"
                header_prefix = "📊 **議論分析レポート**"
            
            try:
                # 1. Analyze first (Heavy processing)
                if self.target_text_channel:
                    # Optional: Typing indicator in the main channel while analyzing
                    async with self.target_text_channel.typing():
                        loop = asyncio.get_running_loop()
                        
                        api_key = os.getenv("GEMINI_API_KEY")
                        if not api_key:
                            if self.target_text_channel:
                                await self.target_text_channel.send("⚠️ エラー: APIキーが設定されていません。起動設定を確認してください。")
                            return
                        
                        report = await loop.run_in_executor(
                            None, 
                            analyze_discussion, 
                            user_files_mp3, 
                            self.last_context, 
                            user_map,
                            api_key,
                            self.settings['analysis_mode']
                        )
                
                # Check for analysis errors or empty results
                if not report or report.startswith("⚠️") or report.startswith("音声データがありません") or report.startswith("❌"):
                     print(f"[{self.guild_id}] Analysis skipped or failed: {report}")
                     # Optionally notify if it's a critical error, but for "no audio" just skip
                     return

                # 2. Create Thread and Post Report
                starter_msg_text = f"📅 **自動分析** ({timestamp_str})"
                if is_final:
                    starter_msg_text = f"🛑 **セッション終了** ({timestamp_str})"

                if self.target_text_channel:
                    starter_msg = await self.target_text_channel.send(starter_msg_text)
                    report_thread = await starter_msg.create_thread(name=thread_name, auto_archive_duration=60)
                    
                    # Update Context
                    self.last_context = report[-2000:]

                    # Post Report
                    header = f"{header_prefix}\n"
                    if len(report) + len(header) < 2000:
                        await report_thread.send(header + report)
                    else:
                        await report_thread.send(header)
                        for i in range(0, len(report), 1900):
                            await report_thread.send(report[i:i+1900])
                        
            except Exception as e:
                print(f"[{self.guild_id}] Error in reporting: {e}")
                if self.target_text_channel:
                        await self.target_text_channel.send(f"⚠️ エラー: {e}")
            
            finally:
                cleanup_files(files_to_cleanup)

        except Exception as e:
             print(f"[{self.guild_id}] Error in perform_analysis: {e}")

class SessionManager:
    def __init__(self, bot):
        self.bot = bot
        self.sessions: Dict[int, GuildSession] = {}

    def get_session(self, guild_id: int) -> GuildSession:
        if guild_id not in self.sessions:
            self.sessions[guild_id] = GuildSession(guild_id, self.bot)
        return self.sessions[guild_id]

    async def cleanup_session(self, guild_id: int, skip_final=False):
        if guild_id in self.sessions:
            await self.sessions[guild_id].stop_recording(skip_final=skip_final)
            del self.sessions[guild_id]
