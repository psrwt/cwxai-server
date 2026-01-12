from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from dotenv import load_dotenv
import os
import time  # Added for timing measurements
import re

# Load environment variables
load_dotenv()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

# Initialize LangChain's AzureChatOpenAI model
llm = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    openai_api_version=AZURE_OPENAI_API_VERSION,
    deployment_name=DEPLOYMENT_NAME,
    openai_api_key=AZURE_OPENAI_API_KEY,
    temperature=0.7,
    max_tokens=2000
)

def get_detailed_problem_statement(idea, location):
    """Returns dictionary with keys: content, time_taken, input_tokens, output_tokens"""
    start_time = time.time()
    print("The user-given idea is: ", idea)

    if not location:
        location = "entire world"

        
    print(location)
    
    prompt = f"""Provide a comprehensive and structured problem statement for the given idea: '{idea}'.  
    If the specified location : '{location}' is relevant to the problem, incorporate localized insights  
    to make the statement more contextual and applicable.  

    - Clearly define the core problem being addressed.  
    - Break it down into smaller challenges or pain points if applicable.  
    - Explain why this problem is significant and who is affected by it.  
    - Highlight any industry-specific or vertical-related aspects that make the problem unique.  
    - Keep the explanation under 250 words while ensuring clarity, depth, and personalization.
    
    """
    
    try:
        messages = [
            SystemMessage(content="You are a business analyst specializing in problem decomposition."),
            HumanMessage(content=prompt)
        ]
        # print(messages)
        
        response = llm.invoke(messages)
        # print(response)
        
        result = {
            "content": response.content,
            "time_taken": time.time() - start_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"]
        }
        print(result)
        return result
    except Exception as e:
        result = {
            "content": f"Error generating problem statement: {str(e)}",
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
        }
        return result
    

def re_evaluate_problem_statement(idea, title, additional_input, current_response, location):
    """Generates a detailed problem statement, incorporating title, additional input, and previous response."""
    start_time = time.time()
    print(f"The user-given idea is: {idea}")
    
    # Construct an optimized prompt using all relevant information
    prompt = f"""The user has provided the following idea: '{idea}'.
    The title of the idea is: '{title}'.
    Additional context provided: '{additional_input}'.
    The current response is: '{current_response}'.
    
    Consider the relevance of the location ('{location}') to this idea. If it plays a crucial role, incorporate localized challenges, market conditions, or regulations that might impact the problem.
    
    Based on these inputs, re-evaluate and refine the problem statement for better clarity, accuracy, and depth. 
    - Provide a more structured and comprehensive understanding of the problem.
    - Break it down into smaller, actionable components if necessary.
    - Ensure the response is insightful, focused, and actionable.
    - Keep the problem statement clear and concise, limited to a maximum of 250 words."""


    try:
        # Construct the prompt for the AI model
        messages = [
            SystemMessage(content="You are a business analyst specializing in problem decomposition."),
            HumanMessage(content=prompt)
        ]
        
        # Call the language model for the re-evaluation
        response = llm.invoke(messages)
        
        # Process and return the result in the desired format
        result = {
            "content": response.content,
            "time_taken": time.time() - start_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"]
        }
        return result
    except Exception as e:
        # In case of error, return an error message
        result = {
            "content": f"Error generating re-evaluated problem statement: {str(e)}",
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
        }
        return result


