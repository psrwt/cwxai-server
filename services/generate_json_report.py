import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dotenv import load_dotenv
import os
from openai import AzureOpenAI, RateLimitError, APIError

# --- Configuration ---
load_dotenv()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")

if not all([AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_DEPLOYMENT_NAME]):
    raise ValueError("Azure OpenAI environment variables (API_KEY, ENDPOINT, DEPLOYMENT_NAME) are not set.")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

SYSTEM_ROLE = "You are a startup strategy assistant."

def generate_with_openai(prompt: str, section_name: str, max_tokens: int = 800):
    print(f"   Generating section: {section_name} using OpenAI...")
    start_time = time.time()
    retries = 3
    wait_time = 5
    last_exception = None  # <-- Step 1

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=AZURE_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_ROLE},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
            )
            content = response.choices[0].message.content.strip()
            usage = response.usage
            time_taken = time.time() - start_time

            print(f"   ✓ Section '{section_name}' generated in {time_taken:.2f}s (Attempt {attempt + 1})")
            print(f"      Tokens used — Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens}, Total: {usage.total_tokens}")

            return {
                "content": content,
                "time_taken": time_taken,
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0
            }

        except RateLimitError as rle:
            last_exception = rle  # <-- Step 2
            print(f"   ! Rate limit hit on section '{section_name}' (Attempt {attempt + 1}/{retries}). Retrying in {wait_time}s...")
        except APIError as apie:
            last_exception = apie  # <-- Step 2
            print(f"   ! API error on section '{section_name}' (Attempt {attempt + 1}/{retries}). Retrying in {wait_time}s...")
        except Exception as e:
            last_exception = e  # <-- Step 2
            print(f"   ✗ Unexpected error on section '{section_name}' (Attempt {attempt + 1}): {type(e).__name__} - {str(e)}")

        if attempt < retries - 1:
            time.sleep(wait_time)
            wait_time *= 2
        else:
            time_taken = time.time() - start_time
            return {
                "content": f"### Error Generating Section: {section_name}\n\nAfter {retries} attempts.\n```\n{str(last_exception)}\n```",
                "time_taken": time_taken,
                "input_tokens": 0,
                "output_tokens": 0
            }
            
