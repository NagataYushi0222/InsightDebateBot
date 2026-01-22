from google import genai
import os
from dotenv import load_dotenv

load_dotenv("insight_bot/.env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Listing models via google-genai SDK...")
try:
    # Pager object, iterate to get models
    for model in client.models.list():
        print(model.name)
except Exception as e:
    print(f"Error listing models: {e}")
