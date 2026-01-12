from langchain_openai import AzureChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv
import os
import time  # Added for timing measurements

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
    max_tokens=500
)

def get_detailed_problem_statement(idea):
    """Returns dictionary with keys: content, time_taken, input_tokens, output_tokens"""
    start_time = time.time()
    print("The user-given idea is: ", idea)
    
    prompt = f"""Provide a detailed and well-structured problem statement based on the following idea: '{idea}'. 
    Break it down into smaller problems if applicable, and explain what the user is aiming to solve or accomplish. 
    Be clear and concise in identifying key components and objectives of the problem and formulate everything under 200 words."""
    
    try:
        messages = [
            SystemMessage(content="You are a business analyst specializing in problem decomposition."),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        # print(response)
        
        result = {
            "content": response.content,
            "time_taken": time.time() - start_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"]
        }
        return result
    except Exception as e:
        result = {
            "content": f"Error generating problem statement: {str(e)}",
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
        }
        return result
    

def get_required_evaluation_headings(problem_statement):
    """Returns dictionary with keys: headings, time_taken, input_tokens, output_tokens"""
    start_time = time.time()
    print("Processing problem statement:", problem_statement[:50] + "...")

    prompt = f"""Generate ONLY evaluation criteria headings for analyzing this business concept: '{problem_statement}'
    Focus on:
    - Market viability
    - Technical feasibility
    - Business model robustness
    - Risk assessment
    - Strategic alignment
    - Identifying Key Competitors
    
    Exclude:
    - Team details
    - Funding requests
    - Pitch elements
    - Timelines
    
    Format as numbered list without descriptions and generate atleast 10 headings and can be more than that.
    
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

def generate_queries_per_heading(problem_statement, evaluation_headings):
    """Returns dictionary with keys: queries, time_taken, input_tokens, output_tokens"""
    start_time = time.time()
    print(f"Generating 3 queries per heading for: {problem_statement[:60]}...")
    
    prompt = f"""Create 3 distinct Google search queries for EACH evaluation criteria below to find validation data.
    Problem: {problem_statement}
    
    For each of these criteria:
    {chr(10).join(evaluation_headings)}
    
    Generate queries that:
    1. Target different data types (market reports, papers, case studies)
    2. Use good differentiating keywords related to the idea
    4. Focus on measurable metrics and validation data
    
    Format as:
    [Heading]: 
    1. "query1"
    2. "query2" 
    3. "query3"
    ..."""

    try:
        # response = openai.ChatCompletion.create(
        #     engine=DEPLOYMENT_NAME,
        #     messages=[
        #         {"role": "system", "content": "You are a research assistant specialized in multi-angle data validation."},
        #         {"role": "user", "content": prompt}
        #     ],
        #     temperature=0.4,
        #     max_tokens=1000
        # )
        messages = [
            SystemMessage(content="You are a research assistant specialized in multi-angle data validation."),
            HumanMessage(content=prompt),
        ]

        response = llm.invoke(messages)

        raw_output = response.content.strip()
        
        # Parse response
        queries_dict = {}
        current_heading = None
        
        for line in raw_output.split('\n'):
            line = line.strip()
            
            if line.endswith(':'):
                current_heading = line[:-1].strip()
                queries_dict[current_heading] = []
            
            elif line.startswith(('1.', '2.', '3.', '"')):
                query = line.split('. ', 1)[-1].strip(' "')
                if current_heading and query:
                    queries_dict[current_heading].append(query[:256])
        
        # Validate query counts
        for heading in queries_dict:
            queries_dict[heading] = queries_dict[heading][:3]
            while len(queries_dict[heading]) < 3:
                queries_dict[heading].append(f"{heading} {problem_statement} research data site:.edu")

        return {
            "queries": queries_dict,
            "time_taken": time.time() - start_time,
            "input_tokens": response.response_metadata["token_usage"]["prompt_tokens"],
            "output_tokens": response.response_metadata["token_usage"]["completion_tokens"]
        }
    
    except Exception as e:
        return {
            "queries": {
                heading: [
                    f'"{heading}" "{problem_statement}" market data ',
                    f'"{heading}" analysis {problem_statement.split()[0]} technical report',
                    f'Recent studies on "{heading}" in {problem_statement}'
                ] for heading in evaluation_headings
            },
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
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




idea = "Develop a tool for automating social media posts for businesses"
result = get_detailed_problem_statement(idea)
print(result)
