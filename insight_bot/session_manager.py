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

    async def start_recording(self, voice_client, channel, api_key=None, initial_message=None):
        self.voice_client = voice_client
        self.target_text_channel = channel
        self.active_sink = UserSpecificSink()
        self.api_key = api_key # Store the key
        self.countdown_message = initial_message
        self.voice_client.start_recording(self.active_sink, self.finished_callback)
        
        # Start periodic task
        self.task = asyncio.create_task(self.process_loop())

    # Removed corrupted block


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
        # Try to get voice client from bot/guild if not tracked in session
        if not self.voice_client:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                self.voice_client = guild.voice_client

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
            remaining_seconds = interval
            
            # Loop for countdown
            while remaining_seconds > 0:
                try:
                    # Determine sleep time (up to 60 seconds)
                    sleep_time = min(60, remaining_seconds)
                    await asyncio.sleep(sleep_time)
                    remaining_seconds -= sleep_time
                    
                    # Edit the countdown message
                    if self.countdown_message and remaining_seconds > 0:
                        try:
                            remaining_minutes = max(1, remaining_seconds // 60)
                            
                            # Keep the original content but update the countdown line
                            # We replace the last line or append if missing
                            content = self.countdown_message.content
                            
                            # Replace the last line using simple substring logic assumes specific format
                            lines = content.split('\n')
                            new_lines = []
                            for line in lines:
                                if "⏳ 次のレポート出力まで:" not in line:
                                    new_lines.append(line)
                                    
                            new_lines.append(f"⏳ 次のレポート出力まで: 約 {remaining_minutes}分")
                            new_content = '\n'.join(new_lines)
                            
                            await self.countdown_message.edit(content=new_content)
                        except discord.NotFound:
                            # Message was probably deleted by a user, ignore
                            self.countdown_message = None
                        except Exception as e:
                            print(f"[{self.guild_id}] Failed to edit countdown message: {e}")
                            
                except asyncio.CancelledError:
                    return

            # Perform the analysis when interval passes
            await self.perform_analysis(is_final=False)
            
            # After analysis, post a new countdown message for the next cycle
            if self.target_text_channel:
                try:
                    interval_mins = interval // 60
                    self.countdown_message = await self.target_text_channel.send(f"⏳ 次のレポート出力まで: 約 {interval_mins}分")
                except Exception as e:
                     print(f"[{self.guild_id}] Failed to send new countdown message: {e}")

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

            # Convert in Executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            user_files_mp3 = {}
            files_to_cleanup = []
            
            for user_id, raw_path in user_files_raw.items():
                # Run ffmpeg conversion in thread
                mp3_path = await loop.run_in_executor(None, convert_to_mp3, raw_path)
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

                        
                        api_key = self.api_key
                        if not api_key:
                            if self.target_text_channel:
                                await self.target_text_channel.send("⚠️ エラー: APIキーが設定されていません。")
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
                     
                     # Notify user about silence or error
                     msg = ""
                     if report.startswith("音声データがありません"):
                         msg = "🎤 音声が検出されませんでした（無音）。"
                     elif report.startswith("⚠️") or report.startswith("❌"):
                         msg = f"⚠️ 分析エラー: {report}"
                     else:
                         msg = "⚠️ 予期せぬエラーでレポートを作成できませんでした。"
                     
                     if self.target_text_channel:
                         await self.target_text_channel.send(msg)
                         
                         # If this was final, ensure we say goodbye even if no report
                         if is_final:
                              await self.target_text_channel.send("🛑 セッションを終了します。")
                     return

                # 2. Create Thread and Post Report
                title_text = f"📅 自動分析 ({timestamp_str})"
                embed_color = discord.Color.blue()
                if is_final:
                    title_text = f"🛑 セッション終了 ({timestamp_str})"
                    embed_color = discord.Color.red()
                
                # レポートのプレビューを作成 (最初の約300文字)
                preview_length = 300
                preview_text = report[:preview_length].strip()
                if len(report) > preview_length:
                    preview_text += "...\n\n"
                
                embed = discord.Embed(
                    title=title_text,
                    description=f"{preview_text}\n*(全文はスレッドを開いてご確認ください)*",
                    color=embed_color
                )

                if self.target_text_channel:
                    starter_msg = await self.target_text_channel.send(embed=embed)
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
