import os
from flask import Flask, request, jsonify
import openai
import requests

app = Flask(__name__)

# Set up OpenAI API Key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Set up SerpAPI Key from environment variable
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

TARGET_WEBSITES = [
    "pcpartpicker.com",
    "tomshardware.com",
    "videocardbenchmark.net",
    "cpubenchmark.net"
]

def search_with_serpapi(query):
    results = []
    for site in TARGET_WEBSITES:
        formatted_query = f"{query} site:{site}"
        params = {
            "q": formatted_query,
            "engine": "google",
            "api_key": SERPAPI_KEY,
        }
        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error fetching data from SerpAPI for site {site}: {e}")
            continue

        for result in data.get("organic_results", []):
            title = result.get("title", "No title available")
            snippet = result.get("snippet", "No snippet available")
            link = result.get("link", "No link available")
            results.append({"title": title, "snippet": snippet, "link": link})

    app.logger.info(f"Search completed with {len(results)} results.")
    return results

def filter_results_with_gpt(google_results, user_query):
    formatted_results = "\n".join(
        [f"Title: {result['title']}\nSnippet: {result['snippet']}\nLink: {result['link']}" for result in google_results[:10]]
    )

    prompt = (
        f"The user asked: '{user_query}'\n\n"
        f"Here are the search results:\n{formatted_results}\n\n"
        "Based on these results, extract the most relevant information and provide a summary of the components needed for the user's PC build."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert PC-building assistant."},
                {"role": "user", "content": prompt},
            ]
        )
        filtered_response = response.choices[0].message["content"].strip()
    except openai.error.OpenAIError as e:
        app.logger.error(f"OpenAI API error: {e}")
        filtered_response = "An error occurred while processing your request."

    return filtered_response

def generate_pc_build(filtered_requirements, user_query):
    prompt = (
        f"The user wants to build a PC.\n\n"
        f"Original Query: {user_query}\n\n"
        f"Filtered Requirements: {filtered_requirements}\n\n"
        "Using the filtered requirements, recommend a detailed PC build. Include part names, approximate prices, and reasons for each choice. Ensure the total budget is reasonable."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a PC-building expert assistant."},
                {"role": "user", "content": prompt},
            ]
        )
        pc_build = response["choices"][0]["message"]["content"].strip()
    except openai.error.OpenAIError as e:
        app.logger.error(f"OpenAI API error: {e}")
        pc_build = "An error occurred while generating your PC build recommendation."

    return pc_build

@app.route('/api/build-pc', methods=['POST'])
def build_pc_api():
    data = request.get_json()
    if not data or 'query' not in data:
        app.logger.warning("Missing 'query' parameter.")
        return jsonify({"error": "Missing 'query' parameter."}), 400
    try:
        result, status_code = call_flask_app(data)
        app.logger.info("Successfully processed build PC request.")
        return jsonify(result), status_code
    except Exception as e:
        app.logger.error(f"Error processing build PC request: {e}")
        return jsonify({"error": "Internal server error."}), 500

def call_flask_app(data):
    user_query = data.get('query', '').strip()
    if not user_query:
        return {"error": "The 'query' parameter cannot be empty."}, 400

    google_results = search_with_serpapi(user_query)
    if not google_results:
        return {"error": "No search results found."}, 404

    filtered_requirements = filter_results_with_gpt(google_results, user_query)
    if not filtered_requirements:
        return {"error": "Failed to filter requirements."}, 500

    pc_build = generate_pc_build(filtered_requirements, user_query)
    if not pc_build:
        return {"error": "Failed to generate PC build recommendation."}, 500

    return {"pc_build": pc_build}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False') == 'True'
    app.run(host='0.0.0.0', port=port, debug=debug)
