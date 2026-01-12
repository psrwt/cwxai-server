import concurrent.futures
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import time
import re
import datetime # Not explicitly used now, but can be useful for filenames etc.
from services.rag_service import RAGService
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


# --- LLM-based Currency Helper ---
def get_currency_via_llm(location_name: str) -> str:
    """
    Determines the 3-letter ISO currency code for a given location using an LLM call.
    Defaults to "USD" if undetermined.
    """
    print(f"   Attempting to determine currency for location: {location_name} via LLM...")
    prompt = f"""What is the 3-letter ISO 4217 currency code for the primary official currency of "{location_name}"?
Respond with ONLY the 3-letter code (e.g., USD, EUR, JPY).
If you are uncertain or the location is fictional, respond with "USD".
Do not include any other text, explanation, or punctuation.
Example for 'Germany': EUR
Example for 'Tokyo, Japan': JPY
Example for 'United States': USD"""

    try:
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides 3-letter ISO currency codes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        currency_code = response.choices[0].message.content.strip().upper()
        
        if re.fullmatch(r"^[A-Z]{3}$", currency_code):
            print(f"   ✓ LLM determined currency for '{location_name}': {currency_code}")
            return currency_code
        else:
            print(f"   ! LLM response for currency ('{currency_code}') not a valid 3-letter code. Defaulting to USD for '{location_name}'.")
            return "USD"
    except Exception as e:
        print(f"   ! Error calling LLM for currency detection for '{location_name}': {e}. Defaulting to USD.")
        return "USD"


# --- Context Unifier: Overall Summary Generation ---
def generate_overall_context_summary(idea: str, location: str, rag_service: RAGService) -> str:
    """
    Generates an overall context summary using the RAG service.
    The summary itself should be concise (max 150 words).
    Individual points within the summary should be 1-2 sentences (20-30 words).
    """
    prompt = f"""
Generate a concise (target 2-3 paragraphs, maximum 150 words) overall context summary in PLAIN TEXT (NO MARKDOWN formatting) for a business report about the idea: '{idea}' in the location: '{location}'.

This summary should briefly outline:
1.  The core business concept and its primary objective (1-2 sentences, ~20-30 words).
2.  The main problem it aims to solve for the target audience in {location} (1 sentence, ~20-30 words).
3.  The key solution or value proposition offered (1 sentence, ~20-30 words).
4.  The primary target market segment in {location} (1 sentence, ~20-30 words).

Keep the language very clear, simple, direct, and strategic. Focus on the essence. Do NOT use any Markdown formatting.
This summary will be used as a preamble for generating other detailed sections of the report.
""".strip()
    print("Generating Overall Context Summary (to be used by other sections)...")
    summary = rag_service.generate_response(prompt, use_chat_history=False)
    print("Overall Context Summary generated.")
    return summary


# --- Report Section Generation Functions ---
# All section generation functions will now accept `overall_summary`

