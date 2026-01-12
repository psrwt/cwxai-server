import os
import asyncio
import logging
import time
import json
from typing import Dict, Any, List

from tqdm.asyncio import tqdm_asyncio
from fake_useragent import UserAgent
from utils.html_cleaner import clean_html_content

from playwright._impl._errors import TargetClosedError, Error as PlaywrightError
from playwright.async_api import Page

# Constants
MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 10 MB limit for full HTML
MAX_SCRAPE_TIME_PER_URL = 30        # 20 seconds max per URL
MAX_CONCURRENT_TASKS = 15            # Limit concurrent tasks to avoid CPU overload.
MAX_RETRIES = 1                      # One attempt only; no retries.

# Logging configuration
logging.basicConfig(level=logging.WARNING)

# Function to fetch a random user agent per request
def get_random_user_agent() -> str:
    ua = UserAgent()
    return ua.random

async def async_generate_content_of_all_search_query_links(
    input_search_links: Dict[str, Dict[str, List[str]]]
) -> Dict[str, Any]:
    """
    Scrapes multiple URLs concurrently and cleans up resources after execution.
    """
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    import crawl4ai.async_webcrawler as awc

    # Disable Crawl4AI caching to prevent reusing outdated event loops
    async def dummy_cache_url(*args, **kwargs):
        return

    async def dummy_retrieve_cached_url(*args, **kwargs):
        return None
 
    awc.AsyncWebCrawler._cache_url = dummy_cache_url
    awc.AsyncWebCrawler._retrieve_cached_url = dummy_retrieve_cached_url

    # Optimized browser configuration.
    BROWSER_CONFIG = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--blink-settings=imagesEnabled=false",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-breakpad",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--safebrowsing-disable-auto-update",
        ]
    )

    random_user_agent = get_random_user_agent()

    RUN_CONFIG = CrawlerRunConfig(
        magic=True,
        word_count_threshold=0,
        exclude_external_links=True,
        remove_overlay_elements=True,
        process_iframes=False,
        simulate_user=True,
        scan_full_page=True,
        ignore_body_visibility=False,
        check_robots_txt=False,
        user_agent=random_user_agent,
        wait_until="domcontentloaded",
        page_timeout=20000,
        only_text=True,
    )

    async def scrape_single_url_shared(
        url: str, category: str, term: str, semaphore: asyncio.Semaphore, crawler
    ) -> Dict[str, Any]:
        """Scrapes a single URL and returns cleaned text content or an error."""
        async with semaphore:
            result = {
                "url": url,
                "category": category,
                "term": term,
                "status": "pending",
                "cleaned_content": None,
                "scrape_time": 0,
                "error": None,
            }
            start_time = time.time()
            try:
                response = await asyncio.wait_for(
                    crawler.arun(url=url, config=RUN_CONFIG),
                    timeout=MAX_SCRAPE_TIME_PER_URL
                )
                if response.success:
                    full_html = response.html
                    if len(full_html.encode("utf-8")) > MAX_OUTPUT_SIZE:
                        result.update({"status": "failed", "error": "Output size exceeded limit"})
                    else:
                        cleaned_content = clean_html_content(full_html)
                        result.update({
                            "status": "success",
                            "cleaned_content": cleaned_content[:20000],
                        })
                else:
                    result.update({"status": "failed", "error": response.error_message})
            except asyncio.TimeoutError:
                logging.error(f"Timeout error for {url}.")
                result.update({"status": "failed", "error": "Timeout error"})
            except (PlaywrightError, TargetClosedError) as pe:
                logging.error(f"Playwright error for {url}: {pe}")
                result.update({"status": "failed", "error": str(pe)})
            except Exception as e:
                logging.error(f"General error for {url}: {e}")
                result.update({"status": "failed", "error": str(e)})
            result["scrape_time"] = time.time() - start_time
            return result

    async def safe_scrape(entry: Dict[str, str], semaphore: asyncio.Semaphore, crawler) -> Any:
        """Wraps `scrape_single_url_shared` to catch and log exceptions."""
        try:
            return await scrape_single_url_shared(
                entry["url"], entry["category"], entry["term"], semaphore, crawler
            )
        except Exception as exc:
            logging.error(f"Unhandled error for {entry['url']}: {exc}")
            return {
                "url": entry["url"],
                "category": entry["category"],
                "term": entry["term"],
                "status": "failed",
                "cleaned_content": None,
                "scrape_time": 0,
                "error": str(exc)
            }

    # Flatten nested input into a queue
    url_queue = [
        {"category": cat, "term": term, "url": url}
        for cat, terms in input_search_links.items()
        for term, urls in terms.items()
        for url in urls
    ]

    start_time = time.time()

    async with AsyncWebCrawler(config=BROWSER_CONFIG) as crawler:
        # Create the semaphore inside the async context to ensure same event loop
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        tasks = [asyncio.shield(safe_scrape(entry, semaphore, crawler)) for entry in url_queue]
        all_results = await tqdm_asyncio.gather(*tasks, desc="Scraping URLs", unit="url")

    end_time = time.time()
    metadata = {
        "processing_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processed_urls": len(url_queue),
        "total_time_taken": end_time - start_time,
    }

    # Write results to file
    with open("output_all.json", "w") as json_file:
        json.dump(all_results, json_file, indent=4)

    return {"metadata": metadata, "results": all_results}

# # --- Standalone Execution Example ---
# if __name__ == "__main__":
#     input_search_links = {
#         "Category1": {
#             "Term1": [
#                 "https://example.com/page1",
#                 "https://example.com/page2",
#             ]
#         }
#     }
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     final_results = loop.run_until_complete(
#         async_generate_content_of_all_search_query_links(input_search_links)
#     )
#     loop.close()  # Ensure the event loop is properly closed
#     print(json.dumps(final_results, indent=4))