import discord
import time
import os
from .config import TEMP_AUDIO_DIR

class UserSpecificSink(discord.sinks.Sink):
    """
    Records raw PCM audio for each user separately.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timestamp = int(time.time())
        if not os.path.exists(TEMP_AUDIO_DIR):
            os.makedirs(TEMP_AUDIO_DIR)

    def write(self, user, data):
        # Print a dot for every packet to show activity in terminal
        print(f".", end="", flush=True)
        # The base Sink.write method appends the data (which is raw PCM) to self.audio_data[user_id]
        super().write(user, data)

    def write_user_audio(self, user_id, audio_data):
        pass

    def get_user_audio(self, user_id):
        return self.audio_data.get(user_id)

    async def flush_audio(self):
        """
        Saves current buffer to disk and clears it to free memory.
        Returns a map of {user_id: file_path}.
        Saves as .pcm (raw signed 16-bit little-endian, 48k stereo).
        """
        saved_files = {}
        # Use a list of keys to avoid runtime modification issues during iteration
        # simple iteration over keys() is fine if we use pop with default or standard logic
        user_ids = list(self.audio_data.keys())
        
        for user_id in user_ids:
            # Atomic-ish pop. The recv thread might re-create this entry immediately if a packet arrives,
            # which is fine (that's the next chunk).
            if user_id in self.audio_data:
                audio = self.audio_data.pop(user_id)
            else:
                continue

            # audio is an AudioData object (which wraps BytesIO in .file)
            if hasattr(audio, 'file'):
                 audio_file = audio.file
            else:
                 audio_file = audio

            # Check if there's data
            try:
                if audio_file.getbuffer().nbytes > 0:
                    filename = f"{TEMP_AUDIO_DIR}/{self.timestamp}_{user_id}_{int(time.time())}.pcm"
                    with open(filename, "wb") as f:
                        f.write(audio_file.getbuffer())
                    saved_files[user_id] = filename
            except Exception as e:
                print(f"Error saving audio for user {user_id}: {e}")
        
        return saved_files
