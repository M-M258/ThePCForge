from flask import Flask, request, jsonify
from flask_cors import CORS 
import json
import openai
import requests
import os
import re

# Initialize Flask app
app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# Set up OpenAI and SerpAPI Keys (loaded from environment variables)
openai.api_key = "openAPI KEY"
SERPAPI_KEY = "SERPAPI KEY"

# Global conversation with a single system message
# keep at most 4 total messages in 'conversation'
conversation = [
    {
        "role": "system",
        "content": "You are an expert PC-building assistant."
    }
]

def enforce_conversation_limit():
    """
    Ensures the conversation doesn't exceed 4 total messages.
    Index 0 is always the system message; we allow 3 more.
    """
    global conversation
    while len(conversation) > 4:
        conversation.pop(1)  # remove the oldest after the system message

# Specific websites to focus searches on
TARGET_WEBSITES = [
    "https://www.google.com/"
    "https://pcpartpicker.com/products"
]

def search_with_serpapi(query):
    """
    Use SerpAPI to search for results focused on specific websites.
    Use serpapi to get latest information for 2025
    """
    results = []
    for site in TARGET_WEBSITES:
        formatted_query = f"{query} site:{site}"
        params = {
            "q": formatted_query,
            "engine": "google",
            "api_key": SERPAPI_KEY,
        }
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()

        # Extract top organic results
        for result in data.get("organic_results", []):
            title = result.get("title", "No title available")
            snippet = result.get("snippet", "No snippet available")
            link = result.get("link", "No link available")
            results.append({"title": title, "snippet": snippet, "link": link})

    return results

def filter_results_with_gpt(google_results, user_query):
    """
    Use GPT to analyze and filter search results for relevance.
    """
    formatted_results = "\n".join(
        [f"Title: {r['title']}\nSnippet: {r['snippet']}\nLink: {r['link']}" for r in google_results]
    )

    prompt = (
        f"The user asked: '{user_query}'\n\n"
        f"Here are the search results:\n{formatted_results}\n\n"
        "Please have a heading  stating the users question and saying something like 'heres your answer'"
        "Please provide the filtered requirements and PC build as plain text with no special formatting (e.g., no bold text, no markdown). but keep the response clean and simple, but detailed. Do not include any aesthetic features"
        "Based on these results, extract the most relevant information. "
            "RULES FOR YOU (the assistant):\n"
            " 1. Ignore any link or snippet that does NOT reference a 2024 Q4 or 2025 product, "
                "such as NVIDIA RTX 50 series, AMD Radeon RX 8000 series, Intel Arrow Lake, "
                "or AMD Ryzen 9000 CPUs. Discard all content about RTX 30 series, Ryzen 7000, etc.\n"
                "2. If a results title or snippet contains a calendar year earlier than 2024, skip it.\n"
                "3. Keep at most the top 5 matches that satisfy rule 1.\n"
                "and provide a summary of the components needed for the user's PC build."
                "4. After filtering, build a **short bullet list** describing the *type* of part needed "
                "(High end CPU, Mid range GPU, DDR5-6400 RAM, Gen5 SSD, etc.) and a one sentence reason.\n"
        "Dont include dates on searches"
        "Ensure Information gathered and used is correct EG 7th gen + Ryzen can only use DDR5 memory"
        "Ensure there are always two blank lines between each section for readability.\n"
    )

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert PC-building assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    filtered_response = response.choices[0].message.content.strip()
    return filtered_response

def generate_pc_build(filtered_requirements, user_query):
    """
    Use GPT to recommend a PC build based on the filtered requirements.
    """
    prompt = (
        f"The user wants to build a PC.\n\n"
        f"Original Query: {user_query}\n\n"
        f"Filtered Requirements: {filtered_requirements}\n\n"
        "Output ONLY the PC build in plain text. No markdown, no bold, no special symbols.\n"
        "List the eight headers EXACTLY in this order:\n"
        "Processor (CPU), Graphics Card (GPU), Motherboard, Memory (RAM), Storage, "
        "Power Supply (PSU), Case, Cooling\n\n"
        "For each header, output **exactly two lines**:\n"
        "  1) A single bullet with the pattern:  - <Model>  -  £<Price>\n"
        "  2) A one‑sentence justification, indented by two spaces.\n"
        "Leave one blank line AFTER the justification before the next header starts.\n\n"
        "Keep sentences short (≈15 words) and avoid technical jargon.\n"
        "Do not prepend anything like 'PC Build:' — just start with the first header.\n"
        "No dates, no approximate symbols; prices use £ and whole numbers (e.g., £420).\n"
        "Make sure the total cost is reasonable for the user’s query.\n"
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a PC-building expert assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    pc_build = response.choices[0].message.content.strip()
    return pc_build

def is_pc_query(query):
    """
    Returns True if the user query looks like it's about PC-building or hardware,
    based on simple keyword matching.
    """
    kws = ["pc", "computer", "hardware", "build"]
    q = query.lower()
    return any(kw in q for kw in kws)

@app.route('/api/build-pc', methods=['POST'])
def build_pc_api():
    data = request.json or {}
    user_query = data.get('query', '').strip()

    # ERROR HANDLING: ensure the question is about PC/hardware
    if not re.search(r"\b(pc|computer|hardware|build)\b", user_query, re.IGNORECASE):
        return jsonify({
            "error": "Your question doesn’t seem to be about PC building or hardware. "
                     "Please ask about PC builds, components, or computer hardware."
        }), 400

    result = call_flask_app(data)
    return jsonify(result)

def call_flask_app(data):
    global conversation
    
    user_query = data.get('query', '')
    
    # 1) Append user message to conversation, enforce limit
    conversation.append({"role": "user", "content": user_query})
    enforce_conversation_limit()

    # 2) Here  the SerpAPI + GPT logic (single-turn approach).
    google_results = search_with_serpapi(user_query)
    filtered_requirements = filter_results_with_gpt(google_results, user_query)
    pc_build = generate_pc_build(filtered_requirements, user_query)

    # 3) Save final answer as assistant message, enforce limit again
    full_reply = f"Filtered Requirements:\n{filtered_requirements}\n\nPC Build:\n{pc_build}"
    conversation.append({"role": "assistant", "content": full_reply})
    enforce_conversation_limit()

   # return the combined text.  return everything:
    return {"pc_build": pc_build, "filtered_requirements": filtered_requirements}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