def extract_possible_json(text):
    """
    Try to extract the first JSON object using a regex (as a last resort fallback).
    """
    match = re.search(r'({.*})', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

# def call_gemini_and_parse_json(prompt, section_name, max_output_tokens=5000):
#     """
#     Calls the Gemini model to generate content for a section, then attempts to parse the output as JSON.
#     Includes cleanup and fallback parsing strategies.
#     """
#     from services.models.gemini_service import generate_with_gemini

#     result = generate_with_gemini(prompt, section_name=section_name, max_output_tokens=max_output_tokens)
#     response_text = result.get("content", "").strip()

#     # Step 1: Clean up ```json blocks or other markdown formatting
#     cleaned_text = re.sub(r"^```(?:json)?\n|\n```$", "", response_text, flags=re.DOTALL).strip()

#     # Step 2: Attempt direct JSON parsing
#     try:
#         return json.loads(cleaned_text)
#     except json.JSONDecodeError:
#         print(f"⚠️ JSONDecodeError in Gemini response for section '{section_name}'. Trying regex fallback...")

#     # Step 3: Try regex-based JSON extraction
#     extracted = extract_possible_json(response_text)
#     if extracted:
#         try:
#             return json.loads(extracted)
#         except json.JSONDecodeError:
#             print(f"❌ Fallback JSON extraction failed for Gemini section '{section_name}'.")

#     # Step 4: Final fallback – return debug info
#     return {
#         "error": f"Failed to parse Gemini response as valid JSON for section '{section_name}'.",
#         "raw_response": response_text,
#         "cleaned_text": cleaned_text,
#         "prompt": prompt[:500] + "...",  # Trimmed prompt for readability
#     }


def call_openai_and_parse_json(prompt, section_name, max_tokens=5000):
    result = generate_with_openai(prompt, section_name=section_name, max_tokens=max_tokens)
    response_text = result.get("content", "").strip()

    # Step 1: Clean markdown-style JSON wrapping like ```json
    cleaned_text = re.sub(r"^```(?:json)?\n|\n```$", "", response_text, flags=re.DOTALL).strip()

    # Step 2: First attempt to parse directly
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        print(f"⚠️ JSONDecodeError in section '{section_name}'. Trying regex fallback...")

    # Step 3: Try to extract JSON using fallback
    extracted = extract_possible_json(response_text)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            print(f"❌ Fallback JSON extraction failed in section '{section_name}'.")

    # Step 4: Final fallback – return error info
    return {
        "error": f"Failed to parse Azure OpenAI response as valid JSON for section '{section_name}'.",
        "raw_response": response_text,
        "cleaned_text": cleaned_text,
        "prompt": prompt[:500] + "...",  # Truncated for brevity
    }


# Dummy functions for testing
def generate_executive_overview(report_content):
    executive_summary = report_content.get("executive_summary", "")
    problem_validation = report_content.get("problem_validation", "")
    market_analysis = report_content.get("market_analysis", "")
    market_size_estimation = report_content.get("market_size_estimation", "")
    industry_insights = report_content.get("industry_insights", "")

    sample_structure = """
    {
  "id": "executive_overview",
  "title": "Executive Overview",
  "subsections": [
    {
      "overview": "[string: 50 to 60 words description about the startup idea]",
      "feasibility_metrics": {
        "metrics": [
          {
            "label": "Market Potential",
            "value": 0,  // int (0–100)
            "icon": "trending-up"
          },
          {
            "label": "Execution Feasibility",
            "value": 0,
            "icon": "gear"
          },
          {
            "label": "Solution Differentiation",
            "value": 0,
            "icon": "light_bulb"
          },
          {
            "label": "Revenue Viability",
            "value": 0,
            "icon": "dollar-sign"
          }
        ],
        "feasibility_score": {
          "label": "Feasibility Score",
          "value": 0,
          "max": 100
        }
      },
      "key_insights": [
        {
          "title": "Market Positioning",
          "content": "[string]"
        },
        {
          "title": "Competitive Edge",
          "content": "[string]"
        },
        {
          "title": "Growth Potential",
          "content": "[string]"
        },
        {
          "title": "Risks & Challenges",
          "content": "[string]"
        }
      ],
      "problem_validation": [
        {
          "title": "Unmet Customer Needs",
          "content": [
            "[string]", "[string]"
          ]
        },
        {
          "title": "Operational Inefficiencies",
          "content": [
            "[string]", "[string]"
          ]
        },
        {
          "title": "Stakeholder Pain Points",
          "content": [
            "[string]", "[string]"
          ]
        },
        {
          "title": "Market Context",
          "content": [
            "[string]", "[string]"
          ]
        }
      ],
      "market_size_estimation": {
        "TAM": {
          "label": "Total Addressable Market (TAM)",
          "value": "[string, e.g., $110 billion or ₹15 crore or any other currency and its scale (just include size in only one currency not more than one meaning do not write anything like this --> ₹5,00,000 crores (USD 60 billion))]",
          "description": "How big is the largest market?",
          "colour": "bg-purple-400"
        },
        "SAM": {
          "label": "Serviceable Available Market (SAM)",
          "value": "[string, e.g., $33 billion]",
          "description": "What kind of portion the market fits you?",
          "colour": "bg-purple-600"
        },
        "SOM": {
          "label": "Serviceable Obtainable Market (SOM)",
          "value": "[string, e.g., $5.5 billion]",
          "description": "What portion of the market are you able to reach?",
          "colour": "bg-purple-800"
        }
      },
      "target_audience": [
        {
          "title": "[string: audience category name]",
          "points": [
            "[string: attribute or need 1]",
            "[string: attribute or need 2]",
            "[string: attribute or need 3]"
          ]
        }
      ],
      "industry_insights": {
        "trends": [
          "[string]", "[string]",...
        ],
        "opportunities": [
          "[string]", "[string]",...
        ],
        "market_size": "[string, e.g., $3.11 billion by 2030 ( for this data just include the market size information only in 5-10 words and the type of information to write is provided in the inline eg. and if the provided content data does not inlucde the infomration of exact market size figures than use your current knowledge and provided data to wirte one)]",
        "growth_drivers": [
          "[string]", "[string]", "[string]", "[string]",...
        ],
        "key_performance_indicators": [
          "[string]", "[string]", "[string]", ....
        ],
        "competitive_edge": [
          "[string]", "[string]"
        ]
      }
    }
  ],
  "sources": {
    "key_insights": [
      "[string: URL]", "[string: URL]"
    ],
    "problem_validation": [
      "[string: URL]", "[string: URL]"
    ],
    "market_size_estimation": [
      "[string: URL]", "[string: URL]"
    ],
    "industry_insights": [
      "[string: URL]", "[string: URL]"
    ]
  }
}
    """

    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "executive_overview" section.

🔒 Strict Format Rules:
- You must **exactly** follow the JSON structure and hierarchy as defined in the sample format.
- Do **not** rename, remove, or add keys. Do not alter nesting or array/object relationships.
- If a section's data is unavailable, **infer it logically** (e.g., feasibility metrics).
- Maintain key order and ensure each expected key exists in the final JSON, even if empty.

📌 Specific Instructions:

1. Use the exact JSON structure provided under "Sample Output Format" for the `executive_overview` section — including all keys like `headline`, `feasibility_metrics`, `key_insights`, `problem_validation`, etc.

2. For the `feasibility_metrics` section, derive four metrics:
   - Market Potential
   - Execution Feasibility
   - Solution Differentiation
   - Revenue Viability
   Also calculate an overall `feasibility_score` (0–100) based on your judgment of the startup idea and content.
   

3. In `market_size_estimation` (TAM, SAM, SOM):
   - Use **only one consistent currency format** across all values (USD, INR or any other).
   - Do **not** include dual currency formats like “₹1500 crore (approx. $180 billion)” or any content in parentheses.
   - Avoid symbols such as `~`, `approx`, or `"approximately"`. Do not include any estimation qualifiers — just clean numbers.
   - Choose a consistent scale unit — example - for INR use `lakhs`, `crores`, for USD use `thousand` ,`millions` or `billions`.
     - ✅ Valid: `₹75,000 crore` or `$9 billion`
     - ❌ Invalid: `₹75,000 crore (approx. $9 billion)` or `~₹75,000 crore`
   - Apply this rule **to all three** values: TAM, SAM, and SOM.


4. In `industry_insights.market_size`:
   - Output only the **short market size figure** (5–10 words max).
   - Do **not** include context or long prose (e.g., avoid sentences like “The Indian industry is growing rapidly”).
   - Example formats: `$3.11 billion by 2030`, `₹5000 crore by 2028`.
   - If no number is in the input, **infer a realistic figure** using your knowledge and the provided data.
   
5. In the `problem_validation` block:

   - The section must include the following **standard categories**, each as an object with a `title` and `content` array:
     - "Unmet Customer Needs"
     - "Operational Inefficiencies"
     - "Stakeholder Pain Points"
     - "Market Context"

   - If the input includes **additional insights** that do not fit neatly into those four categories (e.g., “Localized Statistics”, “Currency Figures”, “Gender-specific Challenges”, “Policy Constraints”), create **new entries** in the `problem_validation` array using their appropriate titles.

   - Do **not** remove or merge unique content — always preserve information by including it in its own logical section.

   - Each object in the `problem_validation` array must have:
     - `"title"`: a short string summarizing the category
     - `"content"`: an array of 1–3 sentence summaries per insight

   - Prioritize relevance and avoid repetition across categories.

   
6. For all major sections (e.g., `key_insights`, `problem_validation`, `market_size_estimation`, `industry_insights`), extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.key_insights`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.
   
7. Maintain clarity, conciseness, and a professional tone in content summaries. Avoid redundancy or excessive elaboration.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
Key Insights and feasiblity metrics data:
{executive_summary}

Problem Validation:
{problem_validation}

# Market Analysis(ignore the competitor analysis data and just use the target audience data):
# {market_analysis}

# Market Size Estimation:
# {market_size_estimation}

# Industry Insights:
# {industry_insights}

Sample Output Format:
{sample_structure}
"""

    return call_openai_and_parse_json(prompt, section_name="Executive Overview")
    # return call_gemini_and_parse_json(prompt, section_name="Executive Overview")


def generate_strategic_insights(report_content):
    swot_analysis = report_content.get("swot_analysis", "")
    vrio_analysis = report_content.get("vrio_analysis", "")
    pestel_analysis = report_content.get("pestel_analysis", "")
    porter_analysis = report_content.get("porters_five_forces", "")
    catwoe_analysis = report_content.get("catwoe_analysis", "")
    
    sample_structure = """
    {
    "id": "strategic_insights",
    "title": "Strategic Insights",
    "subsections": [
        {
            "swot_analysis": {
                "strengths": [
                    "[string]",
                    "[string]"
                ],
                "weaknesses": [
                    "[string]",
                    "[string]"
                ],
                "opportunities": [
                    "[string]",
                    "[string]"
                ],
                "threats": [
                    "[string]",
                    "[string]"
                ]
            },
            "vrio_analysis": {
                "value": "[string]",
                "rarity": "[string]",
                "imitability": "[string]",
                "organization": "[string]"
            },
            "pestel_analysis": {
                "political": "[string]",
                "economic": "[string]",
                "social": "[string]",
                "technological": "[string]",
                "environmental": "[string]",
                "legal": "[string]"
            },
            "porter_analysis": {
                "threat_of_new_entrants": {
                    "title": "1. Threat of New Entrants",
                    "content": "[string]"
                },
                "bargaining_power_of_suppliers": {
                    "title": "2. Bargaining Power of Suppliers",
                    "content": "[string]"
                },
                "bargaining_power_of_buyers": {
                    "title": "3. Bargaining Power of Buyers",
                    "content": "[string]"
                },
                "threat_of_substitutes": {
                    "title": "4. Threat of Substitutes",
                    "content": "[string]"
                },
                "industry_rivalry": {
                    "title": "5. Industry Rivalry",
                    "content": "[string]"
                }
            },
            "catwoe_analysis": {
                "Customers": "[string]",
                "Actors": "[string]",
                "Transformation Process": "[string]",
                "Worldview": "[string]",
                "Owner": "[string]",
                "Environmental Constraints": "[string]"
            }
        }
    ],
    "sources": {
        "swot_analysis": [
            "[string: URL]",
            "[string: URL]"
        ],
        "vrio_analysis": [
            "[string: URL]",
            "[string: URL]"
        ],
        "pestel_analysis": [
            "[string: URL]",
            "[string: URL]"
        ],
        "porter_analysis": [
            "[string: URL]",
            "[string: URL]"
        ],
        "catwoe_analysis": [
            "[string: URL]",
            "[string: URL]"
        ]
    }
}
    """
    
    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "strategic_insights" section.

🔒 Strict Format Rules:
- You must **exactly** follow the JSON structure and hierarchy as defined in the sample format.
- Do **not** rename, remove, or add keys. Do not alter nesting or array/object relationships.
- If a section's data is unavailable, **infer it logically**.
- Maintain key order and ensure each expected key exists in the final JSON, even if empty.

📌 Specific Instructions:
1. Use the exact sample JSON structure  — including all keys like `swot_analysis`, `vrio_analysis`, etc.
3. For all major sections (e.g., `swot_analysis`, `vrio_analysis`, `pestel_analysis`), extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.swot_analysis`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
SWOT analysis:
{swot_analysis}

VRIO analysis:
{vrio_analysis}

PESTEL analysis:
{pestel_analysis}

PORTER analysis:
{porter_analysis}

CATWOE analysis:
{catwoe_analysis}

Sample Output Format:
{sample_structure}
"""

    return call_openai_and_parse_json(prompt, section_name="Strategic Insights")
    # return call_gemini_and_parse_json(prompt, section_name="Strategic Insights")
    

def generate_competitive_landscape(report_content):
    competitor_analysis = report_content.get("competitive_analysis", "")
    market_analysis = report_content.get("market_analysis", "")
    venture_insights = report_content.get("venture_insights", "")
    usp = report_content.get("usp", "")
    
    sample_structure = """
    {
    "id": "competitor_landscape",
    "title": "Competitor Landscape",
    "subsections": [
        {
            "competitor_analysis": {
                "competitors": [
                    {
                        "name": "[string(competitor1 name) eg.MyChart]",
                        "details": [
                            "[string eg.(Market Share: 15%)]",
                            "[stirng eg.Strengths: Established user base, strong integration with healthcare providers, user-friendly interface.]",
                            "[string eg.Weaknesses: Limited analytics features, interoperability issues with non-partnered systems.]",
                            "[string eg.Pricing: Free for users | USD: Free]"
                        ]
                    },
                    {
                        "name": "[string(competitor2 name) eg.Apple Health]",
                        "details": [
                            "[string]",
                            "[string]",
                            "[string]",
                            "[string]"
                        ]
                    }
                ],
                "competitors_comparison_metrics": [
                    {"subject": "[string write metric name eg.User Base]","[string competitor 1 name eg. MyChart]": 0 // int (0–10),"[string competitor 2 name eg. Applehealth]": 0 // int (0–10)},
                    {"subject": "[string write metric name eg.Integration]","[string competitor 1 name eg. MyChart]": 0 // int (0–10),"[string competitor 2 name eg. Applehealth]": 0 // int (0–10)},
                    {"subject": "[string write metric name eg. Cross-Platform]","[string competitor 1 name eg. MyChart]": 0 // int (0–10),"[string competitor 2 name eg. Applehealth]": 0 // int (0–10)},
                    {"subject": "[string write metric name eg. Analytics]","[string competitor 1 name eg. MyChart]": 0 // int (0–10),"[string competitor 2 name eg. Applehealth]": 0 // int (0–10)},
                    {"subject": "[string write metric name eg.UX/UI]","[string competitor 1 name eg. MyChart]": 0 // int (0–10),"[string competitor 2 name eg. Applehealth]": 0 // int (0–10)}
                ],
                "differentiation_strategy": {
                    "title": "Differentiation Strategy",
                    "points": [
                        "[string]",
                        "[string]"
                    ]
                }
            },
            "venture_insights": [
                {
                    "title": "Market Opportunity",
                    "points": [
                        "[string]",
                        "[string]",
                        "[string]"
                    ]
                },
                {
                    "title": "Investment Potential",
                    "points": [
                        "[string]",
                        "[string]",
                        "[string]"
                    ]
                },
                {
                    "title": "Key Success Factors",
                    "points": [
                        "[string]",
                        "[string]",
                        "[string]",
                        "[string]",
                        "[string]"
                    ]
                }
            ],
            "usp": [
                {
                    "title": "Key Differentiators",
                    "points": [
                        "[string]",
                        "[string]"
                    ]
                },
                {
                    "title": "Customer Benefits",
                    "points": [
                        "[string]",
                        "[string]"
                    ]
                },
                {
                    "title": "Value Proposition Statement",
                    "points": [
                        "[string]",
                        "[string]"
                    ]
                },
                {
                    "title": "Competitive Positioning",
                    "points": [
                        "[string]",
                        "[string]",
                        "[string]"
                    ]
                }
            ]
        }
    ],
    "sources": {
        "competitor_analysis": [
            "[string: URL]",
            "[string: URL]"
        ],
        "venture_insights": [
            "[string: URL]",
            "[string: URL]"
        ],
        "usp": [
            "[string: URL]",
            "[string: URL]"
        ]
    }
}
    """
    
    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "competitor_landscape" section.

🔒 Strict Format Rules:
- You must **exactly** follow the JSON structure and hierarchy as defined in the sample format.
- Do **not** rename, remove, or add keys. Do not alter nesting or array/object relationships.
- If a section's data is unavailable, **infer it logically**.
- Maintain key order and ensure each expected key exists in the final JSON, even if empty.

📌 Specific Instructions:
1. Use the exact sample JSON structure  — including all keys like `competitor_analysis`, `venture_insights`, etc.
2. the number of competitor can vary depeding on data that can be one , two or more than two so, accordingly make number of section for each unique competitor under competitor_analysis.competitors
2. to generate the competitors_comparison_metrics use the competitor analysis data and figure out the unique number of competitor( the number of competitor can vary depending of data) and then generate a 5 unique comparison metric for each like user base, integration, analytics etc and then assign 0-10 number of each metric for each competitor and put that in the json 
3. For all major sections (e.g., `competitor_analysis`, `venture_insights`, `usp`), extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.competitor_analysis`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
Competitor analysis:
{competitor_analysis}

this is also the competitor data (just use the competitor analysis data from this and use this data to write for the competitor_analysis section and ignore the target audience data):
{market_analysis}

Venture insights:
{venture_insights}

USP:
{usp}

Sample Output Format:
{sample_structure}
"""

    return call_openai_and_parse_json(prompt, section_name="Competitive Landscape")    
    # return call_gemini_and_parse_json(prompt, section_name="Competitive Landscape")    

def generate_strategy_and_planning(report_content):
    strategy = report_content.get("strategy", "")
    marketing_strategy = report_content.get("marketing_strategy", "")
    social_media_strategy = report_content.get("social_media_strategy", "")
    go_to_market_strategy = report_content.get("go_to_market_strategy", "")
    
    sample_structure = """
    {
    "id": "strategy_and_planning",
    "title": "Strategy & Planning",
    "subsections": [
        {
            "strategy": {
                "title": "Strategy",
                "gridDisplay": true,
                "blocks": [
                    {
                        "label": "Short-Term Goals (1-3 Years)",
                        "items": [
                            {
                                "subtitle": "Customer Growth",
                                "text": "Target 1 million users globally, focusing on patients with chronic conditions and fitness enthusiasts."
                            },
                            {
                                "subtitle": "Revenue Goal",
                                "text": "$50 million in the global market | $40 million in USD."
                            },
                            {
                                "subtitle": "Brand Positioning",
                                "text": "Launch a marketing campaign focusing on data ownership and integration, leveraging influencers."
                            }
                        ]
                    },
                    {
                        "label": "Long-Term Goals (5-10 Years)",
                        "items": [
                            {
                                "subtitle": "Market Expansion",
                                "text": "Enter emerging markets in Asia and Africa, targeting underserved populations."
                            },
                            {
                                "subtitle": "Scalability Plan",
                                "text": "Invest in cloud infrastructure and AI analytics."
                            },
                            {
                                "subtitle": "Projected Revenue",
                                "text": "$500 million in the global market | $400 million in USD."
                            }
                        ]
                    },
                    {
                        "label": "Growth Drivers & Risk Mitigation",
                        "items": [
                            {
                                "subtitle": "Key Growth Driver",
                                "text": "Demand for personalized health solutions amid rising chronic diseases."
                            },
                            {
                                "subtitle": "Risk & Mitigation",
                                "text": "Data privacy concerns; build user trust via security and transparency."
                            }
                        ]
                    },
                    {
                        "label": "Action Plan",
                        "items": [
                            {
                                "subtitle": "Milestone",
                                "text": "500,000 active users by Year 3."
                            },
                            "Develop user-friendly mobile/web apps.",
                            "Conduct user education campaigns.",
                            "Establish partnerships with healthcare providers."
                        ]
                    }
                ]
            },
            "marketing_strategy": {
                "title": "Marketing Strategy",
                "gridDisplay": false,
                "blocks": [
                    {
                        "label": "Positioning, Messaging, and USP",
                        "text": "HealthSync positions itself as a comprehensive platform for health data management, emphasizing ownership, integration, and analytics. The messaging empowers users to control their health data and improve insights."
                    },
                    {
                        "label": "Marketing Channels and Budget",
                        "items": [
                            "Social Media Marketing – 40% – ¥4,000,000 / $30,000",
                            "Content Marketing (Blogs, Webinars) – 30% – ¥3,000,000 / $22,500",
                            "Influencer Partnerships – 20% – ¥2,000,000 / $15,000",
                            "Email Marketing – 10% – ¥1,000,000 / $7,500"
                        ]
                    },
                    {
                        "label": "KPIs and Success Metrics",
                        "items": [
                            {
                                "subtitle": "Brand Awareness",
                                "text": "50% increase in year one"
                            },
                            {
                                "subtitle": "Customer Engagement",
                                "text": "100,000 followers, 20% website conversion"
                            },
                            {
                                "subtitle": "Revenue Growth",
                                "text": "¥10,000,000 / $75,000 in year one"
                            }
                        ]
                    }
                ]
            },
            "social_media_strategy": {
                "title": "Social Media Strategy",
                "gridDisplay": true,
                "blocks": [
                    {
                        "label": "Platform Selection & Content Plan",
                        "items": [
                            {
                                "subtitle": "Instagram",
                                "text": "Visual storytelling for Gen Z/millennials – infographics, success stories, videos"
                            },
                            {
                                "subtitle": "LinkedIn",
                                "text": "B2B content like case studies, industry insights, 2–3 posts/week"
                            },
                            {
                                "subtitle": "WeChat",
                                "text": "Localized content for China – health tips, mini-programs"
                            }
                        ]
                    },
                    {
                        "label": "Content Themes & Engagement Tactics",
                        "items": [
                            {
                                "subtitle": "Theme: Data Empowerment",
                                "text": "Show testimonials, user control over data"
                            },
                            {
                                "subtitle": "Theme: Chronic Disease Management",
                                "text": "Live tips from influencers"
                            }
                        ]
                    },
                    {
                        "label": "Key Performance Indicators (KPIs)",
                        "items": [
                            {
                                "subtitle": "Follower Growth",
                                "text": "10% monthly"
                            },
                            {
                                "subtitle": "Engagement Rate",
                                "text": "5%"
                            },
                            {
                                "subtitle": "Website Traffic from Social",
                                "text": "+20% click-through, 10% conversion"
                            }
                        ]
                    },
                    {
                        "label": "Paid Advertising",
                        "items": [
                            {
                                "subtitle": "Budget",
                                "text": "¥100,000 / $15,000"
                            },
                            {
                                "subtitle": "Expected ROI",
                                "text": "5% conversion, $30 CPA"
                            }
                        ]
                    }
                ]
            },
            "go_to_market_strategy": {
                "title": "Go to Market Strategy",
                "gridDisplay": true,
                "blocks": [
                    {
                        "label": "Market Entry & Launch Plan",
                        "items": [
                            {
                                "subtitle": "Target Market",
                                "text": "Chronic patients, fitness users, caregivers, health-conscious individuals"
                            },
                            {
                                "subtitle": "Phases",
                                "text": "Q1 2024 – R&D, Q2 – Beta, Q3 – Launch, Q4 – Global rollout"
                            }
                        ]
                    },
                    {
                        "label": "Resource Allocation",
                        "items": [
                            {
                                "subtitle": "Marketing Spend",
                                "text": "$5 million"
                            },
                            {
                                "subtitle": "Operational Setup",
                                "text": "$3 million"
                            }
                        ]
                    },
                    {
                        "label": "Distribution & Customer Acquisition",
                        "items": [
                            {
                                "subtitle": "Sales",
                                "text": "Website, healthcare partnerships, app stores"
                            },
                            {
                                "subtitle": "Organic",
                                "text": "SEO, blogs, referral programs"
                            },
                            {
                                "subtitle": "Paid",
                                "text": "Social ads, influencer collaborations, sponsored content"
                            }
                        ]
                    },
                    {
                        "label": "Local Adaptation",
                        "items": [
                            "Localized campaigns for health needs and cultures",
                            "Multilingual support and regional partnerships"
                        ]
                    },
                    {
                        "label": "Key Metrics (KPIs)",
                        "items": [
                            {
                                "subtitle": "CAC",
                                "text": "$50"
                            },
                            {
                                "subtitle": "LTV",
                                "text": "$500 over 5 years"
                            },
                            {
                                "subtitle": "Market Growth",
                                "text": "5% first year → 15% third year"
                            },
                            {
                                "subtitle": "Engagement",
                                "text": "Social metrics, reviews, survey feedback"
                            }
                        ]
                    }
                ]
            }
        }
    ],
    "sources": {
        "strategy": [
            "[string: URL]",
            "[string: URL]"
        ],
        "marketing_strategy": [
            "[string: URL]",
            "[string: URL]"
        ],
        "social_media_strategy": [
           "[string: URL]",
           "[string: URL]"
        ],
        "go_to_market_strategy": [
            "[string: URL]",
            "[string: URL]"
        ]
    }
}
    """
    
    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "strategy_and_planning" section.

🔒 Strict Format Rules:
- You must follow the JSON structure and hierarchy as defined in the sample format.
- If a section's data is unavailable, **infer it logically**.
- Maintain key order and ensure key exists in the final JSON, even if empty.

📌 Specific Instructions:
1. Use the sample JSON structure  — including all keys like `strategy`, `marketing_strategy`, `social_media_strategy` etc.
3. For all major sections (e.g., `strategy`, `marketing_strategy`, `social_media_strategy`), extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.marketing_strategy`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
Strategy:
{strategy}

Marketing Strategy:
{marketing_strategy}

Social meida strategy:
{social_media_strategy}

Go to market strategy:
{go_to_market_strategy}

Sample Output Format:
{sample_structure}
"""
    
    return call_openai_and_parse_json(prompt, section_name="Strategy and Planning")
    # return call_gemini_and_parse_json(prompt, section_name="Strategy and Planning")
    

def generate_product_development(report_content):
    mvp = report_content.get("mvp", "")
    customer_persona = report_content.get("customer_persona", "")
    
    sample_structure = """
    {
    "id": "product_development",
    "title": "Product Development",
    "subsections": [
        {
            "mvp": {
                "core_features": {
                    "title": "Core Features",
                    "features": [
                        {
                            "name": "[ string (feature name) eg.Unified Health Data Dashboard]",
                            "description": "[string (feature detail)"
                        },
                        {
                            "name": "[string (feature name)]",
                            "description": "[string (feature deatil)]"
                        },
                        {
                            "name": "[string (feature name)]",
                            "description": "[string (feature detail)]"
                        }
                    ]
                },
                "target_market_and_testing": {
                    "title": "Target Market and Testing",
                    "primary_users": {
                        "title": "Primary Users",
                        "points": [
                            "[string]",
                            "[string]",
                            "[string]"
                        ]
                    },
                    "early_adopters": {
                        "title": "Early Adopters",
                        "points": [
                            "[string]",
                            "[string]",
                            "[string]"
                        ]
                    },
                    "market_validation_plan": {
                        "title": "Market Validation Plan",
                        "points": [
                            "[string]",
                            "[string]",
                            "[string]"
                        ]
                    }
                },
                "business_model_feasibility": {
                    "title": "Business model & feasibility",
                    "points": [
                        "[string]",
                        "[string]"
                    ]
                },
                "development_timeline": [
                    {
                        "phase": "[string eg.Prototype]",
                        "description": "[string eg.Target completion in 3 months, with key deliverables including a functional app with core features and initial user interface design.]",
                        "label": "Phase 1",
                        "emoji": "🔧"
                    },
                    {
                        "phase": "[string eg.Beta Testing]",
                        "description": "[string]",
                        "label": "Phase 2",
                        "emoji": "🧪"
                    },
                    {
                        "phase": "[string eg.Scaling]",
                        "description": "[string]",
                        "label": "Phase 3",
                        "emoji": "🚀"
                    }
                ],
                "financial_estimates": {
                    "title": "Financial Estimates",
                    "mvp_development_cost": "[string eg.$500,000 — Equivalent in local currencies varies by region.]",
                    "projected_cac": "[string eg.$50/user]",
                    "break_even_timeline": "[string]"
                },
                "potential_risk_challenges": {
                    "title": "Potential Risks & Challenges",
                    "local_risks": [
                        "[string]",
                        "[string]"
                    ],
                    "global_risks": [
                        "[string]",
                        "[string]"
                    ]
                }
            },
            "customer_persona": {
                "name": "[string (persona name) eg.Health-Conscious Hannah]",
                "demographics": {
                    "emoji": "🌍",
                    "ageRange": "[string eg.25-45]",
                    "gender": "[string eg.Female]",
                    "location": "[string]",
                    "incomeLevel": "[string eg.$50,000 - $100,000 USD]",
                    "employmentStatus": "[string eg.Professionals in healthcare, tech, or fitness industries]"
                },
                "sections": [
                    {
                        "title": "Behavioral Patterns & Pain Points",
                        "emoji": "🧠",
                        "groups": [
                            {
                                "label": "Daily Habits",
                                "items": [
                                    "[string]",
                                    "[string]",
                                    "[string]"
                                ]
                            },
                            {
                                "label": "Technology Usage",
                                "items": [
                                    "[string]",
                                    "[string]",
                                    "[string]"
                                ]
                            },
                            {
                                "label": "Key Pain Points",
                                "items": [
                                    "[string]",
                                    "[string]",
                                    "[string]"
                                ]
                            }
                        ]
                    },
                    {
                        "title": "Buying Motivations & Decision Factors",
                        "emoji": "🤔",
                        "groups": [
                            {
                                "label": "Why They Buy",
                                "items": [
                                    "[string]",
                                    "[string]",
                                    "[string]"
                                ]
                            },
                            {
                                "label": "Key Decision Factors",
                                "items": [
                                    "[string]",
                                    "[string]",
                                    "[string]"
                                ]
                            },
                            {
                                "label": "Spending Behavior",
                                "items": [
                                   "[string]",
                                    "[string]"
                                ]
                            }
                        ]
                    },
                    {
                        "title": "Preferred Marketing & Sales Channels",
                        "emoji": "📣",
                        "groups": [
                            {
                                "label": "Most Effective Channels",
                                "items": [
                                    "[string eg.Social media (Instagram, Facebook)]",
                                    "[string eg.Health blogs]",
                                    "[string eg.Email newsletters]"
                                ]
                            },
                            {
                                "label": "Influencers",
                                "items": [
                                    "[string eg.Online reviews]",
                                    "[string]"
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    ],
    "sources": {
        "mvp": [
            "[string: URL]",
            "[string: URL]"
        ],
        "customer_persona": [
            "[string: URL]",
            "[string: URL]"
        ]
    }
}
    """

    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "product_development" section.

🔒 Strict Format Rules:
- You must **exactly** follow the JSON structure and hierarchy as defined in the sample format.
- Do **not** rename, remove, or add keys. Do not alter nesting or array/object relationships.
- If a section's data is unavailable, **infer it logically**.
- Maintain key order and ensure each expected key exists in the final JSON, even if empty.

📌 Specific Instructions:
1. Use the exact sample JSON structure  — including all keys like `mvp`, `customer_persona`, etc.
2. to generate development_timeline use it from the data in MVP and if it is not available then use logical thinkinig to make phased based overall given data
3. For all major sections (e.g., `mvp`, `customer_persona`), extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.competitor_analysis`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
MVP: 
{mvp}

Customer Persona:
{customer_persona}

Sample Output Format:
{sample_structure}
"""

    return call_openai_and_parse_json(prompt, section_name="Product Development")
    # return call_gemini_and_parse_json(prompt, section_name="Product Development")

def generate_financials(report_content):
    finances = report_content.get("finances", "")
    
    sample_structure = """
    {
    "id": "financial_overview",
    "title": "Financial Overview",
    "subsections": [
        {
            "revenue_and_funding": {
                "blocks": [
                    {
                        "top_section": {
                            "title": "Estimated Revenue",
                            "value": "[string eg.$500 million]"
                        },
                        "bottom_section": {
                            "title": "Revenue Streams",
                            "points": [
                                "[string 10-15 words]",
                                "[string]",
                                "[string]"
                            ]
                        }
                    },
                    {
                        "top_section": {
                            "title": "Funding Required",
                            "value": "[string eg.$50 million]"
                        },
                        "bottom_section": {
                            "title": "Potential Funding Strategies",
                            "points": [
                                "[string 10-15 words]",
                                "[string]",
                                "[string]"
                            ]
                        }
                    }
                ]
            },
            "cost_structure": {
                "currency": "[string eg.USD]",
                "scale_unit": "[string eg.millions]",
                "chart_data": [
                    {
                        "name": "Year 1",
                        "revenue": 0,
                        "cost": 0,
                        "profit": 0
                    },
                    {
                        "name": "Year 3",
                        "revenue": 0,
                        "cost": 0,
                        "profit": 0
                    },
                    {
                        "name": "Year 5",
                        "revenue": 0,
                        "cost": 0,
                        "profit": 0
                    }
                ],
                "major_costs": {
                    "points": [
                        "[string 10-15 words]"
                        "[string]"
                        "[string]"
                    ]
                }
            }
        }
    ],
    "sources": {
        "financials": [
            "[string: URL]",
            "[string: URL]"
        ]
    }
}
    """
    
    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "financial_overview" section.

🔒 Strict Format Rules:
- You must **exactly** follow the JSON structure and hierarchy as defined in the sample format.
- Do **not** rename, remove, or add keys. Do not alter nesting or array/object relationships.
- If a section's data is unavailable, **infer it logically based on your understanding of typical startup finances**.
- Maintain key order and ensure each expected key exists in the final JSON, even if inferred.

📌 Specific Instructions:
1. Use the exact sample JSON structure  — including all keys like `cost_structure`, `revenue_and_funding`, etc.

2. In the `cost_structure.chart_data` section:
   - Do **not** insert values like `0` for missing revenue, cost, or profit.
   - Instead, **estimate realistic values** using your domain knowledge about typical startup growth over 1, 3, and 5 years.
   
3. Ensure the `currency` is written using a valid 3-letter code (e.g., `USD`, `INR`, `EUR`) and the `scale_unit` should be either `thousands`, `millions`, or `billions` — **not a mix of both or ambiguous values**.
   - Do **not** write combined scales like `$5000000 million` or `₹15 crore (approx. $1.8 billion)`. Choose **only one consistent scale and currency** throughout.
   - Example accepted format: `currency: USD`, `scale_unit: millions`, `value: $3.5 million`.

4. In `major_costs` and other list-based sections, each point should be concise (10–15 words max).

5. extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.financials`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
Finances data:
{finances}

Sample Output Format:
{sample_structure}
"""
    return call_openai_and_parse_json(prompt, section_name="Finances")
    # return call_gemini_and_parse_json(prompt, section_name="Finances")


def generate_marketing_channel_customer_accquistion(report_content):
    marketing_channels = report_content.get("marketing_channels", "")
    slogan = report_content.get("slogan", "")
    
    sample_structure = """
    {
    "id": "marketing_channels",
    "title": "Marketing Channels & Slogans",
    "subsections": [
        {
            "channels": {
                "headline": "[string 12-20 words]",
                "channel_recommendations": [
                    {
                        "title": "[string eg.Top Channel]",
                        "platform": "[string eg.Google Ads (Globally)]",
                        "roi_ranking": 0 // int 0-5,
                        "strategy": "[string eg.paid]",
                        "best_practices": [
                            "[string 10-15 words]",
                            "[string 10-15 words]"
                        ],
                        "budget": "[string eg.Estimated ad spend of $10,000 (USD)]"
                    },
                    {
                        "title": "[string eg.High-Impact Channel]",
                        "platform": "[string eg.Facebook/Instagram]",
                        "roi_ranking": 0 //int 0-5,
                        "strategy": "[string eg.Paid]",
                        "best_practices": [
                            "[string]",
                            "[string]"
                        ],
                        "budget": ""
                    },
                    {
                        "title": "[string eg.Additional Strong Channel]",
                        "platform": "[string eg.WeChat (China)]",
                        "roi_ranking": 0 //int 0-5, 
                        "strategy": "[string eg.Organic / Paid]",
                        "best_practices": [
                            "[string]",
                            "[string]"
                        ],
                        "budget": "[string]"
                    }
                ]
            },
            "slogans": {
                "headline": "[string eg.Slogan options to align with brand values and mission.]",
                "slogans": [
                    {
                        "text": "[string eg.Empower Your Health, Own Your Data]",
                        "reasoning": "[string]"
                    },
                    {
                        "text": "[string]",
                        "reasoning": "[string]"
                    },
                    {
                        "text": "[string]",
                        "reasoning": "[string]"
                    }
                ]
            }
        }
    ],
    "sources": {
        "channels": [
            "[string: URL]",
            "[string: URL]"
        ],
        "slogans": [
            "[string: URL]",
            "[string: URL]"
        ]
    }
}
    """

    prompt = f"""
You are an expert startup analyst. Based on the startup report data provided below, generate a JSON output for the "marketing_channels" section.

🔒 Strict Format Rules:
- You must **exactly** follow the JSON structure and hierarchy as defined in the sample format.
- Do **not** rename, remove, or add keys. Do not alter nesting or array/object relationships.
- If a section's data is unavailable, **infer it logically**.
- Maintain key order and ensure each expected key exists in the final JSON, even if empty.

📌 Specific Instructions:
1. Use the exact sample JSON structure  — including all keys like `channels`, `slogans`, etc.
2. extract **all source URLs** from the input content and place them in the `sources` block, under the correct key (e.g., `sources.channels` and `sources.slogans`).
   - If a section has no URLs, use an empty list (`[]`) for that section.
   - Do not fabricate or exclude any URLs.

📤 Output Requirements:
- Return only a valid JSON object.
- Do not include any explanation, formatting, or extra text.

Startup Data:
---
Marketing Channels:
{marketing_channels}

Slogans:
{slogan}

Sample Output Format:
{sample_structure}
"""

    return call_openai_and_parse_json(prompt, section_name="Marketing Channels and Slogans")
    # return call_gemini_and_parse_json(prompt, section_name="Marketing Channels and Slogans")
    

# Parallel execution function
def full_json_content_report(report_content):
    report_section_tasks = {
        "executive_overview": generate_executive_overview,
        "strategic_insights": generate_strategic_insights,
        "competitive_landscape": generate_competitive_landscape,
        "strategy_and_planning": generate_strategy_and_planning,
        "product_development": generate_product_development,
        "financials": generate_financials,
        "marketing_channel_customer_accquistion": generate_marketing_channel_customer_accquistion
    }

    report_json_content = {}
    errors = {}

    with ThreadPoolExecutor() as executor:
        future_to_key = {
            executor.submit(func, report_content): key
            for key, func in report_section_tasks.items()
        }

        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                report_json_content[key] = future.result()
            except Exception as e:
                errors[key] = str(e)

    return {
        "report": report_json_content,
        "errors": errors
    }

# Test call
if __name__ == "__main__":
    dummy_input = {"idea": "AI-powered chatbot"}
    output = full_json_content_report(dummy_input)
    print(output)