def get_required_evaluation_headings(problem_statement, location):
    """Returns dictionary with keys: headings, time_taken, input_tokens, output_tokens"""
    start_time = time.time()
    print("Processing problem statement:", problem_statement[:50] + "...")
    print(location)

    prompt = f"""Generate ONLY evaluation criteria headings for analyzing this business concept: '{problem_statement}'.
    
    If the location ('{location}') is relevant to the business concept, incorporate location-specific factors such as market conditions, regulatory landscape, competition, or operational constraints for both location and global aspects.
    
    Focus on key evaluation aspects:
    - Market viability
    - Technical feasibility
    - Business model robustness
    - Risk assessment
    - Strategic alignment
    - Identifying key competitors
    - Location-based challenges (if applicable)

    Exclude:
    - Team details
    - Funding requests
    - Pitch elements
    - Timelines

    Format as a **numbered list** without descriptions.  
    Generate **at least 10 headings** (can be more, but a maximum of 12).  

    Example:
    1. Problem Validation  
    2. Solution Feasibility Analysis  
    3. Market Size Estimation  
    4. Competitive Landscape Assessment  
    5. Revenue Model Viability"""


    try:
        messages = [
            SystemMessage(content="You are an innovation evaluation framework expert. You help break down ideas into measurable assessment criteria."),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        
        # headings = response.content.strip().split("\n")
        raw_output = response.content.strip()
        
        # Process headings
        evaluation_headings = [
            line.split('. ', 1)[-1].strip(' -*•')
            for line in raw_output.split('\n')
            if line.strip() and not any(excluded_word in line.lower() 
                for excluded_word in ['team', 'milestone', 'timeline', 'funding', 'pitch'])
        ]
        
        return {
            "headings": evaluation_headings[:12],
            "time_taken": time.time() - start_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"]
        }
    except Exception as e:
        return {
            "headings": [
                "Core Problem Analysis",
                "Solution Feasibility",
                "Market Validation",
                "Competitive Differentiation",
                "Business Model Sustainability",
                "Implementation Complexity",
                "Risk Assessment",
                "ROI Potential",
                "Scalability Analysis",
                "Technology Readiness"
            ],
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
        }

import time
import json

def generate_queries_per_heading(problem_statement, evaluation_headings, location):
    """
    Returns a dictionary with keys: queries, time_taken, input_tokens, output_tokens.
    Instructs the LLM to output a valid JSON object with each evaluation heading as a key,
    and each value is a list of exactly 3 queries.
    """
    start_time = time.time()
    print(f"Generating 3 queries per heading for: {problem_statement[:60]}...")

    # One-shot JSON example for clarity.
    example_json = '''{
        "Market Size Estimation": [
            "Global AI market growth trends 2025",
            "AI adoption rates by industry site:statista.com",
            "Regional AI funding trends site:crunchbase.com"
        ],
        "Competitive Landscape Assessment": [
            "AI startup competitors in 2025",
            "Major players in AI industry site:forbes.com",
            "AI market share comparison 2025 site:gartner.com"
        ]
    }'''

    prompt = f"""Create 3 distinct Google search queries for EACH evaluation criterion below to find validation data, and output the result as a valid JSON object.

**Problem Statement:** {problem_statement}

**Evaluation Criteria:**
{chr(10).join(evaluation_headings)}

If the location ('{location}') is relevant, include location-specific queries for applicable headings.

**Query Guidelines:**
1. Diversify query types (e.g., market reports, research papers, case studies, industry trends, government regulations).
2. Use well-differentiated and precise keywords.
3. Ensure each criterion gets exactly 3 queries.
4. The output must be valid JSON.

**Example Output:**
{example_json}

**Output Format:**
{{
    "<Heading>": ["query1", "query2", "query3"],
    "<Heading>": ["query1", "query2", "query3"],
    ...
}}
"""

    try:
        messages = [
            SystemMessage(content="You are a research assistant specialized in multi-angle data validation."),
            HumanMessage(content=prompt),
        ]
        response = llm.invoke(messages)
        raw_output = response.content.strip()
        print("Raw JSON Output from LLM:\n", raw_output)

        # --- Clean the raw_output from markdown formatting ---
        # Remove markdown code block delimiters (``` or ```json)
        if raw_output.startswith("```"):
            lines = raw_output.split("\n")
            # Remove the first line if it's a markdown code block marker.
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove the last line if it's a markdown code block marker.
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_output = "\n".join(lines).strip()
        # ----------------------------------------------------------

        # Check if raw_output is empty after cleaning.
        if not raw_output:
            raise ValueError("LLM returned an empty response.")

        # Parse the JSON output.
        queries_dict = json.loads(raw_output)

        # Validate that each evaluation heading has exactly 3 queries.
        for heading in evaluation_headings:
            # Ensure the heading exists and is a list.
            if heading not in queries_dict or not isinstance(queries_dict[heading], list):
                queries_dict[heading] = []
            # Limit to 3 queries, or pad with fallback queries.
            queries = queries_dict[heading][:3]
            while len(queries) < 3:
                queries.append(f"{heading} research data site:.edu")
            queries_dict[heading] = queries

        elapsed_time = time.time() - start_time

        return {
            "queries": queries_dict,
            "time_taken": elapsed_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"],
        }

    except Exception as e:
        print(f"Error generating queries in JSON format: {e}")
        # Fallback: default queries if JSON parsing or LLM invocation fails.
        fallback_queries = {
            heading: [
                f'"{heading}" market data',
                f'"{heading}" analysis technical report',
                f'Recent studies on "{heading}" '
            ] for heading in evaluation_headings
        }
        return {
            "queries": fallback_queries,
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0,
        }

def summarize_website_content(text_content):
    """Returns dictionary with keys: content, time_taken, input_tokens, output_tokens"""
    start_time = time.time()
    
    prompt = f"""Analyze and summarize the following website content while preserving all key contextual information:
    
    {text_content}
    
    Create a comprehensive summary that:
    1. Captures the main purpose and key messages
    2. Highlights essential data points and statistics
    3. Identifies important entities (names, places, products)
    4. Preserves technical terms and domain-specific concepts
    5. Maintains contextual relationships between ideas
    6. Keeps critical quantitative information
    Format the summary in clear, concise paragraphs without markdown."""
    
    try:
        messages = [
            SystemMessage(content="You are a professional content analyst specializing in technical summarization."),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        
        return {
            "content": response.content,
            "time_taken": time.time() - start_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"]
        }
    except Exception as e:
        return {
            "content": f"Error generating summary: {str(e)}",
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
        }


