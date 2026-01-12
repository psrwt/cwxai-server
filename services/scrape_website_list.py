import time
import random 
import os
import psutil
from typing import Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from fake_useragent import UserAgent
from utils.html_cleaner import clean_html_content
from tqdm import tqdm
import logging


MAX_SCRAPE_TIME_PER_URL = 40


def _simulate_human_interaction(driver: webdriver.Remote):
    """Simulate human-like browser interactions."""
    try:
        # Random initial delay
        time.sleep(random.uniform(0.5, 2.5))

        # Simulate mouse movements
        action = ActionChains(driver)
        for _ in range(random.randint(2, 4)):
            action.move_by_offset(
                random.randint(-50, 50),
                random.randint(-50, 50)
            ).perform()
            time.sleep(random.uniform(0.2, 0.7))

        # Random scrolling
        scroll_script = f"window.scrollBy(0, {random.randint(200, 800)});"
        driver.execute_script(scroll_script)
        time.sleep(random.uniform(0.3, 1.2))

        # Secondary scroll
        if random.random() > 0.3:
            driver.execute_script(f"window.scrollBy(0, {random.randint(-200, 200)});")
            time.sleep(random.uniform(0.2, 0.5))

    except Exception as e:
        print(f"Interaction simulation failed: {str(e)}")


def selenium_scrape_webpage(
    url: str,
    browser_type: str = "chrome",
    headless: bool = True,
    driver_path: Optional[str] = None,
    wait_time: int = 10,
    human_like: bool = True,
    max_retries: int = 2
) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrape webpage content using Selenium with human-like behavior simulation.
    """
    driver = None
    user_agent = UserAgent().random
    attempts = 0
    start_time = time.time()

    while attempts <= max_retries:
        try:
            # Browser setup
            if browser_type.lower() == "chrome":
                options = webdriver.ChromeOptions()
                options.add_argument(f"user-agent={user_agent}")
                if headless:
                    options.add_argument("--headless")
                service = ChromeService(executable_path=driver_path) if driver_path else ChromeService()
                driver = webdriver.Chrome(service=service, options=options)
            else:
                return None, "Invalid browser type specified"

            # Navigate to page
            driver.get(url)

            # Human-like behavior simulation
            if human_like:
                _simulate_human_interaction(driver)

            # Wait for page load
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            scrape_time = time.time() - start_time

            return driver.page_source, None, scrape_time

        except Exception as e:
            error_msg = f"Attempt {attempts + 1} failed: {str(e)}"
            attempts += 1
            if driver:
                driver.quit()

        finally:
            if driver:
                driver.quit()

    return None, f"Failed after {max_retries} attempts: {error_msg}"


def process_search_report(input_search_links: Dict[str, Dict[str, list]], max_workers: Optional[int] = None) -> Dict[str, Any]:
    """Main processing function with LLM integration."""
    start_report_time = time.time()  # Total time tracker for report generation

    # Load input data
    # if not os.path.exists(input_file):
    #     raise FileNotFoundError(f"Input file {input_file} not found in the current directory.")
    
    # with open(input_file, 'r') as f:
    #     report_data = json.load(f)

    # Prepare URL list with hierarchy tracking
    # url_queue = []
    # for category, terms in report_data['results'].items():
    #     for term, urls in terms.items():
    #         for url in urls:
    #             url_queue.append({
    #                 'category': category,
    #                 'term': term,
    #                 'url': url
    #             })
    url_queue = [{'category': cat, 'term': term, 'url': url} for cat, terms in input_search_links.items() for term, urls in terms.items() for url in urls]
    

    # Process URLs in parallel with rate limiting
    processed_results = {}
    # with ThreadPoolExecutor(max_workers=max_workers) as executor:
    #     futures = {executor.submit(process_url_entry, entry): entry for entry in url_queue}

    #     for future in as_completed(futures):
    #         entry = futures[future]
    #         try:
    #             result = future.result()

    #             # Build nested structure
    #             category = entry['category']
    #             term = entry['term']

    #             if category not in processed_results:
    #                 processed_results[category] = {}
    #             if term not in processed_results[category]:
    #                 processed_results[category][term] = []

    #             processed_results[category][term].append(result)

    #         except Exception as e:
    #             print(f"Error processing future: {str(e)}")

    # # Create final output structure with enhanced metadata
    # output_data = {
    #     'metadata': {
    #         'original_metadata': report_data['metadata'],
    #         'processing_date': time.strftime("%Y-%m-%d %H:%M:%S"),
    #         'processed_urls': len(url_queue),
    #         'total_input_tokens': sum(
    #             item['summary']['input_tokens'] 
    #             for category in processed_results.values() 
    #             for term in category.values() 
    #             for item in term
    #         ),
    #         'total_output_tokens': sum(
    #             item['summary']['output_tokens'] 
    #             for category in processed_results.values() 
    #             for term in category.values() 
    #             for item in term
    #         )
    #     },
    #     'results': processed_results
    # }
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_url_entry, entry): entry for entry in url_queue}
        
        with tqdm(total=len(url_queue), desc="Scraping progress", unit="url") as pbar:
            for future in as_completed(futures, timeout=MAX_SCRAPE_TIME_PER_URL):
                entry = futures[future]
                try:
                     result = future.result()
                     processed_results.append(result)
                except TimeoutError:
                     logging.error(f"Scraping timed out for {entry['url']}")
                     processed_results.append({'url': entry['url'], 'status': 'failed', 'content': None, 'scrape_time': 0, 'error': 'Scraping timed out', 'category': entry['category'], 'term': entry['term']})
                except Exception as e:
                    logging.error(f"Error processing {entry['url']}: {e}")
                pbar.update(1)
    
    end_report_time = time.time()
    output_data = {
        'metadata': {
            'processing_date': time.strftime("%Y-%m-%d %H:%M:%S"),
            'processed_urls': len(url_queue),
            'total_time_taken': end_report_time - start_report_time
        },
        'results': processed_results
    }

    # Total time for the entire report generation
    end_report_time = time.time()
    total_time_taken = end_report_time - start_report_time
    print(f"Total time taken to generate the report: {total_time_taken:.2f} seconds")
    
    # print(f"Memory after processing all URLs: {get_memory_usage()} MB")

    # Save output with custom encoding
    # with open(output_file, 'w', encoding='utf-8') as f:
    #     json.dump(output_data, f, ensure_ascii=False, indent=2)

    return output_data


def process_url_entry(url_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single URL entry with timing and error handling."""
    result = {'url': url_entry['url'], 'status': 'pending', 'content': None, 'scrape_time': 0, 'error': None, 'category': url_entry['category'], 'term': url_entry['term']}
    
    html, error, scrape_time = selenium_scrape_webpage(url_entry['url'])
    if error:
        result.update({'status': 'failed', 'error': error})
        logging.error(f"Failed to scrape {url_entry['url']}: {error}")
    else:
        cleaned_html = clean_html_content(html) if html else None
        if cleaned_html:
            words = cleaned_html.split()
            cleaned_html = ' '.join(words[:2000])
        result.update({'status': 'success', 'content': cleaned_html, 'scrape_time': scrape_time})
    
    return result

def generate_content_of_all_search_query_links(input_search_links: Dict[str, Dict[str, list]]) -> Dict[str, Any]:
    """Wrapper function to start the scraping process."""
    return process_search_report(input_search_links)