import asyncio
import aiohttp
import gc
import logging
import time
import json
from typing import Dict, Any, List
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from tqdm.asyncio import tqdm_asyncio
from fake_useragent import UserAgent
from utils.html_cleaner import clean_html_content
import nest_asyncio

# Apply nest_asyncio patch if needed (e.g., in nested loop environments)
nest_asyncio.apply()

# Constants
MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 10 MB limit for full HTML
MAX_SCRAPE_TIME_PER_URL = 20         # 20 seconds max scrape time
MAX_CONCURRENT_TASKS = 20            # Limit number of concurrent tasks
BATCH_SIZE = 20                      # Process in batches
MAX_RETRIES = 1                      # Max number of retries for failed URLs

ua = UserAgent()
random_user_agent = ua.random

# Configure browser and crawling settings
BROWSER_CONFIG = BrowserConfig(headless=True, verbose=True)

RUN_CONFIG = CrawlerRunConfig(
    magic=False,
    word_count_threshold=0,
    exclude_external_links=True,
    remove_overlay_elements=True,
    process_iframes=False,
    simulate_user=True,
    scan_full_page=True,
    ignore_body_visibility=False,
    check_robots_txt=False,  
    user_agent=random_user_agent,
    wait_until="networkidle",
    page_timeout=20000
)

