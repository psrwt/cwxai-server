import json
import time
import traceback
from datetime import datetime, timezone
import os
from azure.storage.blob import BlobServiceClient
from celery.exceptions import SoftTimeLimitExceeded

from celery_worker import celery

from services.llm_functions import get_required_evaluation_headings, generate_queries_per_heading
from services.google_search_service import get_search_queries_result
from services.scrape_list_of_websites import async_generate_content_of_all_search_query_links
from services.bulk_summarization_service import parallel_summarization_processing
from services.generate_final_report import generate_full_final_parallel_executed_report
from services.user_crud_service import update_user_credits_by_type
from services.report_crud_service import create_report, update_report
from models.report_schmea import ReportCreate
from utils.json_converter import json_converter
from services.free_report_generation import generate_free_report_content

from services.generate_json_report import full_json_content_report

# Setup Azure Blob Storage client
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "userfiles")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

def upload_blob_data(blob_name: str, data: bytes):
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True)
    print(f"Uploaded blob: {blob_name}")

def retry_operation(func, *args, retries=3, delay=2, **kwargs):
    last_exception = None
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
            time.sleep(delay)
    raise last_exception


@celery.task(bind=True, name="generate_free_report_task")
def generate_free_report_task(self, data, current_user, userIdeasId, slug):
    try:
        self.update_state(state="PROGRESS", meta={
            "current": 1, "total": 3, "status": "Starting with your dream"
        })

        time.sleep(3)  # Show step 1 state for 3 seconds

        self.update_state(state="PROGRESS", meta={
            "current": 2, "total": 3, "status": "Adding the AI magic"
        })

        idea = data.get("problem_response")
        location = data.get("location")
        if not location or not isinstance(location, str):
            location = "USA"


        if not idea:
            raise Exception("Missing problem_response for free report generation")
        
        print("generating the free report content")

        report = generate_free_report_content(idea, location)
        free_report_content = report["free_report_content"]
        # report = {"Key": "hello this is the report"}
        # print(free_report_content)
        
        print("generating the json content")
        report_json_content = full_json_content_report(free_report_content)
        print("this is the report json content: ")
        print(report_json_content)

        self.update_state(state="PROGRESS", meta={
            "current": 3, "total": 3, "status": "Finalising for you"
        })

        time.sleep(2)  # Show final state for 2 seconds

        new_report_data = ReportCreate(
            user_id=current_user,
            user_idea_id=userIdeasId,
            slug=slug,

            access_level="free",
            status="free",

            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),

            free_report_content=report,
            report_json_content=report_json_content
        )

        created_report = create_report(new_report_data)
        report_id = created_report["_id"]

        return {"message": "Free report generated successfully", "report": {
            "reportId": report_id,
            "report": report
        }}

    except Exception as e:
        try:
            update_user_credits_by_type(current_user, 1, credit_type="free")
            print(f"Refunded 1 free credit to user {current_user} due to error.")
        except Exception as credit_refund_error:
            print("Failed to refund credit:", str(credit_refund_error))
        print("Free report generation failed:", str(e))
        traceback.print_exc()
        raise e


# Set soft and hard time limits (in seconds) for long-running tasks.
@celery.task(bind=True, name="execute_workflow_and_generate_report_task")
def execute_workflow_and_generate_report_task(self, data, current_user, userIdeasId, slug):
    try:
        total_steps = 8

        self.update_state(state="PROGRESS", meta={
            "current": 1, "total": total_steps, "status": "Analyzing the Idea"
        })
        detailed_problem_statement = data.get("problem_response")
        location = data.get('location')
        if not location:
            location = "entire world"
        if not detailed_problem_statement:
            raise Exception("Idea is required")

        self.update_state(state="PROGRESS", meta={
            "current": 2, "total": total_steps, "status": "Exploring Possibilities"
        })
        headings_response = retry_operation(get_required_evaluation_headings, detailed_problem_statement, location, retries=3, delay=2)
        headings = headings_response.get("headings", []) if isinstance(headings_response, dict) else []
        
        self.update_state(state="PROGRESS", meta={
            "current": 3, "total": total_steps, "status": "Shaping the Vision"
        })
        queries = retry_operation(generate_queries_per_heading, detailed_problem_statement, headings, location, retries=3, delay=2)
        
        self.update_state(state="PROGRESS", meta={
            "current": 4, "total": total_steps, "status": "Gathering Insights"
        })
        query_links = retry_operation(get_search_queries_result, queries, retries=3, delay=2)
        
        self.update_state(state="PROGRESS", meta={
            "current": 5, "total": total_steps, "status": "Uncovering Opportunities"
        })
        import asyncio
        scraped_content = asyncio.run(async_generate_content_of_all_search_query_links(query_links))
        
        self.update_state(state="PROGRESS", meta={
            "current": 6, "total": total_steps, "status": "Crafting the Narrative"
        })
        summarized_content = parallel_summarization_processing(scraped_content)
        final_output = {"summary": summarized_content["summarized_results"]}
        
        self.update_state(state="PROGRESS", meta={
            "current": 7, "total": total_steps, "status": "Bringing it to Life"
        })
        blob_file_name = f"user_cache/{current_user}/{current_user}-{userIdeasId}.json"
        json_data = json.dumps(final_output, indent=4, default=lambda o: o.__dict__)
        upload_blob_data(blob_file_name, json_data.encode("utf-8"))
        
        self.update_state(state="PROGRESS", meta={
            "current": 8, "total": total_steps, "status": "Finalizing the Blueprint"
        })
        idea = data.get("problem_response")
        report = generate_full_final_parallel_executed_report(
            idea,
            current_user,
            location,
            file_path=f"user_cache/{current_user}/{current_user}-{userIdeasId}.json"
        )
        
        print("generating the json content")
        report_json_content = full_json_content_report(report)
        print("this is the report json content: ")
        print(report_json_content)
        
        new_report_data = ReportCreate(
            user_id=current_user,
            user_idea_id=userIdeasId,
            slug = slug,

            access_level="paid",
            status="paid",

            report_file_path=f"user_cache/{current_user}/{current_user}-{userIdeasId}.json",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            report_content=report,
            report_json_content=report_json_content
        )
        created_report = create_report(new_report_data)
        report_id = created_report["_id"]
        final_report_blob_path = f"user_cache/{current_user}/{current_user}-{userIdeasId}-{report_id}.json"
        report_json = json.dumps(report, indent=4, default=lambda o: o.__dict__)
        upload_blob_data(final_report_blob_path, report_json.encode("utf-8"))

        return {"message": "Workflow and report generation completed successfully","report": {
        "reportId": report_id,
        "report": report
    }}

    except SoftTimeLimitExceeded as e:
        # Task timed out; refund credits.
        try:
            update_user_credits_by_type(current_user, 1, credit_type="paid")
            print(f"Task timed out. Refunded 1 credit to user {current_user}.")
        except Exception as credit_refund_error:
            print("Failed to refund credit after timeout:", str(credit_refund_error))
        print("Task timed out:", str(e))
        traceback.print_exc()
        raise e
    except Exception as e:
        try:
            update_user_credits_by_type(current_user, 1, credit_type="paid")
            print(f"Refunded 1 credit to user {current_user} due to error.")
        except Exception as credit_refund_error:
            print("Failed to refund credit:", str(credit_refund_error))
        print("Workflow execution failed:", str(e))
        traceback.print_exc()
        raise e


