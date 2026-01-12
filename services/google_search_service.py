import requests
from dotenv import load_dotenv
import os
import concurrent.futures
import time
import json

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_SEARCH_API_KEY")

def get_top_links(api_key, search_engine_id, query, num_results=3, region='in'):
    """Retrieve top search results from Google Custom Search JSON API, excluding PDF files."""
    # Append exclusion operator to the query
    modified_query = f"{query} -filetype:pdf"
    
    url = 'https://www.googleapis.com/customsearch/v1'
    params = {
        'key': api_key,
        'cx': search_engine_id,
        'q': modified_query,
        'num': num_results,
        'gl': region,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return [item.get('link') for item in response.json().get('items', [])]
    except requests.exceptions.RequestException as e:
        print(f"Error searching '{query}': {e}")
        return []
    except json.JSONDecodeError:
        print(f"Invalid JSON response for query: {query}")
        return []

def process_search_term(args):
    """Process individual search term with error handling"""
    category, term, api_key, search_engine_id = args
    return {
        'category': category,
        'term': term,
        'links': get_top_links(api_key, search_engine_id, term)
    }

def execute_parallel_searches(api_key, search_engine_id, queries):
    """Execute searches in parallel and maintain nested structure"""
    # Flatten queries into processable tasks
    tasks = [
        (category, term, api_key, search_engine_id)
        for category, terms in queries.items()
        for term in terms
    ]

    # Execute with thread pool
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_search_term, tasks))

    # Reconstruct nested results structure
    structured_results = {}
    for result in results:
        category = result['category']
        term = result['term']
        if category not in structured_results:
            structured_results[category] = {}
        structured_results[category][term] = result['links']

    return structured_results

def get_search_queries_result(input_search_queries):
    API_KEY = api_key
    SEARCH_ENGINE_ID = '53367770c615942a5'
    
    # Execute searches
    start_time = time.time()
    results = execute_parallel_searches(
        API_KEY,
        SEARCH_ENGINE_ID,
        input_search_queries["queries"]
    )
    
    # Calculate statistics
    total_searches = sum(len(terms) for terms in input_search_queries["queries"].values())
    elapsed_time = time.time() - start_time

    # Print performance metrics
    print(f"\nTotal searches executed: {total_searches}")
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"Average time per search: {elapsed_time/total_searches:.2f} seconds")
    print("Here are the links:", results)
    return results
