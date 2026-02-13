import os
from google import genai
from google.genai import types

# Use a dummy file for testing upload (or just check attributes if possible)
# But better to just check the method signatures via introspection if we don't want to burn quota

print("Checking google.genai version...")
try:
    import google.genai
    print(f"google.genai imported successfully.")
except ImportError:
    print("google.genai not found.")
    exit(1)

client = genai.Client(api_key="TEST_KEY")

print(f"Client initialized: {client}")
print(f"Has files.upload: {hasattr(client.files, 'upload')}")
print(f"Has models.generate_content: {hasattr(client.models, 'generate_content')}")

# Check help/docstring for arguments
print("\n--- files.upload help ---")
help(client.files.upload)

print("\n--- models.generate_content help ---")
help(client.models.generate_content)
