import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# GEMINI_API_KEY is now per-user, managed via /set_apikey
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') 
GUILD_ID = os.getenv('GUILD_ID')

# Audio settings
RECORDING_INTERVAL = 300  
SAMPLE_RATE = 48000
CHANNELS = 2

# Models
GEMINI_MODEL_FLASH = "gemini-3-flash-preview"
GEMINI_MODEL_PRO = "gemini-3-pro-preview"
GEMINI_MODEL_DEFAULT = GEMINI_MODEL_FLASH

# Paths
TEMP_AUDIO_DIR = "temp_audio"