async def scrape_single_url(url: str, category: str, term: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    """
    Scrape a single URL, get full HTML, clean it, and return the processed output.
    """
    async with semaphore:  # Limit concurrency
        result = {
            "url": url,
            "category": category,
            "term": term,
            "status": "pending",
            "cleaned_content": None,
            "scrape_time": 0,
            "error": None,
        }
        start_time = asyncio.get_running_loop().time()
        retries = 0
        while retries < MAX_RETRIES:
            try:
                async with AsyncWebCrawler(config=BROWSER_CONFIG) as crawler:
                    response = await asyncio.wait_for(
                        crawler.arun(url=url, config=RUN_CONFIG),
                        timeout=MAX_SCRAPE_TIME_PER_URL
                    )
                    if response.url != url:
                        print(f"Resolved URL ({response.url}) does not match requested URL ({url})")

                    if response.success:
                        full_html = response.html  # Get full website HTML
                        if len(full_html.encode("utf-8")) > MAX_OUTPUT_SIZE:
                            result.update({"status": "failed", "error": "Output size exceeded limit"})
                        else:
                            cleaned_content = clean_html_content(full_html)
                            result.update({
                                "status": "success",
                                "cleaned_content": cleaned_content[:20000],  # Limit output size
                                "scrape_time": asyncio.get_running_loop().time() - start_time,
                            })
                    else:
                        result.update({
                            "status": "failed",
                            "error": f"Crawl failed: {response.error_message}",
                            "scrape_time": asyncio.get_running_loop().time() - start_time,
                        })
                break  # Exit the retry loop on success
            except asyncio.TimeoutError:
                retries += 1
            except Exception as e:
                retries += 1
                result.update({
                    "status": "failed",
                    "error": str(e),
                    "scrape_time": asyncio.get_running_loop().time() - start_time
                })
                await asyncio.sleep(5)  # Wait before retrying
        return result

async def scrape_urls_in_batches(url_batches: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)  # Create inside function
    start_report_time = asyncio.get_running_loop().time()
    all_results = []

    for batch_index, batch in enumerate(url_batches):
        logging.info(f"Processing batch {batch_index + 1}/{len(url_batches)}...")
        try:
            batch_results = await tqdm_asyncio.gather(
                *[scrape_single_url(entry["url"], entry["category"], entry["term"], semaphore)
                  for entry in batch],
                desc=f"Batch {batch_index + 1}",
                unit="url",
            )

            all_results.extend(batch_results)

            # Save intermediate batch results to prevent memory overload
            with open(f"output_batch_{batch_index + 1}.json", "w") as json_file:
                json.dump(batch_results, json_file, indent=4)

            # Free up memory
            del batch_results
            gc.collect()

        except Exception as e:
            logging.error(f"Error processing batch {batch_index + 1}: {str(e)}")

    end_report_time = asyncio.get_running_loop().time()

    output_data = {
        "metadata": {
            "processing_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "processed_urls": sum(len(batch) for batch in url_batches),
            "total_time_taken": end_report_time - start_report_time,
        },
        "results": all_results,
    }

    return output_data

def generate_content_of_all_search_query_links(input_search_links: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    """
    Wrapper function to start the scraping process in optimized batches.
    """
    # Convert input_search_links dictionary into a queue list
    url_queue = [
        {"category": cat, "term": term, "url": url}
        for cat, terms in input_search_links.items()
        for term, urls in terms.items()
        for url in urls
    ]

    # Split into batches
    url_batches = [url_queue[i: i + BATCH_SIZE] for i in range(0, len(url_queue), BATCH_SIZE)]

    return asyncio.run(scrape_urls_in_batches(url_batches))


# Example: 100+ links (replace with actual URLs)
# input_search_links = {
#     "### Competitive Landscape Assessment": {
#         "competitive analysis of automated content generation solutions": [
#             "https://www.sciencedirect.com/science/article/pii/S2666603022000136",
#             "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/how-generative-ai-can-boost-consumer-marketing",
#             "https://www.marketingaiinstitute.com/blog/what-marketers-need-to-know-about-ai-content-generation-today"
#         ],
#         "market share of content creation tools 2023 report": [
#             "https://www.grandviewresearch.com/industry-analysis/digital-content-creation-market-report",
#             "https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier",
#             "https://www.goldmansachs.com/insights/articles/the-creator-economy-could-approach-half-a-trillion-dollars-by-2027"
#         ],
#         "top competitors in content idea generation automation analysis": [
#             "https://buffer.com/resources/ai-social-media-content-creation/",
#             "https://digitalmarketinginstitute.com/blog/what-are-the-best-ai-and-marketing-automation-tools",
#             "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/how-generative-ai-can-boost-consumer-marketing"
#         ]
#     },
#     "### Customization Potential Assessment": {
#         "case studies on tailored content automation solutions": [
#             "https://www.iriusrisk.com/case-studies/tailored-threat-modeling-for-financial-institiution",
#             "https://www.geeklymedia.com/roofing-home-services",
#             "https://wauseonmachine.com/custom-automation-wauseon-machine"
#         ],
#         "customization features in content ideation software survey": [
#             "https://www.nngroup.com/articles/customization-personalization/",
#             "https://www.reddit.com/r/marketing/comments/1c5lq7z/whats_the_most_impressive_ai_tool_you_have_ever/",
#             "https://community.qualtrics.com/website-app-insights-62/automatically-add-timing-questions-24488"
#         ],
#         "user preferences for personalized content generation tools report": [
#             "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/the-value-of-getting-personalization-right-or-wrong-is-multiplying",
#             "https://sproutsocial.com/insights/social-media-algorithms/",
#             "https://hbr.org/2022/11/how-generative-ai-is-changing-creative-work"
#         ]
#     },
#     "### Integration Capability Analysis": {
#         "compatibility of social media platforms with content ideation software": [
#             "https://www.sprinklr.com/blog/social-media-management-tools/",
#             "https://guide.teleprompterpro.com/blog/social-media-tools/",
#             "https://blog.tryleap.ai/best-instagram-automation-tools/"
#         ],
#         "evaluation of API integrations for content generation tools": [
#             "https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview",
#             "https://www.servicenow.com/docs/bundle/vancouver-servicenow-platform/page/administer/assessments/task/t_GenAssessmentOnDemandAPI.html",
#             "https://docs.tenable.com/integrations/patch-management/Content/vm-api-key.htm"
#         ],
#         "integration of content management systems with automation tools case study": [
#             "https://www.hyland.com/en/solutions/products/alfresco-platform",
#             "https://start.docuware.com/",
#             "https://www.hyland.com/en/solutions/products/perceptive-content"
#         ]
#     },
#     "### Market Size Estimation": {
#         "content ideation software market analysis and forecast": [
#             "https://www.thebusinessresearchcompany.com/report/content-marketing-software-global-market-report",
#             "https://www.businessresearchinsights.com/market-reports/idea-management-software-market-105230",
#             "https://www.grandviewresearch.com/industry-analysis/creative-software-market-report"
#         ],
#         "growth of content marketing automation industry statistics": [
#             "https://backlinko.com/marketing-automation-stats",
#             "https://moosend.com/blog/10-marketing-automation-statistics-need-know/",
#             "https://explodingtopics.com/blog/marketing-automation-stats"
#         ],
#         "market size for content creation automation tools report 2023": [
#             "https://www.grandviewresearch.com/industry-analysis/digital-content-creation-market-report",
#             "https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier",
#             "https://www.hubspot.com/marketing-statistics"
#         ]
#     },
#     "### Problem Validation": {
#         "content idea generation challenges marketers case study": [
#             "https://www.linkedin.com/pulse/case-study-101-preparing-competitions-case-based-makenna-schumacher",
#             "https://www.smartinsights.com/traffic-building-strategy/campaign-planning/four-steps-developing-big-idea-campaign/",
#             "https://contentmarketinginstitute.com/articles/b2b-content-marketing-trends-research/"
#         ],
#         "impact of manual brainstorming on content creation efficiency report": [
#             "https://www.linkedin.com/pulse/identifying-right-metrics-measuring-ai-tool-impact-luciana-padua-ytrjc",
#             "https://www.reddit.com/r/ChatGPT/comments/13ecw4a/notes_from_a_teacher_on_ai_detection/",
#             "https://www.tiny.cloud/blog/how-ai-text-editors-improve-content-creation/"
#         ],
#         "user struggles with content ideation survey results": [
#             "https://www.cdc.gov/mmwr/volumes/69/wr/mm6932a1.htm",
#             "https://pubmed.ncbi.nlm.nih.gov/29233805/",
#             "https://www.samhsa.gov/data/sites/default/files/reports/rpt39443/2021NSDUHFFRRev010323.pdf"
#         ]
#     },
#     "### Revenue Model Viability": {
#         "financial viability of subscription-based content ideation software": [
#             "https://www.reddit.com/r/SaaS/comments/17iv5tt/what_is_the_best_saasmicro_saas_ideas_to_build/",
#             "https://iteo.com/blog/post/the-shift-towards-subscription-based-business-models/",
#             "https://www.reddit.com/r/ChatGPT/comments/1alz2hh/chatgpt_4_or_gemini_advanced_whats_your_pick/"
#         ],
#         "profitability analysis of content generation platforms": [
#             "https://pubsonline.informs.org/doi/10.1287/isre.2022.0620",
#             "https://www.accc.gov.au/system/files/ACCC+commissioned+report+-+The+impact+of+digital+platforms+on+news+and+journalistic+content,+Centre+for+Media+Transition+(2).pdf",
#             "https://www.sciencedirect.com/science/article/pii/S2666603022000136"
#         ],
#         "revenue models for content automation tools case studies": [
#             "https://www.smartinsights.com/digital-marketing-strategy/online-business-revenue-models/amazon-case-study/",
#             "https://www.accc.gov.au/system/files/ACCC+commissioned+report+-+The+impact+of+digital+platforms+on+news+and+journalistic+content,+Centre+for+Media+Transition+(2).pdf",
#             "https://tim.blog/2017/12/30/how-to-build-a-million-dollar-one-person-business/"
#         ]
#     },
#     "### Risk Identification and Mitigation Strategies": {
#         "case studies on failure points in content automation projects": [
#             "https://www.linkedin.com/posts/dr-karthik-nagendra-ba874b7_b2bmarketing-saas-contentmarketingtips-activity-7247186339467517952-F-WO",
#             "https://hfast.mie.utoronto.ca/wp-content/uploads/DeGuzman_Kanaan_Hopkins_Donmez_ITS_postprint.pdf",
#             "https://www.oracle.com/ma/erp/what-is-erp/erp-implementation-case-study/"
#         ],
#         "mitigation strategies for content ideation tool risks analysis": [
#             "https://pmc.ncbi.nlm.nih.gov/articles/PMC7587888/",
#             "https://www.health.state.mn.us/people/syringe/suicide.pdf",
#             "https://www.jnjmedicalconnect.com/products/spravato/medical-content/spravato-suicidal-ideation-and-behavior-assessment-tool-sibat"
#         ],
#         "risks in implementing automated content generation solutions report": [
#             "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/how-generative-ai-can-boost-consumer-marketing",
#             "https://www.linkedin.com/posts/bmagnetta_leveling-up-your-business-with-llms-and-retrieval-augmented-activity-7260003640940072962-qZp_",
#             "https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier"
#         ]
#     },
#     "### Scalability of the Solution": {
#         "case studies on scaling content ideation platforms": [
#             "https://www.ndash.com/blog/scaling-content-strategies-lessons-for-2025",
#             "https://contently.com/",
#             "https://www.bynder.com/en/glossary/content-at-scale/"
#         ],
#         "growth potential of automated content generation solutions report": [
#             "https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier",
#             "https://hbr.org/2022/11/how-generative-ai-is-changing-creative-work",
#             "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/how-generative-ai-can-boost-consumer-marketing"
#         ],
#         "scalability challenges in content automation tools analysis": [
#             "https://hbr.org/sponsored/2023/04/how-automation-drives-business-growth-and-efficiency",
#             "https://www.ddw-online.com/high-content-screening-the-next-challenge-effective-data-mining-and-exploration-633-200812/",
#             "https://www.linkedin.com/pulse/strategies-scaling-content-production-without-sacrificing-wmpqe"
#         ]
#     },
#     "### Solution Feasibility Analysis": {
#         "automated content idea generation tools feasibility study": [
#             "https://softwareengineering.stackexchange.com/questions/241410/is-it-feasible-and-useful-to-auto-generate-some-code-of-unit-tests",
#             "https://www.sciencedirect.com/science/article/pii/S0268401223000233",
#             "https://www.reddit.com/r/NewTubers/comments/118037m/i_want_to_start_a_faceless_youtube_channel_any/"
#         ],
#         "case studies on automating user workflows for content ideation": [
#             "https://sparktoro.com/blog/dont-just-get-a-sense-for-your-customers-make-audience-research-actionable-through-revenue-lifting-tactics/",
#             "https://zapier.com/blog/chatgpt-marketing-writing/",
#             "https://www.teamim.com/blog/harnessing-ai-for-content-management"
#         ],
#         "evaluation of AI in content creation processes research paper": [
#             "https://www.sciencedirect.com/science/article/pii/S0268401223000233",
#             "https://libguides.kcl.ac.uk/systematicreview/ai",
#             "https://www.sciencedirect.com/science/article/pii/S2666603022000136"
#         ]
#     },
#     "### Strategic Fit with Market Trends": {
#         "alignment of content automation tools with digital marketing trends report": [
#             "https://blog.hubspot.com/marketing/hubspot-blog-marketing-industry-trends-report",
#             "https://www.hubspot.com/marketing-statistics",
#             "https://chapman.peopleadmin.com/postings/35862/print_preview"
#         ],
#         "market trends in content creation and automation analysis": [
#             "https://www.sciencedirect.com/science/article/pii/S2666603022000136",
#             "https://news.missouristate.edu/2024/10/03/how-ai-is-transforming-marketing/",
#             "https://www.forbes.com/councils/forbestechcouncil/2024/03/21/how-ai-is-transforming-the-marketing-industry/"
#         ],
#         "strategic opportunities in automated content ideation solutions": [
#             "https://www.sitecore.com/resources/insights/marketing-automation/content-marketing-automation-best-practices",
#             "https://www.clearvoice.com/resources/harnessing-ai-for-content-ideation-and-briefing/",
#             "https://www.mediagenix.tv/"
#         ]
#     },
#     "### Technology Requirements Evaluation": {
#         "requirements for AI-driven content ideation systems research": [
#             "https://www.mckinsey.com/capabilities/mckinsey-digital/our-insights/the-economic-potential-of-generative-ai-the-next-productivity-frontier",
#             "https://dl.acm.org/doi/10.1145/3544548.3580652",
#             "https://www.getblend.com/blog/10-best-ai-tools-to-use-for-content-creation/"
#         ],
#         "technical specifications for content automation software": [
#             "https://csrc.nist.gov/pubs/sp/800/126/r1/final",
#             "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-126r3.pdf",
#             "https://csrc.nist.gov/pubs/sp/800/126/r2/final"
#         ],
#         "technology stack for automated content generation tools analysis": [
#             "https://www.copy.ai/blog/ai-content-creation",
#             "https://www.reddit.com/r/Entrepreneur/comments/174o7vd/i_run_an_ai_automation_agency_aaa_my_honest/",
#             "https://zenmedia.com/blog/marketing-tech-stack/"
#         ]
#     },
#     "### User Demand Assessment": {
#         "market research on user preferences for content idea generation": [
#             "https://www.sciencedirect.com/science/article/pii/S0268401220308082",
#             "https://www.braineet.com/blog/co-creation-examples",
#             "https://www.sciencedirect.com/science/article/pii/S0040162522001305"
#         ],
#         "trends in content creation needs among marketers report": [
#             "https://contentmarketinginstitute.com/articles/b2b-content-marketing-trends-research/",
#             "https://www.hootsuite.com/research/social-trends",
#             "https://contentmarketinginstitute.com/articles/research-b2b-audience/"
#         ],
#         "user demand for automated content ideation tools survey": [
#             "https://community.qualtrics.com/survey-platform-54/qualtrics-dark-mode-26479?sort=likes.desc",
#             "https://www.workast.com/blog/efficient-marketing-campaigns-through-automated-content-creation/",
#             "https://basis.com/news/nearly-all-marketers-use-generative-ai-every-month-70-use-it-weekly"
#         ]
#     }
# }

# report = generate_content_of_all_search_query_links(input_search_links)

# Save full report
# output_file_path = "final_output.json"
# with open(output_file_path, "w") as json_file:
#     json.dump(report, json_file, indent=4)

# logging.info(f"Final report saved to {output_file_path}")
