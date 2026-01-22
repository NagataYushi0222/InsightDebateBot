from google import genai
import inspect

client = genai.Client(api_key="TEST")
print(inspect.signature(client.files.upload))
