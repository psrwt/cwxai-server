import concurrent.futures
from openai import AzureOpenAI, RateLimitError, APIError
from dotenv import load_dotenv
import os
import time
import json
import re
import datetime

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

SYSTEM_ROLE = """You are a highly skilled and meticulous business analyst and consultant, with a talent for making complex information engaging.
Your task is to generate specific sections of a business analysis report based on a given idea, location, overall context summary, and a target currency.
Craft your analysis in a professional yet engaging manner. Your goal is to present these insights as if to a potential investor or key stakeholder, making the opportunity clear and compelling while delivering critical facts.
Use clear, compelling language. Where appropriate, frame insights to highlight the story of the business opportunity or challenges to overcome. Maintain a tone that is both authoritative and accessible.
Adhere strictly to the requested format (Markdown) and structure for each section.
Ensure insights are relevant to the provided idea, location, and align with the overall context summary.
Use simple, direct language. Keep sentences short. Be concise, to the point, and impactful.
For all individual insights, bullet points, or descriptive items within a list or under a subheading, keep the text for each item to approximately 20-30 words. This ensures the report is to-the-point and easy to read.
You will be provided with a TARGET_CURRENCY symbol for the report. If financial figures are requested or appropriate, provide them primarily in this TARGET_CURRENCY. If the TARGET_CURRENCY is not USD, also provide plausible USD equivalents where sensible.
Avoid generic statements; provide specific, plausible (though hypothetical) details and data points where structure suggests.
Do NOT include ```markdown blocks around your entire response for a section. Only use markdown formatting within the content itself (like headings, lists, bold text).
Focus ONLY on the specific section requested in each prompt, avoiding overlap with other analytical frameworks unless explicitly instructed by the prompt structure.
Keep responses concise, fulfilling the requirements of each section's template, including word limits per point.
"""

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
            model=AZURE_DEPLOYMENT_NAME, # Use the main deployment or a faster/cheaper one if available for this task
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides 3-letter ISO currency codes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1, # Low temperature for factual, deterministic output
            max_tokens=10,    # Max 3 letters + some buffer, but should be very short
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        currency_code = response.choices[0].message.content.strip()
        
        # Validate if the response is a 3-letter uppercase string
        if re.fullmatch(r"^[A-Z]{3}$", currency_code):
            print(f"   ✓ LLM determined currency for '{location_name}': {currency_code}")
            return currency_code
        else:
            print(f"   ! LLM response for currency ('{currency_code}') not a valid 3-letter code. Defaulting to USD for '{location_name}'.")
            return "USD"
    except Exception as e:
        print(f"   ! Error calling LLM for currency detection for '{location_name}': {e}. Defaulting to USD.")
        return "USD"

# --- OpenAI API Call Helper ---
def _generate_content(prompt, section_name, max_tokens=800, temperature=0.5): # Temp at 0.5 for engaging yet focused output
    """Helper function to call OpenAI ChatCompletion and handle errors."""
    print(f"   Generating section: {section_name}...")
    start_time = time.time()
    retries = 3
    wait_time = 5

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=AZURE_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_ROLE},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
            )
            content = response.choices[0].message.content.strip()
            usage = response.usage
            time_taken = time.time() - start_time
            print(f"   ✓ Section '{section_name}' generated in {time_taken:.2f}s (Attempt {attempt + 1})")
            return {
                "content": content,
                "time_taken": time_taken,
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0
            }
        except RateLimitError as rle:
            print(f"   ! Rate limit hit for section '{section_name}' (Attempt {attempt + 1}/{retries}). Waiting {wait_time}s... Error: {rle}")
            if attempt == retries - 1: raise
            time.sleep(wait_time)
            wait_time *= 2
        except APIError as apie:
            print(f"   ! OpenAI API Error for section '{section_name}' (Attempt {attempt + 1}/{retries}). Waiting {wait_time}s... Error: {apie}")
            if attempt == retries - 1: raise
            time.sleep(wait_time)
            wait_time *= 2
        except Exception as e:
            error_message = f"Unexpected error generating section '{section_name}' on attempt {attempt + 1}: {type(e).__name__} - {str(e)}"
            print(f"   ✗ {error_message}")
            if attempt == retries - 1:
                 return {
                    "content": f"### Error Generating Section: {section_name}\n\nAfter {retries} attempts.\n```\n{error_message}\n```",
                    "time_taken": time.time() - start_time,
                    "input_tokens": 0,
                    "output_tokens": 0
                 }
            time.sleep(wait_time)
            wait_time *= 2
    final_error_msg = f"Failed to generate section '{section_name}' after {retries} attempts."
    print(f"   ✗ {final_error_msg}")
    return {
        "content": f"### Error Generating Section: {section_name}\n\n```\n{final_error_msg}\n```",
        "time_taken": time.time() - start_time,
        "input_tokens": 0,
        "output_tokens": 0
    }

# --- Context Unifier: Overall Summary Generation ---
def generate_overall_context_summary(idea, location):
    prompt = f"""
Generate a concise (target 2-3 paragraphs, maximum 150 words) overall context summary in PLAIN TEXT (NO MARKDOWN formatting) for a business report about the idea: '{idea}' in the location: '{location}'.

This summary should briefly outline:
1.  The core business concept and its primary objective (1-2 sentences).
2.  The main problem it aims to solve for the target audience in {location} (1 sentence).
3.  The key solution or value proposition offered (1 sentence).
4.  The primary target market segment in {location} (1 sentence).

Keep the language very clear, simple, direct, and strategic. Focus on the essence. Do NOT use any Markdown formatting.
""".strip()
    return _generate_content(prompt, "Overall Context Summary", max_tokens=200, temperature=0.4)["content"] # Slightly lower temp for precise summary

# --- Section Generation Functions (Unchanged from previous, system role drives engagement) ---
# Note: Prompts remain largely the same as the SYSTEM_ROLE now carries the instruction for engagement and conciseness.
# The {target_currency_symbol} is passed and used as before.
# The "approx. 20-30 words" constraint is reiterated in prompts as a strong guideline.

