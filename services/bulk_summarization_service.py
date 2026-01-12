import time
import json
# import openai
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import multiprocessing
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# Load environment variables
load_dotenv()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")  # Name of your deployed model (e.g., "gpt-4")
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

if not (AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and DEPLOYMENT_NAME):
    raise ValueError("Azure OpenAI configuration not found in the .env file.")
# Initialize LangChain's AzureChatOpenAI model
llm = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    openai_api_version=AZURE_OPENAI_API_VERSION,
    deployment_name=DEPLOYMENT_NAME,
    openai_api_key=AZURE_OPENAI_API_KEY,
    temperature=0.7,
    max_tokens=2000
)


# # Configure the Azure OpenAI API
# openai.api_type = "azure"
# openai.api_key = AZURE_OPENAI_API_KEY
# openai.api_base = AZURE_OPENAI_ENDPOINT
# openai.api_version = "2024-08-01-preview"  # Adjust the version as needed

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
    Format the summary in clear, concise paragraphs without markdown. And generate the summary in less than 500 words."""
    
    try:
        # response = openai.ChatCompletion.create(
        #     engine=DEPLOYMENT_NAME,
        #     messages=[
        #         {"role": "system", "content": "You are a professional content analyst specializing in technical summarization."},
        #         {"role": "user", "content": prompt}
        #     ],
        #     temperature=0.5,  # Lower temperature for more factual accuracy
        #     max_tokens=900
        # )

        messages = [
            SystemMessage(content="You are a professional content analyst specializing in technical summarization."),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)


        return {
            "content": response.content,
            # "time_taken": round(time.time() - start_time, 4),  # More precise time
            # "input_tokens": response.response_metadata['token_usage']['prompt_tokens'],
            # "output_tokens": response.response_metadata['token_usage']['completion_tokens']
        }
    except Exception as e:
        return {
            "content": f"Error generating summary: {str(e)}",
            # "time_taken": round(time.time() - start_time, 4),
            # "input_tokens": 0,
            # "output_tokens": 0
        }

def generate_batch_queries(results):
    """
    Generates a list of queries with metadata from the cleaned_content of each item in the data.
    Args:
      results: A dictionary containing metadata and results.
    Returns:
      A list of dictionaries, each containing cleaned_content and its metadata.
    """
    text_content = []
    if "results" in results and isinstance(results["results"], list):
        for result in results["results"]:
            if "cleaned_content" in result:
                text_content.append({
                    "cleaned_content": result["cleaned_content"],
                    "category": result.get("category", ""),  # Default to empty string if missing
                    "status": result.get("status", ""),
                    "term": result.get("term", ""),
                    "url": result.get("url", "")
                })
    return text_content

def parallel_summarization_processing(results):
    """
    Runs the summarization in parallel while keeping track of metadata.
    Args:
      results: A dictionary containing website content and metadata.
    Returns:
      A dictionary containing metadata and summarized results.
    """
    start_time = time.time()  # Track total processing time
    text_content = generate_batch_queries(results)
    
    summaries = []
    total_input_tokens = 0
    total_output_tokens = 0
    
    # Dynamically set max_workers based on CPU cores
    max_workers = 120  # Optimal thread count
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_content = {executor.submit(summarize_website_content, item["cleaned_content"]): item for item in text_content}
        
        for future in as_completed(future_to_content):
            item = future_to_content[future]
            try:
                summary = future.result()
                summaries.append({
                    "category": item["category"],
                    "status": item["status"],
                    "term": item["term"],
                    "url": item["url"],
                    "summary": summary["content"],
                    # "time_taken": summary["time_taken"],
                    # "input_tokens": summary["input_tokens"],
                    # "output_tokens": summary["output_tokens"]
                })
                # Accumulate token counts
                # total_input_tokens += summary["input_tokens"]
                # total_output_tokens += summary["output_tokens"]
            except Exception as e:
                summaries.append({
                    "category": item["category"],
                    "status": item["status"],
                    "term": item["term"],
                    "url": item["url"],
                    "summary": f"Error: {str(e)}",
                    # "time_taken": 0,
                    # "input_tokens": 0,
                    # "output_tokens": 0
                })
    
    total_time = round(time.time() - start_time, 4)
    return {
        "metadata": {
            "processed_content_count": len(summaries),
            "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_time_taken": total_time,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens
        },
        "summarized_results": summaries
    }



# # Example usage
# sample_results = {
#     "results": [
#         {
#             "cleaned_content": "AI is transforming industries by automating tasks and analyzing data...",
#             "category": "Technology",
#             "status": "Published",
#             "term": "AI",
#             "url": "https://example.com/ai-industry"
#         },
#         {
#             "cleaned_content": "Healthcare advancements with AI are leading to better diagnostics...",
#             "category": "Healthcare",
#             "status": "Draft",
#             "term": "Medical AI",
#             "url": "https://example.com/health-ai"
#         }
#     ]
# }

# final_output = parallel_summarization_processing(sample_results)
# print(json.dumps(final_output, indent=4))
