import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv("insight_bot/.env")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model_name = "gemini-1.5-flash-latest" # or gemini-flash-latest

print(f"Testing model: {model_name}")

# Attempt 1: String (Failed)
# tools = "google_search" 

# Attempt 2: Tool Object
try:
    print("Attempting with Tool object...")
    # This structure depends on the exact SDK version, probing common paths
    tool = genai.protos.Tool(
        google_search = genai.protos.GoogleSearch()
    )
    model = genai.GenerativeModel(model_name, tools=[tool])
    print("Model initialized with Tool object.")
    
    # Try a simple generation to see if it accepts it
    # We won't actually run it to save quota/time, just initialization, 
    # but the error might happen at generate_content time.
    # So let's try a dry run.
    print("Generating content...")
    response = model.generate_content("What is the latest news about Python?")
    print("Success!")
    print(response.text[:100])
except Exception as e:
    print(f"Attempt 2 Failed: {e}")

# Attempt 3: Config Dict
try:
    print("\nAttempting with Config Dict...")
    tools = [{'google_search': {}}]
    model = genai.GenerativeModel(model_name, tools=tools)
    print("Model initialized with Config Dict.")
    response = model.generate_content("What is the latest news about Python?")
    print("Success!")
    print(response.text[:100])
except Exception as e:
    print(f"Attempt 3 Failed: {e}")
