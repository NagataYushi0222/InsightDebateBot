import os
import sys
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in environment.")
    sys.exit(1)

print(f"--- Environment Info ---")
print(f"Python: {sys.version}")
try:
    import google.genai
    print(f"google-genai location: {os.path.dirname(google.genai.__file__)}")
    # Try to find version if available
    from importlib.metadata import version
    print(f"google-genai version: {version('google-genai')}")
except Exception as e:
    print(f"Could not determine SDK version: {e}")

print(f"\n--- Initializing Client ---")
try:
    client = genai.Client(api_key=api_key)
    print("Client initialized successfully.")
except Exception as e:
    print(f"Client initialization failed: {e}")
    sys.exit(1)

print(f"\n--- Available Models ---")
try:
    # v1.0 SDK style listing
    # Note: list() returns an iterator/generator of Model objects
    models = list(client.models.list())
    print(f"Found {len(models)} models.")
    
    for m in models:
        # Check if it supports generateContent
        supported_methods = m.supported_actions if hasattr(m, 'supported_actions') else []
        if 'generateContent' in str(supported_methods) or not supported_methods:
             print(f"- {m.name} ({m.display_name})")
        else:
             print(f"- {m.name} [No generateContent support]")

except Exception as e:
    print(f"Failed to list models: {e}")

print("\n--- Testing Specific Model Names ---")
test_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest", "gemini-pro-latest"]

for model_name in test_models:
    print(f"Testing {model_name}...", end=" ")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Hello, ignore this."
        )
        print("OK ✅")
    except Exception as e:
        print(f"FAILED ❌ ({e})")
