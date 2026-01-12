from flask import Blueprint, request, jsonify
import asyncio
import json
import os
import time
import traceback
from flask_jwt_extended import jwt_required, get_jwt_identity
from dotenv import load_dotenv
from datetime import datetime, timezone

# === Azure Blob Storage Setup ===
from azure.storage.blob import BlobServiceClient
from services.llm_functions import (
    get_detailed_problem_statement,
    get_required_evaluation_headings,
    generate_queries_per_heading
)
from services.google_search_service import get_search_queries_result
from services.scrape_list_of_websites import async_generate_content_of_all_search_query_links
from services.bulk_summarization_service import parallel_summarization_processing
from services.idea_service import create_idea, update_idea, get_idea_by_user_id_and_slug
from services.generate_final_report import generate_full_final_parallel_executed_report
from services.report_crud_service import create_report, get_report_by_user_id_and_slug, update_report
from models.report_schmea import ReportCreate
from utils.json_converter import json_converter

# Import user credit functions
from services.user_crud_service import get_user_credits, update_user_credits_by_type

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "userfiles")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

def upload_blob_data(blob_name: str, data: bytes):
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True)
    print(f"Uploaded blob: {blob_name}")

workflow_bp = Blueprint("workflow", __name__)

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

@workflow_bp.route('/execute-workflow-and-generate-report', methods=['POST'])
@jwt_required()
def execute_workflow_and_generate_report():
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return jsonify({"error": "Unauthorized: Missing user identity"}), 401

        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be a JSON object"}), 400

        access_level = data.get("access_level", "free").lower()
        slug = data.get("slug")
        userIdeasId = data.get("userideasId")

        if not slug or not userIdeasId:
            return jsonify({"error": "Missing 'slug' or 'userideasId' in request"}), 400

        if access_level not in ["free", "paid"]:
            return jsonify({"error": "Invalid access level. Must be 'free' or 'paid'"}), 400

        # Fetch credits safely
        user_credits = get_user_credits(current_user) or {}
        free_credits = user_credits.get('free_credits', 0)
        paid_credits = user_credits.get('paid_credits', 0)

        task = None

        if access_level == "free":
            if free_credits < 1:
                return jsonify({"error": "Insufficient free credits"}), 403

            try:
                update_user_credits_by_type(current_user, -1, credit_type="free")
            except Exception as e:
                print("Error updating free credits:", str(e))
                return jsonify({"error": "Failed to deduct free credit"}), 500

            from tasks import generate_free_report_task
            task = generate_free_report_task.delay(data, current_user, userIdeasId, slug)

        elif access_level == "paid":
            if paid_credits < 1:
                return jsonify({"error": "Insufficient paid credits"}), 403

            try:
                update_user_credits_by_type(current_user, -1, credit_type="paid")
            except Exception as e:
                print("Error updating paid credits:", str(e))
                return jsonify({"error": "Failed to deduct paid credit"}), 500

            from tasks import execute_workflow_and_generate_report_task
            task = execute_workflow_and_generate_report_task.delay(data, current_user, userIdeasId, slug)

        if not task or not hasattr(task, "id"):
            return jsonify({"error": "Failed to initiate report generation"}), 500

        return jsonify({"task_id": task.id, "status": "Report generation task submitted"}), 202

    except Exception as e:
        print("Unexpected error during report generation:", str(e))
        traceback.print_exc()
        return jsonify({"error": "Internal server error during report generation"}), 500
    

@workflow_bp.route('/workflow-task-status/<task_id>', methods=['GET', 'OPTIONS'])
@jwt_required()
def workflow_task_status(task_id):
    if request.method == "OPTIONS":
        return "", 200
    from tasks import execute_workflow_and_generate_report_task
    task = execute_workflow_and_generate_report_task.AsyncResult(task_id)
    
    response = {
        "state": task.state,
        "progress": task.info if task.state == "PROGRESS" else {}
    }
    if task.state == "SUCCESS":
        response["progress"] = {"current": 1, "total": 1, "status": "Completed"}
        response["result"] = task.result
    elif task.state == "FAILURE":
        response["progress"] = {"current": 0, "total": 0, "status": "Failed"}
        response["error"] = str(task.info)
    
    return jsonify(response)



# handling the upgrade of report here 

@workflow_bp.route('/upgrade-report-and-execute-workflow', methods=['POST'])
@jwt_required()
def upgrade_report_and_execute_workflow():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(force=True)
        slug = data.get("slug")
        # userIdeasId = data.get("userideasId")

        found_user_idea_based_on_slug = get_idea_by_user_id_and_slug(user_id, slug)


        userIdeasId = found_user_idea_based_on_slug["_id"]
        
        problem_response = found_user_idea_based_on_slug["problem_response"]["content"]
        location = found_user_idea_based_on_slug["location"]
        print("userIdeasId: ", userIdeasId)
        print("Location: ", location)
        if not problem_response:
            return jsonify({"error": "Problem not found"}), 404
        

        if not slug or not userIdeasId:
            return jsonify({"error": "Missing slug or userIdeasId"}), 400

        # 1. Fetch existing report
        existing = get_report_by_user_id_and_slug(user_id, slug)

        repord_id = existing["_id"]
        if not existing:
            return jsonify({"error": "No existing report to upgrade"}), 404
        if existing.get("status") != "free":
            return jsonify({"error": "Only free reports can be upgraded"}), 409

        # 2. Check & deduct paid credit
        credits = get_user_credits(user_id) or {}
        if credits.get("paid_credits", 0) < 1:
            return jsonify({"error": "Insufficient paid credits"}), 403

        try:
            update_user_credits_by_type(user_id, -1, credit_type="paid")
        except Exception as e:
            print("Credit deduction failed:", e)
            return jsonify({"error": "Failed to deduct paid credit"}), 500
        
        from tasks import upgrade_report_to_paid_task

        # 3. Dispatch upgrade task
        task = upgrade_report_to_paid_task.delay(
            data, user_id, userIdeasId, str(existing["_id"]), problem_response, location)
        if not task or not hasattr(task, "id"):
            return jsonify({"error": "Failed to start upgrade task"}), 500

        return jsonify({"task_id": task.id, "status": "Upgrade task submitted"}), 202

    except Exception as e:
        print("Unexpected error in upgrade route:", str(e))
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500