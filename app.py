import os
import json


from flask import Flask, render_template, request, jsonify

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


try:
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    exit()

app = Flask(__name__)

# --- Generative AI Model Configuration ---
# Google Search tool is iused for data collection
google_search_tool = types.Tool(google_search=types.GoogleSearch())

# Two models - research_model collects data, structuring_model model generates the final report
# In first case Google Search tool used for data gathering, in second - for grounding.
# Both models are based on gemini-2.5-pro, however gemini-2.5-flash is also not bad
research_model = genai.Client()
research_model_name = "gemini-2.5-pro"
research_config = types.GenerateContentConfig(tools=[google_search_tool])

structuring_model = genai.Client()
structuring_model_name = "gemini-2.5-pro"
structuring_config = types.GenerateContentConfig(
    tools=[google_search_tool],  # response_mime_type="application/json"
)


# --- Flask Routes ---
# Main Page
@app.route("/")
def index():
    return render_template("index.html")


# Handles research request
@app.route("/research", methods=["POST"])
def research():
    if not request.json or "topic" not in request.json:
        return jsonify({"error": "Missing topic"}), 400

    topic = request.json["topic"]
    print(f"Received research request for topic: {topic}")

    try:
        # --- Step 1: Perform Research ---
        research_prompt = f"""
            You are a world-class market research analyst.
            Your task is to conduct a comprehensive market analysis for '{topic}'.
            Use your search capabilities to gather all necessary information to create a multi-section report including:
            - Market Overview
            - Key Trends
            - Competitive Landscape
            - Growth Drivers & Challenges
            - A final summary
            Also, find quantifiable data for at least one chart with 4+ data points (e.g., market size over time).
            Present all your findings as a detailed, unstructured text block.
        """
        print("--- Sending research prompt to Gemini ---")
        research_response = research_model.models.generate_content(
            model=research_model_name,
            contents=research_prompt,
            config=research_config,
        )

        try:
            researched_text = research_response.text
        except ValueError:
            block_reason = (
                research_response.prompt_feedback.block_reason.name
                if research_response.prompt_feedback.block_reason
                else "Unknown"
            )
            error_message = f"The initial research from the model was blocked. Reason: {block_reason}"
            print(error_message)
            return jsonify({"error": error_message}), 500

        # --- Step 2: Structure the Research into JSON ---
        print("--- Sending researched text to be structured into JSON ---")
        structuring_prompt = f"""
            You are a data structuring expert. Based on the following market research text, generate a single, valid JSON object.
            The report must be thorough, insightful, and well-structured.

            ## JSON Output Structure:
            Generate a single, valid JSON object with two top-level keys: "report" and "charts".

            1.  **"report" (array of objects):** An array of objects, where each object represents a section of the report.
                *   Each section object must have a "title" (string) and "content" (string).
                *   The content should be detailed and formatted using Markdown (e.g., using `**` for bold, `*` for italics, and `-` for bullet points). Newline characters (`\n`) will be rendered as paragraph breaks.
                *   The report MUST include the following sections in order:
                    1.  Market Overview
                    2.  Key Trends
                    3.  Competitive Landscape
                    4.  Growth Drivers & Challenges
                    5.  Summary (This MUST be the last section and provide a concise summary of the entire report).

            2.  **"charts" (array of objects):** An array containing at least one relevant chart to visualize key data.
                *   The chart must have at least 4 data points.
                *   Each chart object must have a "title", a "type" ('bar', 'line', 'pie', 'doughnut'), and a "data" object.
                *   The "data" object must contain "labels" (array of strings) and "datasets" (an array of objects, each with a "label" and "data" array of numbers).

            ## Market Research Text to Analyze:
            ---
            {researched_text}
            ---

            ### Example A (shortened content for brevity)
            {{
            "report": [
                {{
                "title": "Market Overview",
                "content": "**Scope:** The EV charging market spans residential, commercial, and fast-charging hubs.\\n**Size & Growth:** Strong double-digit CAGR driven by policy incentives and OEM commitments."
                }},
                {{
                "title": "Key Trends",
                "content": "- **Ultrafast DC** adoption rising in highways.\\n- *Bidirectional (V2G)* pilots increasing.\\n- Software-driven optimization for uptime and load balancing."
                }},
                {{
                "title": "Competitive Landscape",
                "content": "**Leaders:** ChargePoint, Tesla, ABB.\\n**Challengers:** Startups focusing on software, payments, and predictive maintenance."
                }},
                {{
                "title": "Growth Drivers & Challenges",
                "content": "- **Drivers:** Government incentives, falling battery costs, fleet electrification.\\n- **Challenges:** Interoperability, grid constraints, maintenance economics."
                }},
                {{
                "title": "Summary",
                "content": "The market is expanding with policy tailwinds and OEM momentum. Software and reliability differentiate vendors, while grid and interoperability remain execution risks."
                }}
            ],
            "charts": [
                {{
                "title": "Adoption by Segment (Illustrative Share)",
                "type": "bar",
                "data": {{
                    "labels": ["Residential", "Workplace", "Public AC", "Public DC"],
                    "datasets": [
                    {{
                        "label": "Share (%)",
                        "data": [35, 20, 25, 20]
                    }}
                    ]
                }}
                }}
            ]
            }}

            ### Example B (shortened content for brevity)
            {{
            "report": [
                {{
                "title": "Market Overview",
                "content": "**Industrial AI in Oil & Gas** enhances throughput, safety, and OPEX via predictive analytics and edge deployments."
                }},
                {{
                "title": "Key Trends",
                "content": "- *Edge inference* for latency-sensitive control.\\n- **RAG** for ops knowledge.\\n- Cybersecurity-first architectures."
                }},
                {{
                "title": "Competitive Landscape",
                "content": "Mix of hyperscalers, OT vendors, and niche ISVs; partnerships with EPCs and system integrators accelerate delivery."
                }},
                {{
                "title": "Growth Drivers & Challenges",
                "content": "- **Drivers:** Unplanned downtime reduction, emissions reporting, skilled labor gaps.\\n- **Challenges:** Data quality, model governance, brownfield integration."
                }},
                {{
                "title": "Summary",
                "content": "Value accrues to solutions that pair robust data foundations with MLOps and governance, integrated into OT workflows."
                }}
            ],
            "charts": [
                {{
                "title": "Top Use Cases (Share of Mentions)",
                "type": "doughnut",
                "data": {{
                    "labels": ["Predictive Maintenance", "Anomaly Detection", "Energy Optimization", "Quality Inspection"],
                    "datasets": [
                    {{
                        "label": "Share (%)",
                        "data": [40, 25, 20, 15]
                    }}
                    ]
                }}
                }}
            ]
            }}

            Now, using the **Market Research Text** above, generate **only** the final JSON object adhering to the contract.
        """

        json_response_raw = structuring_model.models.generate_content(
            model=structuring_model_name,
            contents=structuring_prompt,
            config=structuring_config,
        )
        json_response = json_response_raw.text
        json_response = json_response.replace("json", "")
        json_response = json_response.replace("```", "")

        # Handle errors from the JSON response
        try:
            return jsonify(json.loads(json_response))
        except ValueError:
            block_reason = (
                json_response_raw.prompt_feedback.block_reason.name
                if json_response_raw.prompt_feedback.block_reason
                else "Unknown"
            )
            error_message = (
                f"The JSON structuring response was blocked. Reason: {block_reason}"
            )
            print(error_message)
            return jsonify({"error": error_message}), 500
        except json.JSONDecodeError:
            error_message = "The model returned a response that was not valid JSON."
            print(error_message)
            print("--- Model's Raw Response ---")
            print(json_response.text)
            print("----------------------------")
            return jsonify({"error": error_message}), 500

    except Exception as e:
        # This catches other API errors, like authentication or network issues.
        print(f"An unexpected error occurred during the API call: {e}")
        error_message = (
            "An API communication error occurred. Please check the server logs."
        )
        if "API key not valid" in str(e):
            error_message = "Invalid Google API Key. Please check your .env file."

        return jsonify({"error": error_message}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
