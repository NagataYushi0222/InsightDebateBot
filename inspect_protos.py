import google.generativeai as genai
import textwrap

print("Available attributes in genai.protos:")
attrs = [a for a in dir(genai.protos) if "Search" in a or "Tool" in a]
print(attrs)

# Check Tool class definition if possible (or just attributes)
# We want to see if it takes google_search or google_search_retrieval
