from pydub import AudioSegment
import os
import glob
from .config import TEMP_AUDIO_DIR

def convert_to_mp3(file_path):
    """
    Converts a file (WAV or PCM) to MP3 using pydub.
    Returns the path to the new MP3 file.
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        if file_path.endswith(".pcm"):
            # Import AudioSegment inside function if strictly needed, but it's at top level
            # Discord PCM is s16le, 48k, 2ch
            with open(file_path, 'rb') as f:
                pcm_data = f.read()
            sound = AudioSegment(
                data=pcm_data,
                sample_width=2, # 16 bit
                frame_rate=48000,
                channels=2
            )
        else:
            sound = AudioSegment.from_wav(file_path)
            
        mp3_path = file_path.rsplit('.', 1)[0] + ".mp3"
        sound.export(mp3_path, format="mp3")
        return mp3_path
    except Exception as e:
        print(f"Error converting {file_path}: {e}")
        return None

def cleanup_files(file_paths):
    """
    Removes the specified files.
    """
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error removing {path}: {e}")

def get_audio_info(file_path):
    """
    Returns duration in seconds.
    """
    if not os.path.exists(file_path):
        return 0
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except:
        return 0