# upgrade report task is here 


@celery.task(bind=True, name="upgrade_report_to_paid_task")
def upgrade_report_to_paid_task(self, data, current_user, userIdeasId, report_id, problem_response, location):
    try:
        total_steps = 8

        # 1. Analyzing the Idea
        self.update_state(state="PROGRESS", meta={
            "current": 1, "total": total_steps, "status": "Analyzing the Idea"
        })
        idea = problem_response
        location = location or "USA"
        if not idea:
            raise Exception("Missing problem_response")

        # 2–7: same as paid workflow (headings, queries, scraping, summarization)
        self.update_state(state="PROGRESS", meta={"current": 2, "total": total_steps, "status": "Exploring Possibilities"})
        headings = retry_operation(get_required_evaluation_headings, idea, location).get("headings", [])

        self.update_state(state="PROGRESS", meta={"current": 3, "total": total_steps, "status": "Shaping the Vision"})
        queries = retry_operation(generate_queries_per_heading, idea, headings, location)

        self.update_state(state="PROGRESS", meta={"current": 4, "total": total_steps, "status": "Gathering Insights"})
        query_links = retry_operation(get_search_queries_result, queries)

        self.update_state(state="PROGRESS", meta={"current": 5, "total": total_steps, "status": "Uncovering Opportunities"})
        import asyncio
        scraped = asyncio.run(async_generate_content_of_all_search_query_links(query_links))

        self.update_state(state="PROGRESS", meta={"current": 6, "total": total_steps, "status": "Crafting the Narrative"})
        summary = parallel_summarization_processing(scraped)["summarized_results"]
        final_output = {"summary": summary}

        # 7. Upload intermediate JSON
        self.update_state(state="PROGRESS", meta={"current": 7, "total": total_steps, "status": "Bringing it to Life"})
        intermediate_path = f"user_cache/{current_user}/{current_user}-{userIdeasId}.json"
        upload_blob_data(intermediate_path, json.dumps(final_output, default=lambda o: o.__dict__).encode())

        # 8. Finalizing the Blueprint
        self.update_state(state="PROGRESS", meta={"current": 8, "total": total_steps, "status": "Finalizing the Blueprint"})
        report = generate_full_final_parallel_executed_report(
            idea, current_user, location, file_path=intermediate_path
        )
        
        print("generating the json content")
        report_json_content = full_json_content_report(report)
        print("this is the report json content: ")
        print(report_json_content)

        # Persist to DB
        update_report(report_id, {
            "access_level": "paid",
            "status": "paid",
            "report_content": report,
            "report_json_content": report_json_content,
            "report_file_path": intermediate_path,
            "updated_at": datetime.now(timezone.utc)
        })

        # **Upload final file for RAG usage**
        final_path = f"user_cache/{current_user}/{current_user}-{userIdeasId}-{report_id}.json"
        upload_blob_data(final_path, json.dumps(report, indent=4, default=lambda o: o.__dict__).encode())

        return {
            "message": "Report upgraded successfully",
            "report": {"reportId": report_id, "report": report}
        }

    except SoftTimeLimitExceeded as e:
        # refund on timeout
        try:
            update_user_credits_by_type(current_user, 1, credit_type="paid")
        except:
            pass
        raise e

    except Exception as e:
        # refund on any other error
        try:
            update_user_credits_by_type(current_user, 1, credit_type="paid")
        except:
            pass
        raise e