def generate_executive_summary(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Now, generate a **sharp, no-fluff Executive Summary** for **'{idea}'** in **Markdown**.
This section is for the location: **{location}**. Use **{currency_code} & USD** for financials.
Ensure each point under subheadings is concise, around 20-30 words.

---

# **Executive Summary**

### **Overview**
[One-sentence summary of the business and its market potential, reflecting the overall context. Aim for 20-30 words.]

### **Key Insights**
- **Market Positioning:** [Where it fits in the market, with {location}-based insights. Concise, 20-30 words.]
- **Competitive Edge:** [Key players & how this idea stands out. Concise, 20-30 words.]
- **Growth Potential:** [Scalability & market opportunities. Concise, 20-30 words.]
- **Risks & Challenges:** [Market, regulatory, or economic concerns for {location}. Concise, 20-30 words.]

### **Feasibility Score:** **[0-100] based on market demand, problem clarity, solution uniqueness, execution complexity, market size, competition saturation, monetization clarity, and legal/ethical considerations for '{idea}' in '{location}'.**

---

**IMPORTANT:** Response must be **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_problem_validation(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Validate the **core problem** behind **'{idea}'** in **Markdown** format, specifically for **{location}**.
Integrate:
✔ **Localized statistics** for {location} on unmet customer needs.
✔ **Market-specific inefficiencies** in {location} affecting profitability.
✔ **Stakeholder pain points** in {location} (e.g., regulations, infrastructure gaps).
✔ **Currency figures** in both {currency_code} & USD.
Ensure each detailed point under subheadings is concise, around 20-30 words.

---

# **Problem Validation**

### **Unmet Customer Needs in {location}**
- **Need 1:** [Relevant data & {location}-based insights. Detail in 20-30 words.]
- **Need 2:** [Supporting statistics or trends for {location}. Detail in 20-30 words.]

### **Operational Inefficiencies in {location}**
- **Analysis:** [Key inefficiencies affecting cost, scalability, or service delivery in {location}, with real-world examples. Main points in 20-30 words each.]

### **Stakeholder Pain Points in {location}**
- **Pain Point 1:** [Issue affecting businesses, regulators, or consumers in {location}. Describe in 20-30 words.]
- **Pain Point 2:** [Another major challenge in the {location} ecosystem. Describe in 20-30 words.]

**IMPORTANT:** Your response **must be valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_market_analysis(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Conduct a **comprehensive market analysis** in **Markdown** format for **'{idea}'** in **{location}**.
Keep the response brief. Use **{currency_code}** where relevant.
Incorporate:
- **Demographics & psychographics** specific to {location}.
- **Competitor analysis** including **regional ({location}) and global competitors**.
Ensure each descriptive point or list item under subheadings is concise, around 20-30 words.

### **Market Analysis for {location}**

#### **Target Audience in {location}**
[Detailed description of key customer demographics & psychographics in {location}. Summarize key aspects in 20-30 words each.]

#### **Competitor Analysis (relevant to {location})**
- **Competitor:** [Name of major competitor]
  - **Market Share:** [Percentage in {location} if known, brief context. 20-30 words.]
  - **Strengths:** [Key advantages. Each explained in 20-30 words.]
  - **Weaknesses:** [Key disadvantages. Each explained in 20-30 words.]
- **Competitor:** [Name of another major competitor]
  - **Market Share:** [Percentage in {location} if known, brief context. 20-30 words.]
  - **Strengths:** [Key advantages. Each explained in 20-30 words.]
  - **Weaknesses:** [Key disadvantages. Each explained in 20-30 words.]

**IMPORTANT:**
Your response **must be valid Markdown** and must **not contain any YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_market_size_estimation(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Estimate the **Market Size** in **Markdown** format for **'{idea}'** in **{location}**.
Keep response brief.
Incorporate:
- **Region-specific market data** for {location}.
- **Currency figures in both {currency_code} and USD**.
- **Relevant industry reports or data for {location}**.
Ensure each point (Estimation, Methodology, Source) under subheadings is concise, around 20-30 words.

### **Market Size Estimation for {location}**

#### **Total Addressable Market (TAM)**
- **Estimation:** [Market size in {currency_code} & USD. Value and rationale in 20-30 words.]
- **Methodology:** [How TAM was calculated for {location}. 20-30 words.]
- **Source:** [Data source for {location}. Mention concisely, 20-30 words.]

#### **Serviceable Available Market (SAM)**
- **Estimation:** [Market size in {currency_code} & USD. Value and rationale in 20-30 words.]
- **Methodology:** [How SAM was calculated for {location}. 20-30 words.]
- **Source:** [Data source for {location}. Mention concisely, 20-30 words.]

#### **Serviceable Obtainable Market (SOM)**
- **Estimation:** [Market size in {currency_code} & USD. Value and rationale in 20-30 words.]
- **Methodology:** [How SOM was calculated for {location}. 20-30 words.]
- **Source:** [Data source for {location}. Mention concisely, 20-30 words.]

**IMPORTANT:**
Your response **must be valid Markdown** and **must not contain any YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_swot_analysis(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Analyze **'{idea}'** using **SWOT** in **Markdown**. Focus on **{location}**. Use **{currency_code}** where relevant.
Ensure **clarity, conciseness, and industry relevance**.
Each point should be explained in 20-30 words.

---

# **SWOT Analysis for {idea} in {location}**

### **Strengths**
- **[Strength 1]** – [Competitive advantage for '{idea}' in {location}. Explain in 20-30 words.]
- **[Strength 2]** – [Customer value proposition for '{idea}' in {location}. Explain in 20-30 words.]

### **Weaknesses**
- **[Weakness 1]** – [Operational or market challenge for '{idea}' in {location}. Explain in 20-30 words.]
- **[Weakness 2]** – [Scalability or resource constraint for '{idea}' in {location}. Explain in 20-30 words.]

### **Opportunities**
- **[Opportunity 1]** – [Emerging trend or gap in {location} to exploit for '{idea}'. Explain in 20-30 words.]
- **[Opportunity 2]** – [Market shift in {location} favoring growth for '{idea}'. Explain in 20-30 words.]

### **Threats**
- **[Threat 1]** – [External risk or competition in {location} for '{idea}'. Explain in 20-30 words.]
- **[Threat 2]** – [Regulatory or economic concern in {location} for '{idea}'. Explain in 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_vrio_analysis(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Analyze **'{idea}'** using **VRIO** in **Markdown**, considering **{location}**. Use **{currency_code}** where relevant.
Ensure **clarity, conciseness, and industry relevance**.
Each 'Insight' should be explained in 20-30 words.

---

# **VRIO Analysis for {idea} (considering {location})**

### **Value**
- **Insight:** [How '{idea}' delivers exceptional value in {location}. Explain in 20-30 words.]

### **Rarity**
- **Insight:** [What makes '{idea}' unique & scarce in {location}. Explain in 20-30 words.]

### **Imitability**
- **Insight:** [How hard '{idea}' is to replicate & why, in {location}. Explain in 20-30 words.]

### **Organization**
- **Insight:** [How well the business for '{idea}' is structured to sustain its advantage in {location}. Explain in 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_pestel_analysis(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Analyze **'{idea}'** using **PESTEL** in **Markdown**, focusing on **{location}**. Use **{currency_code}** if figures are relevant.
Ensure **clarity, conciseness, and industry relevance**.
Each 'Insight' should highlight specific factors for {location} and be explained in 20-30 words.

---

# **PESTEL Analysis for {idea} in {location}**

### **Political**
- **Insight:** [Regulations, policies in {location} impacting '{idea}'. 20-30 words.]

### **Economic**
- **Insight:** [Market conditions, inflation in {location} impacting '{idea}'. Use {currency_code} if relevant. 20-30 words.]

### **Social**
- **Insight:** [Consumer behavior, trends in {location} impacting '{idea}'. 20-30 words.]

### **Technological**
- **Insight:** [Tech infrastructure, R&D in {location} impacting '{idea}'. 20-30 words.]

### **Environmental**
- **Insight:** [Sustainability, climate factors in {location} impacting '{idea}'. 20-30 words.]

### **Legal**
- **Insight:** [Compliance, laws in {location} impacting '{idea}'. 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_porters_five_forces(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Analyze **'{idea}'** using **Porter’s Five Forces** in **Markdown**, focused on the **{location}** market. Use **{currency_code}** if figures are relevant.
Keep it **concise, specific, and industry-relevant**.
Each 'Insight' should be explained in 20-30 words.

---

# **Porter's Five Forces Analysis for {idea} in {location}**

### **Threat of New Entrants**
- **Insight:** [Barriers to entry in {location} for '{idea}'. 20-30 words.]

### **Bargaining Power of Suppliers**
- **Insight:** [Supplier influence on '{idea}' in {location}. 20-30 words.]

### **Bargaining Power of Buyers**
- **Insight:** [Customer influence on '{idea}' in {location}. 20-30 words.]

### **Threat of Substitutes**
- **Insight:** [Alternative solutions to '{idea}' in {location}. 20-30 words.]

### **Industry Rivalry**
- **Insight:** [Competitive intensity for '{idea}' in {location}. 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_venture_insights(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Provide **Venture Insights** for **'{idea}'** in **Markdown**, with a focus on **{location}**.
Focus on **investment appeal, scalability, and key success factors**. Use **{currency_code} and USD** for financials.
Each 'Insight' should be explained in 20-30 words.

---

# **Venture Insights for {idea} in {location}**

### **Market Opportunity in {location}**
- **Insight:** [Unmet needs & emerging trends in {location} for '{idea}'. 20-30 words.]

### **Investment Potential (considering {location})**
- **Insight:** [Investor interest in {location}, typical funding ({currency_code}/USD) for similar ventures. 20-30 words.]

### **Key Success Factors in {location}**
- **Insight:** [Essential strategies for '{idea}' to succeed in {location}. 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_industry_insights(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Provide **Industry Insights** for **'{idea}'** in **Markdown**, specifically for **{location}**. Use **{currency_code}** if figures are relevant.
Focus on **customer experience, operational efficiency, and profitability**.
Each point or sub-point should be explained in 20-30 words.

---

# **Industry Insights for {idea} in {location}**

### **Current Trends & Opportunities in {location}**
- **Trend:** [Relevant Trend 1 in {location}] → **Opportunity:** [How '{idea}' can leverage it. 20-30 words.]
- **Trend:** [Relevant Trend 2 in {location}] → **Opportunity:** [Market potential for '{idea}'. 20-30 words.]

### **Market Growth & Key Drivers in {location}**
- [Growth projections & major factors driving the industry for '{idea}' in {location}. Summarize in 20-30 words per driver.]

### **Competitive Landscape & Benchmarks in {location}**
- **KPIs:** [Key performance indicators for success in this industry in {location}. Explain each KPI in 20-30 words.]
- **Edge:** [How '{idea}' can outperform competitors in {location}. 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_catwoe_analysis(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Perform a **CATWOE Analysis** for **'{idea}'** in **Markdown**, considering **{location}**. Use **{currency_code}** if figures are relevant.
Focus on **customer experience, operational efficiency, and profitability**.
Each point should be described in 20-30 words.

---

# **CATWOE Analysis for {idea} in {location}**

### **Customers**
- [Who benefits from '{idea}' in {location}? Demographics, user groups. 20-30 words.]

### **Actors**
- [Key stakeholders executing '{idea}' in {location}. 20-30 words.]

### **Transformation Process**
- [How '{idea}' changes inputs to outputs in {location}. 20-30 words.]

### **Worldview**
- [Broader impact of '{idea}' in {location}. 20-30 words.]

### **Owner**
- **Who:** [Decision-maker for '{idea}'. 20-30 words.]
- **Why:** [Strategic rationale for '{idea}'. 20-30 words.]

### **Environmental Constraints**
- [Limitations in {location} for '{idea}'. 20-30 words.]

---

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_strategy(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Develop a **Strategic Plan** in **Markdown** for **'{idea}'** in **{location}**.
Use **{currency_code} & USD** for financials.
Include:
- **Market challenges & opportunities in {location}.**
- **Key regulatory, economic, or competitive factors in {location}.**
Each point under subheadings should be explained in 20-30 words.

---

# **Strategic Plan for {idea} in {location}**

### **Short-Term Goals (1-3 Years)**
- **Customer Growth:** [Target users in {location}. 20-30 words.]
- **Revenue Goal:** [{currency_code} X (approx. USD Y). 20-30 words.]
- **Brand Positioning:** [Actions for brand recognition in {location}. 20-30 words.]

### **Long-Term Goals (5-10 Years)**
- **Market Expansion:** [New regions/segments from {location} base. 20-30 words.]
- **Scalability Plan:** [Tech & operational scaling for {location} and beyond. 20-30 words.]
- **Projected Revenue:** [{currency_code} X (approx. USD Y). 20-30 words.]

### **Growth Drivers & Risk Mitigation (for {location})**
- **Key Growth Driver:** [Top factor for '{idea}' in {location}. 20-30 words.]
- **Risk & Mitigation:** [Biggest challenge in {location} for '{idea}' & solution. 20-30 words.]

### **Action Plan (Initial Milestones for {location})**
- **Milestone:** [Specific goal for {location} market entry. 20-30 words.]
  - **Actions:** [Key execution steps. Each action 20-30 words.]

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_marketing_strategy(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Create a **Marketing Strategy** in **Markdown** for **'{idea}'** in **{location}**.
Use **{currency_code} and USD** for budget figures.
Incorporate:
- **Regional consumer behavior trends in {location}**.
- **Marketing channels specific to {location}**.
Each point under subheadings should be explained concisely, around 20-30 words.

### **Marketing Strategy for {idea} in {location}**

#### **Positioning, Messaging, and USP**
- **Description:** [USP and brand positioning for '{idea}' in {location}. 20-30 words per aspect.]

#### **Marketing Channels and Budget (for {location})**
- **Channel:** [Best channel for '{idea}' in {location}]
   **Budget Allocation:** [% & {currency_code} X (USD Y). Rationale 20-30 words.]
- **Channel:** [Second relevant channel for '{idea}' in {location}]
   **Budget Allocation:** [% & {currency_code} X (USD Y). Rationale 20-30 words.]

#### **KPIs and Success Metrics (for {location})**
- **KPI:** Brand Awareness in {location}
  **Target Value:** [Metric for {location}. Target and rationale 20-30 words.]
- **KPI:** Customer Engagement in {location}
  **Target Value:** [Reach, traffic, or conversion target. 20-30 words.]
- **KPI:** Revenue Growth from {location}
  **Target Value:** [Expected revenue in {currency_code} & USD. 20-30 words.]

**IMPORTANT:** Your response **must be valid Markdown** and **not contain any YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_social_media_strategy(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Create a **Social Media Strategy** in **Markdown** for **'{idea}'** in **{location}**.
Use **{currency_code} and USD** for ad budget.
Incorporate:
- **Preferred social platforms in {location}**.
- **Localized content themes for {location}**.
Each justification, plan, tactic, target, or budget explanation should be 20-30 words.

---

# **Social Media Strategy for {idea} in {location}**

## **Platform Selection & Content Plan (for {location})**

### **Best Platform: [Top platform in {location} for '{idea}']**
- **Justification:** [Why ideal for '{idea}' in {location}. 20-30 words.]
- **Content Plan:** [Content types, frequency for {location}. 20-30 words.]

### **Second Platform: [Another channel in {location} for '{idea}']**
- **Justification:** [Demographics & engagement in {location}. 20-30 words.]
- **Content Plan:** [Posting strategy for {location}. 20-30 words.]

## **Content Themes & Engagement Tactics (for {location})**
1. **Theme:** [Content theme for '{idea}' in {location}]
   - **Tactic:** [Engagement method for {location}. 20-30 words.]
2. **Theme:** [Another theme for '{idea}' in {location}]
   - **Tactic:** [Interaction enhancement in {location}. 20-30 words.]

## **Key Performance Indicators (KPIs) (for {location})**
 **Follower Growth** → [Target growth in {location}. 20-30 words.]
 **Engagement Rate** → [Ideal % for {location}. 20-30 words.]
 **Website Traffic from Social (local)** → [CTR & conversion goals. 20-30 words.]

## **Paid Advertising (if applicable for {location})**
 **Budget:** [Spend in {currency_code} & USD. 20-30 words.]
 **Expected ROI:** [Conversion rates & CAC for {location}. 20-30 words.]

**IMPORTANT:** The response **must be valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_slogan(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Based on the business idea: '{idea}', potentially considering unique aspects of '{location}' and using {currency_code} for any implied value, generate three catchy slogan options in Markdown.
Slogans should be modern, clean, efficient, max 8 words.
Each reasoning should be concise, 20-30 words.

IMPORTANT: Your entire response must be valid Markdown with no YAML formatting or extra text.

### **Slogan Option 1:** [slogan 1]
   - *Reasoning:* [Why effective for '{idea}', possibly reflecting {location}. 20-30 words.]

### **Slogan Option 2:** [slogan 2]
   - *Reasoning:* [Why effective for '{idea}', possibly reflecting {location}. 20-30 words.]

### **Slogan Option 3:** [slogan 3]
   - *Reasoning:* [Why effective for '{idea}', possibly reflecting {location}. 20-30 words.]
    """.strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_marketing_channels(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Identify **best Marketing Channels** in **Markdown** for **'{idea}'** in **{location}**.
Use **{currency_code} and USD** for ad costs.
Prioritize: Customer Experience, Operational Efficiency, Profitability & ROI.
Include:
- **Regional ad platforms for {location}**.
- **Local penetration strategies (organic/paid) for {location}**.
Each best practice, budget, or consideration should be 20-30 words.

---

# **Marketing Channels for {idea} in {location} (Ranked by ROI)**

## **Top Channel: [Best channel in {location} for '{idea}']**
**ROI Ranking:** ⭐⭐⭐⭐⭐
**Strategy:** [Organic / Paid]
**Best Practices for {location}:**
- [Optimization for {location}. 20-30 words.]
- [Audience targeting in {location}. 20-30 words.]
- **Budget:** [Ad spend in {currency_code} & USD for {location}. 20-30 words.]

## **High-Impact Channel: [Second channel in {location} for '{idea}']**
**ROI Ranking:** ⭐⭐⭐⭐
**Strategy:** [Organic / Paid]
**Best Practices for {location}:**
- [Content approach for {location}. 20-30 words.]
- [Engagement for {location}. 20-30 words.]
- **Budget:** [Costs in {currency_code} & USD for {location}. 20-30 words.]

## **Additional Considerations for {location}**
- **Offline Marketing:** [Local events/media in {location}. Strategy 20-30 words.]
- **Strategic Partnerships:** [Local collaborations for {location}. 20-30 words.]
- **Localization Strategy:** [Tailoring content for {location}. 20-30 words.]

**IMPORTANT:** Ensure **valid Markdown** with **no YAML formatting**.
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_mvp(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Define a **Minimum Viable Product (MVP)** in **Markdown** for **'{idea}'**, tailored for **{location}**.
Use **{currency_code} and USD** for budgeting.
Include feasibility, localization for {location}, compliance.
Each feature, user description, plan, model, phase, cost, or risk should be 20-30 words.

---

# **Minimum Viable Product (MVP) for {idea} in {location}**

## **Core Features (for {location} launch)**
- **Essential Feature 1:** [Must-have for '{idea}' in {location}. Rationale 20-30 words.]
- **Essential Feature 2:** [Enhances local fit for '{idea}' in {location}. Rationale 20-30 words.]
- **Differentiator:** [Competitive edge for '{idea}' in {location}. Rationale 20-30 words.]

## **Target Market & Testing (in {location})**
- **Primary Users:** [Key audience for '{idea}' in {location}. 20-30 words.]
- **Early Adopters:** [Users in {location} for '{idea}'. 20-30 words.]
- **Market Validation Plan:** [Testing in {location}. 20-30 words.]

## **Business Model & Feasibility (for {location})**
- **Revenue Model:** [Model for '{idea}' in {location}. 20-30 words.]
- **Market Potential:** [TAM for '{idea}' in {location}. 20-30 words.]
- **Competitive Edge:** [Differentiator for '{idea}' in {location}. 20-30 words.]

## **Development Phases & Milestones (focus on {location})**
1. **Prototype (Phase 1):** [Deliverables for {location}. 20-30 words.]
2. **Beta Testing (Phase 2 in {location}):** [Success metrics. 20-30 words.]
3. **Scaling (Phase 3, post-{location}):** [Growth plan. 20-30 words.]

## **Financial Estimates (for {location} MVP)**
- **MVP Development Cost:** [{currency_code} X (USD Y). Context 20-30 words.]
- **Projected CAC (in {location}):** [{currency_code} X/user (USD Y). Context 20-30 words.]
- **Break-Even Timeline (initial):** [Duration for {location} launch. 20-30 words.]

## **Potential Risks & Challenges (for {location})**
- **Local Risks:** [Barriers in {location} for '{idea}'. 20-30 words.]
- **Execution Risks:** [Challenges for '{idea}'. 20-30 words.]

**Ensure valid Markdown format.**
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_usp(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Define a **Unique Selling Proposition (USP)** in **Markdown** for **'{idea}'** in **{location}**. Use **{currency_code}** if figures are relevant.
Highlight differentiation, customer benefits, competitive positioning concisely.
Each point should be explained in 20-30 words.

---

# **Unique Selling Proposition (USP) for {idea} in {location}**

## **Key Differentiators (for {location})**
- **What Makes It Stand Out:** [Unique value of '{idea}' for {location}. 20-30 words.]
- **Technology/Innovation Factor:** [Tech advantage of '{idea}' for {location}. 20-30 words.]

## **Customer Benefits (in {location})**
- **Problem Solved:** [Key issue '{idea}' addresses in {location}. 20-30 words.]
- **Why It Matters in {location}:** [Local relevance of '{idea}'. 20-30 words.]

## **Value Proposition Statement**
- **USP Statement:** "[Concise USP for '{idea}' targeting {location}]"
- **Impact:** [Benefit for {location} customers. 20-30 words.]

## **Competitive Positioning (against {location} competitors)**
- **Competitor 1 (in {location}):** [Their offering. 20-30 words.]
- **Why '{idea}' Wins:** [Edge for '{idea}' in {location}. 20-30 words.]

---
**Ensure valid Markdown format.**
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_customer_persona(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Create a **Customer Persona** in **Markdown** for **'{idea}'** in **{location}**.
Income/spending in **{currency_code} and USD**.
Include demographics, behaviors, pain points, motivations concisely.
Each descriptive point should be 20-30 words.

---

# **Customer Persona for {idea} in {location}**

## **Persona Name:** [Relatable name for {location}]

## **Demographics (specific to {location})**
- **Age Range:** [Target age in {location}. Relevance 20-30 words.]
- **Gender:** [Primary gender in {location}. 20-30 words.]
- **Location:** [Region within {location}. 20-30 words.]
- **Income Level:** [{currency_code} X (USD Y) in {location}. 20-30 words.]
- **Employment Status:** [Common jobs in {location}. 20-30 words.]

## **Behavioral Patterns & Pain Points (in {location})**
- **Daily Habits:** [Interaction with similar products in {location}. 20-30 words.]
- **Technology Usage:** [Preferred tech in {location}. 20-30 words.]
- **Key Pain Points:** [Challenges '{idea}' solves in {location}. 20-30 words.]

## **Buying Motivations & Decision Factors (for {location} customers)**
- **Why They Buy:** [Reasons for solutions like '{idea}' in {location}. 20-30 words.]
- **Key Decision Factors:** [Influences in {location}. 20-30 words.]
- **Spending Behavior:** [Budget in {currency_code} (USD Y) in {location}. 20-30 words.]

## **Preferred Marketing & Sales Channels (in {location})**
- **Most Effective Channels:** [Where they engage in {location}. 20-30 words.]

---
**Ensure valid Markdown format.**
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_finances(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Provide a **Financial Overview** in **Markdown** for **'{idea}'** in **{location}**.
Financials in **{currency_code} and USD equivalent**.
Include revenue model, costs, profitability timeline, funding needs concisely.
Each point or sub-point should be explained in 20-30 words.

---

# **Financial Overview for {idea} in {location}**

## **Revenue Model (for {location} market)**
- **Revenue Streams:**
  - [{currency_code} Stream 1 for '{idea}' in {location}. 20-30 words.]
  - [{currency_code} Stream 2 for '{idea}' in {location}. 20-30 words.]
- **Est. Initial Revenue (Y1 in {location}):** [{currency_code} X (USD Y). Context 20-30 words.]

## **Cost Structure & Profitability (estimates for {location})**
- **Major Costs:**
  - [Expense 1 for '{idea}' in {location} ({currency_code}). 20-30 words.]
  - [Expense 2 for '{idea}' in {location} ({currency_code}). 20-30 words.]
- **Profitability Timeline (projections for {location}):**
  - **Year 1:** [Revenue, costs, net profit/loss in {currency_code} (USD Y). 20-30 words.]
  - **Year 3:** [Financials for {location}. 20-30 words.]

## **Funding & Investment (for {location} launch)**
- **Funding Required:** [{currency_code} X (USD Y) for '{idea}' in {location}. Context 20-30 words.]
- **Potential Funding Strategies (for {location}):**
  - [Strategy 1 for {location}. 20-30 words.]
  - [Strategy 2 for {location}. 20-30 words.]

---
**Ensure valid Markdown format.**
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_go_to_market_strategy(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Develop a **Go-To-Market (GTM) Strategy** in **Markdown** for **'{idea}'** in **{location}**.
Financials in **{currency_code} and USD**. Each point concisely explained in 20-30 words.
Include market entry, distribution, customer acquisition, success measurement.

---

# **Go-To-Market Strategy for {idea} in {location}**

## **Market Entry & Launch Plan (for {location})**
- **Target Market Segments:** [Segments for '{idea}' in {location}. 20-30 words.]
- **Launch Timeline:** [Phases for '{idea}' in {location}. 20-30 words.]
- **Resource Allocation:** [Spend in {currency_code} (USD Y) for {location} launch. 20-30 words.]

## **Distribution & Customer Acquisition (in {location})**
- **Sales Channels:** [Channels for '{idea}' in {location}. Strategy 20-30 words.]
- **Marketing Strategies (for {location}):**
  - **Organic:** [SEO, content for {location}. Tactic 20-30 words.]
  - **Paid:** [Ads, influencers for {location}. Tactic 20-30 words.]
- **Local Adaptation:** [Tailoring '{idea}' for {location}. 20-30 words.]

## **Key Metrics (KPIs) for GTM Success in {location}**
- **Customer Acquisition Cost (CAC):** [Target CAC in {currency_code} (USD Y) for {location}. Rationale 20-30 words.]
- **Customer Lifetime Value (LTV):** [Projected LTV for {location}. Rationale 20-30 words.]
- **Market Penetration Rate:** [Target for '{idea}' in {location} Y1. 20-30 words.]
- **Brand Awareness & Engagement:** [Metrics for {location}. Target 20-30 words.]

---

**Ensure valid Markdown format.**
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)

def generate_competitive_analysis(idea: str, location: str, currency_code: str, overall_summary: str, rag_service: RAGService):
    prompt = f"""
Given the following overall context for the business idea:
--- OVERALL CONTEXT ---
{overall_summary}
--- END OVERALL CONTEXT ---

Conduct a **Competitive Analysis** in **Markdown** for **'{idea}'** in **{location}**.
Use **{currency_code} and USD** for pricing.
Cover customer experience, efficiency, profitability, pricing.
Each point (Positioning, Strength, Weakness, Pricing, Differentiation) should be 20-30 words.

---

# **Competitive Analysis for {idea} in {location}**

## **Key Competitors in {location}**
- **Competitor 1:** [Name] – **Positioning:** [Market position in {location}. 20-30 words.]
- **Competitor 2:** [Name] – **Positioning:** [Market position in {location}. 20-30 words.]

## **Competitor Comparison (for {location} market)**
- **Competitor 1:**
  - **Strengths:** [Strengths in {location}. Each 20-30 words.]
  - **Weaknesses:** [Weaknesses in {location}. Each 20-30 words.]
  - **Pricing (in {location}):** [{currency_code} range (USD X). Context 20-30 words.]
- **Competitor 2:**
  - **Strengths:** [Strengths in {location}. Each 20-30 words.]
  - **Weaknesses:** [Weaknesses in {location}. Each 20-30 words.]
  - **Pricing (in {location}):** [{currency_code} range (USD X). Context 20-30 words.]

## **Differentiation Strategy for '{idea}' in {location}**
- **How We Stand Out:** [Unique strengths of '{idea}' for {location}. 20-30 words.]
- **Better Customer Experience:** [How '{idea}' improves CX in {location}. 20-30 words.]

---
**Ensure valid Markdown format.**
""".strip()
    return rag_service.generate_response(prompt, use_chat_history=False)


# --- Main Report Generation Orchestrator ---
def generate_full_final_parallel_executed_report(idea: str, current_user: str, location: str, file_path: str = None):
    """
    Generates all sections of the final report.
    Currency and Overall Summary are generated sequentially first.
    Other sections are generated in parallel, using the currency and overall summary.
    """
    print(f"--- Starting Full Report Generation ---")
    print(f"Idea: '{idea}'")
    print(f"Location: '{location}'")
    print(f"User: '{current_user}'")

    # 1. Get Currency based on Location (Sequential)
    print("\nStep 1: Determining currency...")
    local_currency_code = get_currency_via_llm(location)
    print(f"Currency for {location} determined as: {local_currency_code}")

    # 2. Initialize RAG Service (Sequential)
    print("\nStep 2: Initializing RAG Service...")
    rag_service = RAGService(
        current_user,
        file_path
    )
    print("RAG Service initialized.")

    # 3. Generate Overall Context Summary (Sequential)
    print("\nStep 3: Generating Overall Context Summary (sequentially)...")
    overall_summary_content = generate_overall_context_summary(idea, location, rag_service)
    print("Overall Context Summary content acquired.")

    results = {"overall_context_summary": overall_summary_content} # Pre-populate results

    # 4. Define tasks for the remaining report sections
    print("\nStep 4: Defining report generation tasks for parallel execution...")
    report_section_tasks = {
        "executive_summary": generate_executive_summary,
        "problem_validation": generate_problem_validation,
        "market_analysis": generate_market_analysis,
        "market_size_estimation": generate_market_size_estimation,
        "swot_analysis": generate_swot_analysis,
        "vrio_analysis": generate_vrio_analysis,
        "pestel_analysis": generate_pestel_analysis,
        "porters_five_forces": generate_porters_five_forces,
        "venture_insights": generate_venture_insights,
        "industry_insights": generate_industry_insights,
        "catwoe_analysis": generate_catwoe_analysis,
        "strategy": generate_strategy,
        "marketing_strategy": generate_marketing_strategy,
        "social_media_strategy": generate_social_media_strategy,
        "slogan": generate_slogan,
        "marketing_channels": generate_marketing_channels,
        "mvp": generate_mvp,
        "usp": generate_usp,
        "customer_persona": generate_customer_persona,
        "finances": generate_finances,
        "go_to_market_strategy": generate_go_to_market_strategy,
        "competitive_analysis": generate_competitive_analysis,
    }
    print(f"{len(report_section_tasks)} tasks defined for parallel generation.")

    # 5. Execute tasks in parallel
    print("\nStep 5: Executing report section tasks in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_task_name = {
            executor.submit(func, idea, location, local_currency_code, overall_summary_content, rag_service): name
            for name, func in report_section_tasks.items()
        }

        for i, future in enumerate(concurrent.futures.as_completed(future_to_task_name)):
            task_name = future_to_task_name[future]
            try:
                results[task_name] = future.result()
                print(f"   ✓ Completed: {task_name} ({i+1}/{len(report_section_tasks)})")
            except Exception as e:
                error_message = f"Error generating {task_name}: {str(e)}"
                print(f"   ! Error in task: {task_name} - {error_message}")
                results[task_name] = error_message
    
    print("\nStep 6: All report sections processed.")
    return results


if __name__ == '__main__':
    test_idea = "Eco-friendly urban mobility subscription service"
    test_user = "analyst_jane_doe"
    test_location = "Amsterdam, Netherlands"
    # test_location = "Future Mars Colony" # To test default USD and handling of unusual locations
    test_file_path = None # Optional: path to a context document for RAG

    print(f"--- Initiating example report generation ---")
    
    start_time = time.time()
    final_report_data = generate_full_final_parallel_executed_report(
        idea=test_idea,
        current_user=test_user,
        location=test_location,
        file_path=test_file_path
    )
    end_time = time.time()

    print(f"\n--- Full Report Generation Completed in {end_time - start_time:.2f} seconds ---")

    # Print out the generated sections (order might vary slightly due to parallel execution, except for overall_summary)
    print(f"\n\n--- Overall Context Summary ---")
    print(final_report_data.get("overall_context_summary", "Not generated."))
    
    for section_name, content in final_report_data.items():
        if section_name != "overall_context_summary":
            print(f"\n\n--- {section_name.replace('_', ' ').title()} ---")
            print(content)

    # Example: Save the full report to a single Markdown file
    report_filename = f"Comprehensive_Report_{test_idea[:20].replace(' ', '_')}_{test_location.split(',')[0].replace(' ', '_')}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(f"# Comprehensive Business Report\n\n")
        f.write(f"**Idea:** {test_idea}\n")
        f.write(f"**Location:** {test_location}\n")
        f.write(f"**Generated on:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Write overall summary first
        f.write(f"## Overall Context Summary\n\n")
        f.write(final_report_data.get("overall_context_summary", "Not available.") + "\n\n---\n\n")

        # Write other sections
        for section_name, content_text in final_report_data.items():
            if section_name != "overall_context_summary":
                f.write(f"## {section_name.replace('_', ' ').title()}\n\n")
                f.write(str(content_text) + "\n\n---\n\n") # Ensure content is string
    print(f"\nFull report saved to {report_filename}")