import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GUILD_ID = os.getenv('GUILD_ID')

# Audio settings
RECORDING_INTERVAL = 300  
SAMPLE_RATE = 48000
CHANNELS = 2

# Models
GEMINI_MODEL_FLASH = "gemini-2.0-flash"
GEMINI_MODEL_PRO = "gemini-2.0-pro"

# Paths
TEMP_AUDIO_DIR = "temp_audio"
