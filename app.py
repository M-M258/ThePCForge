from flask import Flask, request, jsonify
import json
import openai
import requests
import os

# Initialize Flask app
app = Flask(__name__)

# Set up OpenAI and SerpAPI Keys (loaded from environment variables)
openai.api_key = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

# Pages to scrape for components
SCRAPING_PAGES = {
    "cpu": "https://pcpartpicker.com/products/cpu/",
    "cpu-cooler": "https://pcpartpicker.com/products/cpu-cooler/",
    "motherboard": "https://pcpartpicker.com/products/motherboard/",
    "memory": "https://pcpartpicker.com/products/memory/",
    "internal-hard-drive": "https://pcpartpicker.com/products/internal-hard-drive/",
    "video-card": "https://pcpartpicker.com/products/video-card/",
    "power-supply": "https://pcpartpicker.com/products/power-supply/",
    "case": "https://pcpartpicker.com/products/case/"
}

def search_with_serpapi(query):
    """
    Use SerpAPI to search for results based on GPT-identified requirements.
    """
    results = []
    for category, site in SCRAPING_PAGES.items():
        # Append category-specific query
        formatted_query = f"{query} site:{site}"
        params = {
            "q": formatted_query,
            "engine": "google",
            "api_key": SERPAPI_KEY,
        }
        response = requests.get("https://serpapi.com/search", params=params)
        if response.status_code != 200:
            continue
        data = response.json()

        # Extract top organic results
        for result in data.get("organic_results", []):
            title = result.get("title", "No title available")
            snippet = result.get("snippet", "No snippet available")
            link = result.get("link", "No link available")
            results.append({"category": category, "title": title, "snippet": snippet, "link": link})

    return results

def filter_results_with_gpt(google_results, user_query):
    """
    Use GPT to analyze and filter search results for relevance.
    """
    # Format the search results for GPT
    formatted_results = "\n".join(
        [f"Category: {result['category']}\nTitle: {result['title']}\nSnippet: {result['snippet']}\nLink: {result['link']}" for result in google_results]
    )

    # GPT Prompt
    prompt = (
        f"The user asked: '{user_query}'\n\n"
        f"Here are the search results:\n{formatted_results}\n\n"
        "Based on these results, extract the most relevant information and provide a summary of the components needed for the user's PC build."
    )

    # Call GPT API
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert PC-building assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    # Extract GPT response
    filtered_response = response.choices[0].message["content"].strip()
    return filtered_response

def generate_pc_build(filtered_requirements, user_query):
    """
    Use GPT to recommend a PC build based on the filtered requirements.
    """
    prompt = (
        f"The user wants to build a PC.\n\n"
        f"Original Query: {user_query}\n\n"
        f"Filtered Requirements: {filtered_requirements}\n\n"
        "Using the filtered requirements, recommend a detailed PC build. Include part names, approximate prices, and reasons for each choice. Ensure the total budget is reasonable."
    )

    # Call GPT API
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a PC-building expert assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    # Extract GPT response
    pc_build = response["choices"][0]["message"]["content"].strip()
    return pc_build

@app.route('/api/build-pc', methods=['POST'])
def build_pc_api():
    data = request.json
    result = call_flask_app(data)
    return jsonify(result)

def call_flask_app(data):
    user_query = data.get('query', '')

    # Step 1: Use GPT to determine requirements based on the user query
    requirements_prompt = (
        f"The user wants to build a PC based on the following input: '{user_query}'.\n"
        "Extract the key component requirements (e.g., high-end GPU, mid-range CPU, etc.) needed for the PC."
    )
    gpt_response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a PC component requirements extraction assistant."},
            {"role": "user", "content": requirements_prompt},
        ]
    )
    extracted_requirements = gpt_response["choices"][0]["message"]["content"].strip()

    # Step 2: Search for components matching the requirements
    google_results = search_with_serpapi(extracted_requirements)

    # Step 3: Filter results using GPT
    filtered_requirements = filter_results_with_gpt(google_results, user_query)

    # Step 4: Generate the PC build
    pc_build = generate_pc_build(filtered_requirements, user_query)

    return {"pc_build": pc_build}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