def generate_executive_summary(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall business context, generate a sharp, concise, and engaging Executive Summary in Markdown for '{idea}' in '{location}'.
Each point/insight approx. 20-30 words.

Follow this structure exactly:

# **Executive Summary**

### **Overview**
[One-sentence, high-impact summary of '{idea}' and its market potential in {location}, aligning with overall context. Approx. 20-30 words.]

### **Key Insights**
[Each insight approx. 20-30 words]
- **Market Positioning:** [Where '{idea}' fits in {location} market. Insights on demand/gaps, consistent with context.]
- **Competitive Edge:** [1-2 key competitors in {location}; how '{idea}' uniquely stands out.]
- **Growth Potential:** [Scalability within {location} and potential beyond.]
- **Risks & Challenges:** [1-2 primary risks, considering {location}-specific factors.]

### **Feasibility Score:** [Estimated score (0-100) for '{idea}' in {location}. Justify in one sentence (approx. 20-30 words).]

---
**IMPORTANT:** Valid Markdown. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. No ```markdown blocks around entire response. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Executive Summary")

def generate_problem_validation(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, validate the core problem for '{idea}' in '{location}'. Present this validation in an engaging way.
Each point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Problem Validation**

### **Unmet Customer Needs**
[Each need approx. 20-30 words]
- **Need 1:** [Primary customer need '{idea}' addresses. Plausible localized statistics/examples for {location}.]
- **Need 2:** [Secondary, related need in {location}.]

### **Operational Inefficiencies / Market Gaps**
[Analysis approx. 20-30 words]
- **Analysis:** [Key inefficiencies/gaps in {location} market '{idea}' fixes. Brief example with costs if relevant.]

### **Stakeholder Pain Points**
[Each pain point approx. 20-30 words]
- **Pain Point 1:** [Specific challenge for stakeholders in {location} related to the problem.]
- **Pain Point 2:** [Optional: Another significant pain point in {location}.]

---
**IMPORTANT:** {location}-specific context. Financials primarily in {target_currency_symbol} (and USD if {target_currency_symbol} != USD). Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Problem Validation")

def generate_market_analysis(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, conduct a concise and engaging market analysis (Target Audience & Competitors) for '{idea}' in '{location}'.
Each description/point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Market Analysis**

#### **Target Audience**
[Describe primary target audience for '{idea}' in {location}. Key demographics/psychographics specific to {location}. Be specific. Approx. 20-30 words.]

#### **Competitor Analysis**
[Each competitor point (Market Share, Strengths, Weaknesses) approx. 20-30 words or a short list]
- **Competitor:** [Plausible major competitor in {location}.]
  - **Market Share:** [Est. plausible share in {location}.]
  - **Strengths:** [1-2 key strengths in {location} market.]
  - **Weaknesses:** [1-2 key weaknesses in {location} market '{idea}' could exploit.]
- **Competitor:** [Second plausible competitor in {location}.]
  - **Market Share:** [Est. plausible share.]
  - **Strengths:** [1-2 strengths.]
  - **Weaknesses:** [1-2 weaknesses.]

---
**IMPORTANT:** {location}-specific audience/competitors. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Market Analysis")

def generate_market_size_estimation(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, estimate market size (TAM, SAM, SOM) for '{idea}', focusing on '{location}'. Make the numbers tell a story of potential.
Each estimation/methodology/source point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Market Size Estimation**

#### **Total Addressable Market (TAM)**
- **Estimation:** [Est. total global/regional market size for '{idea}'. Plausible figure.]
- **Methodology:** [Brief plausible method, e.g., Based on global industry reports.]
- **Source:** [Plausible source type, e.g., Industry Research Reports.]

#### **Serviceable Available Market (SAM)**
- **Estimation:** [Portion of TAM reachable, focusing on {location}. Plausible figures.]
- **Methodology:** [Plausible method, e.g., Demographic data for target segments in {location}.]
- **Source:** [Plausible source types, e.g., {location} National Statistics Office.]

#### **Serviceable Obtainable Market (SOM)**
- **Estimation:** [Realistic portion of SAM for '{idea}' in 3-5 years (primarily {location}). Plausible figures.]
- **Methodology:** [Plausible method, e.g., Projected market penetration rate in {location}.]
- **Source:** [Plausible source, e.g., Internal projections for {location}.]

---
**IMPORTANT:** Plausible, hypothetical figures. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Market Size Estimation", max_tokens=600)

def generate_swot_analysis(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, generate an engaging SWOT Analysis for '{idea}' in '{location}'.
Each point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **SWOT Analysis**

### **Strengths** (Internal, Positive)
[Each strength approx. 20-30 words]
- **[Strength 1]:** [Plausible key internal strength of '{idea}'.]
- **[Strength 2]:** [Another plausible internal strength.]

### **Weaknesses** (Internal, Negative)
[Each weakness approx. 20-30 words]
- **[Weakness 1]:** [Plausible key internal weakness for '{idea}' in {location}.]
- **[Weakness 2]:** [Another plausible internal weakness.]

### **Opportunities** (External, Positive)
[Each opportunity approx. 20-30 words]
- **[Opportunity 1]:** [Plausible key external opportunity in {location} market.]
- **[Opportunity 2]:** [Another plausible external opportunity for {location}.]

### **Threats** (External, Negative)
[Each threat approx. 20-30 words]
- **[Threat 1]:** [Plausible key external threat in {location}.]
- **[Threat 2]:** [Another plausible external threat for {location}.]

---
**IMPORTANT:** Strengths/Weaknesses internal; Opportunities/Threats external to {location} market. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "SWOT Analysis")

def generate_vrio_analysis(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, analyze a core resource/capability of '{idea}' using VRIO in '{location}'. Present this as a strategic assessment.
Each insight approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **VRIO Analysis**
*(Analyzing primary resource/capability of '{idea}')*

### **Value**
- **Insight:** [Does it allow '{idea}' to exploit opportunity/neutralize threat in {location}? How it creates value for customers in {location}. Approx. 20-30 words.]

### **Rarity**
- **Insight:** [Is it controlled by few competitors in {location}? Assess rarity (Yes/No/Partially) & explain. Approx. 20-30 words.]

### **Imitability**
- **Insight:** [Cost disadvantage for others to obtain/develop it? Assess (Costly/Moderate/Easy) for {location}. Approx. 20-30 words.]

### **Organization**
- **Insight:** [Is '{idea}'s organization suited to exploit it in {location}? Assess alignment (Yes/No/Partially) & explain. Approx. 20-30 words.]

**Conclusion:** [Competitive implication for '{idea}' in {location} market (e.g., Sustainable Competitive Advantage). Approx. 20-30 words.]

---
**IMPORTANT:** Focus VRIO on a core resource of '{idea}' relevant to {location}. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "VRIO Analysis")

def generate_pestel_analysis(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, conduct an engaging PESTEL Analysis for '{idea}' in '{location}'.
Each insight approx. 20-30 words. Plausible examples. Markdown format.

Follow this structure exactly:

# **PESTEL Analysis**

### **Political**
- **Insight:** [1-2 key political factors in {location} impacting '{idea}' (e.g., Govt stability, Regulations, Tax policies). Approx. 20-30 words per factor.]

### **Economic**
- **Insight:** [1-2 key economic factors in {location} (e.g., GDP outlook, Inflation, Consumer spending, Currency stability). Approx. 20-30 words per factor.]

### **Social**
- **Insight:** [1-2 key social/cultural factors in {location} (e.g., Demographics, Lifestyle trends, Attitudes to sector). Approx. 20-30 words per factor.]

### **Technological**
- **Insight:** [1-2 key tech factors in {location} (e.g., Internet penetration, Infrastructure, R&D focus). Approx. 20-30 words per factor.]

### **Environmental**
- **Insight:** [1-2 key environmental factors in {location} (e.g., Regulations, Sustainability awareness, Climate risks). Approx. 20-30 words per factor.]

### **Legal**
- **Insight:** [1-2 key legal factors in {location} (e.g., Data laws, Consumer protection, Contract enforcement). Approx. 20-30 words per factor.]

---
**IMPORTANT:** Insights plausible and relevant to '{location}' & '{idea}'. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "PESTEL Analysis", max_tokens=700)

def generate_porters_five_forces(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, analyze competitive environment for '{idea}' in '{location}' using Porter's Five Forces. Make the competitive dynamics clear and engaging.
Each justification approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Porter's Five Forces Analysis**

### **Threat of New Entrants**
- **Assessment:** [High/Medium/Low]
- **Justification:** [1-2 key barriers in {location} (e.g., Capital, Brand loyalty, Regulations). Approx. 20-30 words.]

### **Bargaining Power of Suppliers**
- **Assessment:** [High/Medium/Low]
- **Justification:** [Supplier concentration, Switching costs for '{idea}' in {location}. Approx. 20-30 words.]

### **Bargaining Power of Buyers**
- **Assessment:** [High/Medium/Low]
- **Justification:** [Customer concentration, Alternatives, Price sensitivity in {location}. Approx. 20-30 words.]

### **Threat of Substitutes**
- **Assessment:** [High/Medium/Low]
- **Justification:** [1-2 plausible substitutes in {location}. Price/performance relative to '{idea}'. Approx. 20-30 words.]

### **Industry Rivalry**
- **Assessment:** [High/Medium/Low]
- **Justification:** [Competitor strength, Market growth rate, Differentiation in {location}. Approx. 20-30 words.]

---
**IMPORTANT:** Frame analysis around dynamics in '{location}'. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Porter's Five Forces")

def generate_venture_insights(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, provide concise and engaging Venture Insights for '{idea}' in '{location}'s venture ecosystem.
Each insight approx. 20-30 words. Focus on investment appeal/success factors. Markdown format.

Follow this structure exactly:

# **Venture Insights**

### **Market Opportunity & Scalability**
- **Insight:** [Assess if '{idea}' targets large/growing market in {location} or scalable from {location}. Addresses pain point attractive to investors? Approx. 20-30 words.]

### **Investment Potential ({location} Context)**
- **Insight:** [Likely investor interest (High/Medium/Low) for '{idea}' in {location}. Typical funding stages/amounts, valuation drivers. Plausible funding range. Approx. 20-30 words.]

### **Key Success Factors for Venture Funding**
- **Insight:** [2-3 critical factors for '{idea}' to attract VC in {location} (e.g., Traction, Team, Scale path). Approx. 20-30 words per factor.]

---
**IMPORTANT:** Tailor insights to {location}'s venture capital landscape. Plausible examples. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Venture Insights")

def generate_industry_insights(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, provide concise and engaging Industry Insights for '{idea}', focusing on trends, growth, competition in its sector in '{location}'.
Each insight/opportunity approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Industry Insights ({location})**

### **Current Trends & Opportunities in {location}**
[Each trend and opportunity approx. 20-30 words]
- **Trend 1:** [Key industry trend in {location}.] → **Opportunity:** [How '{idea}' could leverage it in {location}.]
- **Trend 2:** [Another relevant trend in {location}.] → **Opportunity:** [How '{idea}' could leverage it in {location}.]

### **Market Growth & Key Drivers in {location}**
- **Insight:** [Overall growth trajectory (Growing/Stable/Declining) of '{idea}'s sector in {location}. 1-2 key drivers. Approx. 20-30 words.]

### **Competitive Landscape & Benchmarks in {location}**
- **Insight:** [Competitive intensity in sector in {location}. 1-2 common KPIs for benchmarking in this industry. Approx. 20-30 words.]

---
**IMPORTANT:** Insights specific to '{idea}'s industry and '{location}' market. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Industry Insights")

def generate_catwoe_analysis(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, perform an engaging CATWOE Analysis for '{idea}' considering transformation and stakeholders in '{location}'.
Each point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **CATWOE Analysis**

### **Customers**
- **Who benefits?** [Primary beneficiaries of '{idea}' in {location} market. Approx. 20-30 words.]

### **Actors**
- **Who performs the transformation?** [Key people/roles carrying out '{idea}'s activities in {location}. Approx. 20-30 words.]

### **Transformation Process**
- **What is the core change?** [Fundamental input-to-output transformation '{idea}' performs. Input: ... Output: ... Approx. 20-30 words.]

### **Worldview (Weltanschauung)**
- **What is the bigger picture belief driving '{idea}'?** [Underlying assumption making '{idea}' meaningful, with {location} nuance. Approx. 20-30 words.]

### **Owner**
- **Who owns the process/system '{idea}'?** [Entity/role with ultimate authority over '{idea}'. Approx. 20-30 words.]

### **Environmental Constraints**
- **What external factors limit '{idea}' in {location}?** [1-2 key external constraints in {location} (e.g., Regulations, Infrastructure, Economy). Approx. 20-30 words per constraint.]

---
**IMPORTANT:** Frame CATWOE elements considering '{idea}' in '{location}'. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "CATWOE Analysis", max_tokens=700)

def generate_strategy(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, develop a high-level, engaging Strategic Plan outline for '{idea}', focusing on initial years and growth within/from '{location}'.
Each statement/goal/action/driver/risk/mitigation approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Strategic Plan**

### **Vision Statement**
[Brief, aspirational vision for '{idea}', mentioning {location} impact. Approx. 20-30 words.]

### **Mission Statement**
[Concise mission for '{idea}'s purpose and audience in {location}. Approx. 20-30 words.]

### **Short-Term Goals (1-2 Years)**
[Each goal and action approx. 20-30 words]
- **Goal 1 (Market Entry):** [e.g., Launch MVP in {location}, acquire first [N] customers.] Action: [Key action]
- **Goal 2 (Product Validation):** [e.g., Achieve PMF with {location} users.] Action: [Key action]
- **Goal 3 (Revenue):** [e.g., Reach initial revenue target from {location}.] Action: [Key action]

### **Long-Term Goals (3-5 Years)**
[Each goal and action approx. 20-30 words]
- **Goal 1 (Market Position):** [e.g., Top [N] player in [Niche] in {location}.] Action: [Key action]
- **Goal 2 (Expansion):** [e.g., Expand services, or enter [New Market].] Action: [Key action]
- **Goal 3 (Scalability):** [e.g., Achieve operational efficiency for scaling beyond {location}.] Action: [Key action]

### **Key Growth Drivers**
- [1-2 primary factors driving growth for '{idea}' from {location}. Approx. 20-30 words per driver.]

### **Risk Mitigation**
[Each risk and mitigation approx. 20-30 words]
- **Risk:** [Major strategic risk (e.g., Competitor reaction in {location}).] **Mitigation:** [High-level strategy.]
- **Risk:** [Another major risk (e.g., Failure to adapt to {location} market).] **Mitigation:** [Strategy.]

---
**IMPORTANT:** Goals/actions plausible for '{idea}' in '{location}'. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Strategy", max_tokens=900)

def generate_marketing_strategy(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, develop a concise, engaging Marketing Strategy outline for '{idea}' for launch and growth in '{location}'.
Each point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Marketing Strategy**

#### **Positioning, Messaging, and USP**
[Each approx. 20-30 words]
- **Positioning:** [How '{idea}' will be positioned in {location} market.]
- **Messaging:** [Core message emphasizing 1-2 key benefits for {location} audience.]
- **USP:** "[Concise, compelling USP tailored for {location}.]"

#### **Marketing Channels and Budget Allocation (Illustrative - Year 1)**
[Each channel description and cost approx. 20-30 words or brief]
- **Channel 1:** [Primary, effective channel for {location} (e.g., Ads on [Platform popular in {location}]).]
   **Budget Allocation:** [e.g., 40%] Est. Monthly Cost: [Plausible cost]
- **Channel 2:** [Secondary channel for {location} (e.g., Content Marketing for {location}).]
   **Budget Allocation:** [e.g., 30%] Est. Monthly Cost: [Plausible cost]
- **Channel 3:** [Tertiary channel (e.g., Local Partnerships in {location}).]
   **Budget Allocation:** [e.g., 20%] Est. Monthly Cost: [Plausible cost]
*(Note: Remaining 10% for PR/Experimentation)*

#### **Key Performance Indicators (KPIs) and Success Metrics**
[Each KPI and target approx. 20-30 words or brief]
- **KPI 1:** [e.g., Website Traffic from {location}] Target: [Plausible Target]
- **KPI 2:** [e.g., Lead Generation Rate ({location})] Target: [Plausible Target]
- **KPI 3:** [e.g., Customer Acquisition Cost (CAC) in {location}] Target: [< Amount]
- **KPI 4:** [e.g., Brand Mentions/Sentiment in {location}] Target: [Plausible Target]

---
**IMPORTANT:** Channels, costs, KPIs plausible for '{idea}' in '{location}'. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Marketing Strategy", max_tokens=700)

def generate_social_media_strategy(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, develop a concise, engaging Social Media Strategy outline for '{idea}', tailored for '{location}'.
Each rationale/pillar/tactic/KPI/budget point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Social Media Strategy**

## **Platform Selection & Rationale ({location} Focus)**
[Each rationale approx. 20-30 words]
- **Primary Platform:** [Most relevant platform for '{idea}' in {location}.]
    - **Rationale:** [Why key for {location} (e.g., User base, Content alignment).]
- **Secondary Platform:** [Another relevant platform for {location}.]
    - **Rationale:** [Its role (e.g., Reaches different segment).]

## **Content Pillars & Themes ({location} Relevance)**
[Each pillar theme approx. 20-30 words]
1.  **Pillar 1:** [e.g., Educational Content] - Theme: [Specific theme for '{idea}' and {location} audience.]
2.  **Pillar 2:** [e.g., Brand Story] - Theme: [Showcasing team/values, with {location} context.]
3.  **Pillar 3:** [e.g., Community Engagement] - Theme: [Highlighting {location} user success.]

## **Engagement Tactics ({location} Specific)**
- [2-3 specific tactics for {location} audience (e.g., Polls on {location} challenges, Local influencers). Each tactic approx. 20-30 words.]

## **Key Performance Indicators (KPIs)**
[Each KPI target approx. 20-30 words or brief]
- **Follower Growth ({location} Audience):** Target [Plausible %/number] monthly.
- **Engagement Rate (per post):** Target [Plausible %] average.
- **Website Referral Traffic (from Social - {location}):** Target [Plausible %] increase.
- **Lead/Conversion Rate (if applicable):** Track leads from social targeting {location}.

## **Paid Social Advertising (Optional Initial Plan)**
[Each point approx. 20-30 words]
- **Platform:** [Primary platform for ads targeting {location}.]
- **Targeting:** [Key targeting for {location} audience.]
- **Budget:** Est. initial monthly test budget: [Plausible amount].

---
**IMPORTANT:** Platform choices, content, tactics, budget plausible for '{idea}' in '{location}'. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Social Media Strategy", max_tokens=800)

def generate_slogan(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol} # Though not directly used, passed for consistency
Based on the overall context, generate 3 catchy, impactful, and engaging slogan options for '{idea}'.
Max 8 words per slogan. Brief reasoning (approx. 20-30 words per reasoning). Markdown format.

Follow this structure exactly:

# **Slogan Options**

### **Slogan Option 1:** [Generate Slogan 1]
   - *Reasoning:* [Briefly explain angle/benefit and appeal. Approx. 20-30 words.]

### **Slogan Option 2:** [Generate Slogan 2]
   - *Reasoning:* [Briefly explain. Approx. 20-30 words.]

### **Slogan Option 3:** [Generate Slogan 3]
   - *Reasoning:* [Briefly explain. Approx. 20-30 words.]

---
**IMPORTANT:** Slogans short, memorable, relevant to '{idea}'. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Slogan", max_tokens=400)

def generate_marketing_channels(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol} # Though not directly used, passed for consistency
Based on the overall context, identify and rank top 3-4 engaging Marketing Channels for '{idea}' in '{location}', prioritizing ROI and relevance.
Brief strategic notes (approx. 20-30 words per note). Markdown format.

Follow this structure exactly:

# **Marketing Channels (Ranked by Potential ROI for {location})**

## **1. [Top Channel Estimate, e.g., Targeted Digital Ads ({location}) ]**
**ROI Potential:** High
**Strategy:** [Paid/Organic/Hybrid]
**Notes:** [Why top for {location} (e.g., Targeting capability). Key platforms. Approx. 20-30 words.]
**Est. Budget Focus:** High %.

## **2. [Second Channel, e.g., Content Marketing ({location} Focus)]**
**ROI Potential:** Medium-High (Long-term)
**Strategy:** Organic
**Notes:** [Builds authority, attracts organic traffic in {location}. Approx. 20-30 words.]
**Est. Budget Focus:** Medium %.

## **3. [Third Channel, e.g., Strategic Partnerships ({location}) ]**
**ROI Potential:** Medium-High (Variable)
**Strategy:** Relationship-based
**Notes:** [Leverage existing audiences in {location}. Approx. 20-30 words.]
**Est. Budget Focus:** Low %.

## **4. [Fourth Channel (Optional), e.g., Local Events in {location}]**
**ROI Potential:** Medium
**Strategy:** Hybrid
**Notes:** [Builds brand presence in {location} community. Approx. 20-30 words.]
**Est. Budget Focus:** Low-Medium %.

---
**IMPORTANT:** Channels/rationale plausible for '{idea}' in '{location}'. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Marketing Channels")

def generate_mvp(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol} # Though not directly used, passed for consistency
Based on the overall context, define an engaging Minimum Viable Product (MVP) for '{idea}', for initial launch and learning in '{location}'.
Each point/feature/metric/timeline approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Minimum Viable Product (MVP)**

## **MVP Goal**
[Primary learning objective for MVP in {location} (e.g., Validate core value prop with {location} users). Approx. 20-30 words.]

## **Core Features (Minimal Set)**
[Each feature description approx. 20-30 words]
- **Feature 1:** [Absolute essential feature for core problem for initial {location} users.]
- **Feature 2:** [Another critical feature for core workflow.]
- **Feature 3 (Optional):** [Minimal feature hinting at key differentiator.]
- **Explicitly Excluded:** [1-2 significant features *not* in MVP (e.g., Advanced reporting). Approx. 20-30 words.]

## **Target Users (Initial {location} Segment)**
- **Description:** [Specific early adopter segment in {location} for MVP. Approx. 20-30 words.]

## **Key Metrics for Validation**
[Each metric and target approx. 20-30 words or brief]
- **Metric 1:** [e.g., Activation Rate ({location} cohort).] Target: [Plausible %]
- **Metric 2:** [e.g., Retention Rate (Week 1) for {location} users.] Target: [Plausible %]
- **Metric 3:** [e.g., Qualitative Feedback Score ({location} users).] Target: [e.g., >7/10]
- **Metric 4 (If applicable):** [e.g., Initial Conversion Rate ({location} testers).] Target: [Plausible %]

## **MVP Development & Launch**
[Each point approx. 20-30 words]
- **Timeline:** Estimated [Number] weeks/months.
- **Launch Approach:** [e.g., Closed Beta in {location}.]

---
**IMPORTANT:** Focus on *minimum* to learn from {location} market. Features/metrics specific and measurable. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "MVP Definition", max_tokens=700)

def generate_usp(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol} # Though not directly used, passed for consistency
Based on the overall context, define a clear, compelling, and engaging Unique Selling Proposition (USP) for '{idea}', tailored for '{location}' market.
Each point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Unique Selling Proposition (USP)**

## **Target Audience & Problem ({location} Focus)**
[Each point approx. 20-30 words]
- **For:** [Primary target audience segment in {location}.]
- **Who Struggle With:** [Core problem experienced by this audience in {location}.]

## **Our Solution: '{idea}'**
- **Provides:** [Primary solution/capability of '{idea}'. Approx. 20-30 words.]

## **Key Differentiator(s) (vs. {location} Alternatives)**
[Each point approx. 20-30 words]
- **Unlike:** [Main category of competitors/alternatives in {location}.]
- **'{idea}' Uniquely Offers:** [1-2 core elements making '{idea}' different and better for {location} audience.]

## **Primary Benefit(s) for {location} Audience**
- **Resulting In:** [Main quantifiable/qualitative benefit(s) for users in {location}. Approx. 20-30 words.]

## **USP Statement (Synthesis)**
- **"{idea} helps [Target Audience in {location}] achieve [Primary Benefit] by providing [Unique Differentiator], unlike [Competitor Category in {location}] which often [Competitor Weakness]."** *(Craft concise sentence, approx. 20-30 words)*

---
**IMPORTANT:** USP must articulate *why* customer in '{location}' chooses '{idea}'. Differentiators/benefits specific for {location}. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "USP", max_tokens=600)

def generate_customer_persona(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, create a detailed and engaging Customer Persona for the ideal primary customer of '{idea}' in '{location}'.
Each demographic/goal/challenge/behavior point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Customer Persona**

## **[Persona Name]**
*(Relatable name, e.g., "Anna Chen, {location} Small Business Owner")*

## **Demographics**
[Each point approx. 20-30 words or brief]
- **Age Range:** [Plausible range]
- **Location:** [Specific area/type within {location}]
- **Role/Occupation:** [Specific role in {location}]
- **Income Level (Approx.):** [Plausible range, primary in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalent.]
- **Education:** [Typical level for role in {location}]

## **Goals & Motivations**
[Each goal/motivation approx. 20-30 words]
- **Primary Goal:** [What persona wants to achieve related to '{idea}'.]
- **Secondary Goal:** [Another relevant goal.]
- **Motivated By:** [What drives them (e.g., Recognition, Success, Balance).]

## **Challenges & Pain Points ({location} Context)**
[Each challenge/fear approx. 20-30 words]
- **Primary Challenge:** [Main frustration '{idea}' solves, in {location} context.]
- **Secondary Challenge:** [Another relevant pain point.]
- **Fears:** [Potential negative outcomes worrying them.]

## **Behavior & Technology Usage**
[Each point approx. 20-30 words]
- **Information Sources:** [Where they get info (e.g., Local publications, {location}-specific forums).]
- **Tech Savviness:** [e.g., Highly tech-savvy, Early adopter.]
- **Preferred Communication:** [e.g., Email, Channels common in {location}.]
- **Social Media:** [Platforms actively used (mention {location}-specific if relevant).]

## **How '{idea}' Helps**
- [Briefly explain how '{idea}' directly addresses this persona's goals and challenges in {location} context. Approx. 20-30 words.]

---
**IMPORTANT:** Details create realistic picture of target customer in '{location}'. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Customer Persona", max_tokens=800)

def generate_finances(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, provide a high-level, engaging Financial Overview for '{idea}' (initial 1-3 years) in '{location}'.
Each point/projection/cost/metric approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Financial Overview (Preliminary)**

## **Revenue Model**
[Each point approx. 20-30 words]
- **Primary Stream:** [Main way '{idea}' generates revenue in {location}.]
- **Pricing Strategy:** [Approach for {location}.] Sample Price: [Plausible starting price].
- **Year 1 Revenue Projection ({location}):** [Plausible estimate.]
- **Year 3 Revenue Projection ({location} & early expansion):** [Plausible estimate.]

## **Cost Structure (Key Annual Estimates - Year 1)**
[Each cost item approx. 20-30 words or brief value]
- **COGS / Direct Costs:** [Estimate % Revenue or fixed amount.]
- **Operating Expenses (OpEx):**
  - **Sales & Marketing ({location} launch):** [Plausible estimate.]
  - **R&D (Initial Product):** [Plausible estimate.]
  - **G&A (Rent, Salaries for {location} ops):** [Plausible estimate.]
- **Total Estimated Year 1 Costs:** [Plausible sum.]

## **Profitability & Key Metrics**
[Each point approx. 20-30 words or brief value]
- **Gross Margin:** [Estimated %.]
- **Profitability Timeline:** [Estimate break-even (e.g., Q4 Year 2) for {location} launch.]
- **Key Financial Metric:** [e.g., Target CAC for {location}.]
- **Key Financial Metric:** [e.g., Target LTV for {location} (LTV > 3x CAC).]

## **Funding Needs & Strategy**
[Each point approx. 20-30 words]
- **Funding Required (Seed):** [Estimate for ~18-24 months runway.]
- **Use of Funds:** [Brief breakdown %: Product Dev, S&M ({location}), Ops.]
- **Potential Funding Sources for {location}:** [1-2 plausible sources for {location} (e.g., Local Angel Network).]

---
**IMPORTANT:** Plausible figures for early-stage venture '{idea}' in '{location}'. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Financial Overview", max_tokens=900)

def generate_go_to_market_strategy(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, develop a concise, engaging Go-To-Market (GTM) Strategy outline for launching '{idea}' in '{location}'.
Each point/phase/channel/tactic/metric approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Go-To-Market Strategy ({location})**

## **Target Market (Initial Launch)**
[Each point approx. 20-30 words]
- **Segment:** [Define the specific niche or early adopter segment within {location} to target first (reference Persona if available).]
- **Value Proposition:** [Reiterate the core value proposition tailored for this initial {location} segment.]

## **Launch Strategy & Timeline**
[Each point approx. 20-30 words]
- **Approach:** [e.g., Phased rollout starting with Closed Beta in {location}, Followed by Public Launch targeting key {location} cities/regions.]
- **Key Phases:**
    - **Pre-Launch ([Duration]):** [Activities: e.g., Build waitlist in {location}, Secure initial local partners.]
    - **MVP Launch ([Target Quarter/Date]):** [Activities: e.g., Onboard Beta users from {location}, Gather feedback.]
    - **Public Launch ([Target Quarter/Date]):** [Activities: e.g., Execute primary marketing campaigns in {location}.]

## **Sales & Distribution Channels ({location})**
[Each channel/model point approx. 20-30 words]
- **Primary Channel:** [e.g., Direct Online Sales via localized website for {location}.]
- **Secondary Channel:** [e.g., Inside Sales team focused on {location} SMEs, Partnerships with local {location} consultants/agencies.]
- **Pricing Model for {location}:** [Confirm pricing model with currency displayed.]

## **Marketing & Customer Acquisition ({location} Focus)**
[Each tactic and budget point approx. 20-30 words]
- **Awareness:** [Key tactics for generating awareness in {location} (e.g., {location}-targeted PR, Ads on [Platform popular in {location}]).]
- **Consideration:** [Key tactics for engaging potential customers (e.g., Webinars addressing {location} market needs, Downloadable guides, Free trial).]
- **Conversion:** [Key tactics for converting leads (e.g., Clear Call-to-Actions, Limited-time launch offers for {location}, Sales demos).]
- **Initial Marketing Budget:** Estimated amount for first 6 months focused on {location} launch.

## **Success Metrics (First 6-12 Months in {location})**
[Each metric approx. 20-30 words or brief value]
- **Reach:** [e.g., Website visitors from {location}.]
- **Acquisition:** [e.g., Number of new customers acquired in {location}, CAC.]
- **Activation:** [e.g., % of users completing key onboarding step.]
- **Revenue:** [e.g., Monthly Recurring Revenue (MRR) generated from {location} customers.]
- **Retention:** [e.g., Customer Churn Rate within {location} cohort.]

---
**IMPORTANT:** Strategy practical and specific for '{idea}' in '{location}'. Plausible details/metrics. Financials primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Go-To-Market Strategy", max_tokens=900)

def generate_competitive_analysis(idea, location, overall_summary, target_currency_symbol):
    prompt = f"""
**Overall Business Context Provided:**
{overall_summary}

---
TARGET_CURRENCY: {target_currency_symbol}
Based on the overall context, conduct a concise, engaging Competitive Analysis for '{idea}', focusing on key competitors in '{location}' market.
Each strength/weakness/pricing/limitation/differentiation point approx. 20-30 words. Markdown format.

Follow this structure exactly:

# **Competitive Analysis ({location})**

## **Direct Competitors in {location}**
[Each competitor point approx. 20-30 words or short list]
- **Competitor 1:** [Plausible direct competitor with presence in {location}.]
    - **Strengths:** [List 1-2 key strengths relevant in {location}.]
    - **Weaknesses:** [List 1-2 key weaknesses relevant in {location}.]
    - **Pricing Model:** [Describe briefly.] Est. Price: [Amount].
- **Competitor 2:** [Name another plausible direct competitor in {location}.]
    - **Strengths:** [List 1-2 strengths.]
    - **Weaknesses:** [List 1-2 weaknesses.]
    - **Pricing Model:** [Describe briefly.] Est. Price: [Amount].

## **Indirect Competitors / Alternatives in {location}**
[Each point approx. 20-30 words]
- **Type:** [e.g., Traditional methods, Manual processes.]
    - **Why a substitute?** [Briefly explain why customers in {location} might use this instead.]
    - **Key Limitation:** [What's the main drawback compared to '{idea}' for {location} users?]

## **Competitive Advantage for '{idea}' in {location}**
[Each point approx. 20-30 words]
- **Differentiation:** [Reiterate 1-2 key points from USP how '{idea}' stands out against these specific {location} competitors/alternatives.]
- **Strategic Positioning:** [Based on the analysis, how should '{idea}' position itself for success in {location}?]

---
**IMPORTANT:** Focus only on competitors and alternatives relevant within the '{location}' market. Pricing primarily in {target_currency_symbol}. If {target_currency_symbol} != USD, add USD equivalents. Valid Markdown. No ```markdown blocks. Align with context and word limits.
""".strip()
    return _generate_content(prompt, "Competitive Analysis", max_tokens=700)


# --- Main Orchestration Function (Context Unifier) ---
def generate_free_report_content(idea, location):
    """
    Generates a report. First, an overall context summary and target currency are determined.
    These are then passed to all individual section generators to ensure cohesive output.
    """
    if not idea or not isinstance(idea, str):
        return {"error": "Invalid 'idea' input."}
    if not location or not isinstance(location, str):
        return {"error": "Invalid 'location' input."}

    print(f"Starting context-unified report generation for:\n  Idea: '{idea}'\n  Location: '{location}'")
    start_time_total = time.time()

    # 1. Determine Target Currency using LLM
    target_currency_symbol = get_currency_via_llm(location)
    # This function already prints its progress/result.

    # 2. Generate Overall Context Summary
    print("Generating overall context summary...")
    try:
        overall_summary_content = generate_overall_context_summary(idea, location)
        if "### Error Generating Section" in overall_summary_content: # Basic check for error placeholder
            print(f"   ✗ Failed to generate overall context summary. LLM Output: {overall_summary_content[:200]}...")
            return {
                "error": "Failed to generate the crucial overall context summary. Report generation halted.",
                "details": overall_summary_content,
                "metadata": {"idea": idea, "location": location, "target_currency": target_currency_symbol, "report_generated_at": datetime.datetime.now().isoformat(), "total_generation_time_seconds": round(time.time() - start_time_total, 2)}
            }
        print(f"   ✓ Overall context summary generated.")
    except Exception as e:
        print(f"   ✗ Exception during overall context summary generation: {e}")
        return {
            "error": f"Exception while generating overall context summary: {str(e)}",
            "metadata": {"idea": idea, "location": location, "target_currency": target_currency_symbol, "report_generated_at": datetime.datetime.now().isoformat(), "total_generation_time_seconds": round(time.time() - start_time_total, 2)}
        }

    # Define all tasks (section generation functions)
    # The boolean indicates if the function needs the target_currency_symbol
    tasks_to_run = {
        "executive_summary": (generate_executive_summary, True),
        "problem_validation": (generate_problem_validation, True),
        "market_analysis": (generate_market_analysis, True),
        "market_size_estimation": (generate_market_size_estimation, True),
        "swot_analysis": (generate_swot_analysis, True),
        "vrio_analysis": (generate_vrio_analysis, True),
        "pestel_analysis": (generate_pestel_analysis, True),
        "porters_five_forces": (generate_porters_five_forces, True),
        "competitive_analysis": (generate_competitive_analysis, True),
        "usp": (generate_usp, True),
        "customer_persona": (generate_customer_persona, True),
        "mvp": (generate_mvp, True),
        "strategy": (generate_strategy, True),
        "go_to_market_strategy": (generate_go_to_market_strategy, True),
        "marketing_strategy": (generate_marketing_strategy, True),
        "marketing_channels": (generate_marketing_channels, True),
        "social_media_strategy": (generate_social_media_strategy, True),
        "slogan": (generate_slogan, True),
        "finances": (generate_finances, True),
        "venture_insights": (generate_venture_insights, True),
        "industry_insights": (generate_industry_insights, True),
        "catwoe_analysis": (generate_catwoe_analysis, True),
    }

    report_sections_content = {}
    generation_metadata = {}
    futures = {}
    max_workers = 22 # Adjust based on API limits and system capability

    print(f"\nRunning {len(tasks_to_run)} sections in parallel (max_workers={max_workers}), using overall context and target currency {target_currency_symbol}...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for name, (func, needs_currency) in tasks_to_run.items():
            if needs_currency: # All current functions use it
                future = executor.submit(func, idea, location, overall_summary_content, target_currency_symbol)
            else: # Fallback, though not currently used
                future = executor.submit(func, idea, location, overall_summary_content)
            futures[future] = name

        for future in concurrent.futures.as_completed(futures):
            task_name = futures[future]
            try:
                result_obj = future.result()
                if isinstance(result_obj, dict) and 'content' in result_obj:
                    report_sections_content[task_name] = result_obj['content']
                    generation_metadata[task_name] = {
                        "time_taken": round(result_obj.get('time_taken', 0), 2),
                        "input_tokens": result_obj.get('input_tokens', 0),
                        "output_tokens": result_obj.get('output_tokens', 0)
                    }
                else:
                    error_msg = f"Unexpected result format for {task_name}. Type: {type(result_obj)}"
                    print(f"   ✗ {error_msg}")
                    report_sections_content[task_name] = f"### Error processing result format for section: {task_name}\n\n```\n{error_msg}\n```"
                    generation_metadata[task_name] = {"error": error_msg, "time_taken": 0, "input_tokens": 0, "output_tokens": 0}
            except Exception as e:
                error_msg = f"Exception processing result for {task_name}: {type(e).__name__} - {str(e)}"
                print(f"   ✗ {error_msg}")
                report_sections_content[task_name] = f"### Error retrieving or processing result: {task_name}\n\n```\n{error_msg}\n```"
                generation_metadata[task_name] = {"error": error_msg, "time_taken": 0, "input_tokens": 0, "output_tokens": 0}

    end_time_total = time.time()    
    total_duration = end_time_total - start_time_total
    print(f"\nFinished report generation in {total_duration:.2f} seconds.")

    final_report_content = {"overall_context_summary": overall_summary_content}
    # Use the order from tasks_to_run for the final report structure
    for section_key, _ in tasks_to_run.items(): # Ensure defined order
        final_report_content[section_key] = report_sections_content.get(section_key, f"### Error: Content for section '{section_key}' not found.")
    
    sorted_generation_metadata = dict(sorted(generation_metadata.items()))

    final_output = {
        "metadata": {
            "idea": idea,
            "location": location,
            "target_currency": target_currency_symbol,
            "report_generated_at": datetime.datetime.now().isoformat(),
            "total_generation_time_seconds": round(total_duration, 2),
            "openai_deployment": AZURE_DEPLOYMENT_NAME,
            "section_generation_details": sorted_generation_metadata
        },
        "free_report_content": final_report_content
    }
    return final_output

# --- Example Usage ---
if __name__ == '__main__':
    input_idea = input("Enter the business idea: ")
    input_location = input("Enter the target location: ")

    report_data = generate_free_report_content(input_idea, input_location)

    if "error" in report_data:
        print(f"\nCritical Error: {report_data['error']}")
        if "details" in report_data:
            print(f"Details: {report_data['details']}")
    else:
        sanitized_idea = re.sub(r'[^\w\-]+', '_', input_idea)[:50]
        sanitized_location = re.sub(r'[^\w\-]+', '_', input_location)[:30]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Engaging_Business_Report_{sanitized_idea}_{sanitized_location}_{timestamp}.json"

        try:
            print(f"\nSaving report to JSON file: {filename}")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=4, ensure_ascii=False)
            print(f"✓ Report successfully saved.")

            print("\nGenerated Sections Included in 'report_content':")
            if "report_content" in report_data:
                for section_key in report_data["report_content"].keys():
                     print(f"- {section_key}")
            else:
                print("No report content found in the output.")

        except IOError as e:
            print(f"\n✗ Error saving report to file '{filename}': {e}")
        except Exception as e:
            print(f"\n✗ An unexpected error occurred during saving: {e}")