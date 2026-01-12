from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
from bson import ObjectId
# from services.rag_service import RAGService, HumanMessage, AIMessage
# from utils.serialization import serialize_messages, deserialize_messages
# from services.generate_final_report import generate_full_final_parallel_executed_report
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
from services.report_crud_service import create_report, update_report, get_report, get_report_by_user_id_and_slug
from models.report_schmea import ReportCreate, ReportInDB
from utils.json_converter import json_converter

# === Azure Blob Storage Setup ===
# from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import os
load_dotenv()

# AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
# AZURE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "userfiles")
# blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
# container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

# def upload_blob_data(blob_name: str, data: bytes):
#     blob_client = container_client.get_blob_client(blob_name)
#     blob_client.upload_blob(data, overwrite=True)
#     print(f"Uploaded blob: {blob_name}")
# === End Blob Setup ===

chat_bp = Blueprint('chat', __name__)

# @chat_bp.route('/ask', methods=['POST'])
# @jwt_required()
# def handle_query():
#     data = request.get_json()
#     current_user = get_jwt_identity()
#     userIdeasId = data.get('userideasId')
#     report_id = data.get('reportId')
#     chat_history = data.get('chat_history')

#     # The file_path points to the final report file in blob storage.
#     file_path = f"user_cache/{current_user}/{current_user}-{userIdeasId}-{report_id}.json"
#     rag_service = RAGService(current_user, file_path=file_path)
#     if not data or 'query' not in data:
#         return jsonify({'error': 'Missing query parameter'}), 400

#     chat_history = []
#     query = data['query']
#     response = rag_service.generate_response(query, chat_history, use_chat_history=True)
#     chat_history.append(HumanMessage(content=query))
#     chat_history.append(AIMessage(content=response))
    
#     updated_messages = serialize_messages(chat_history)

#     return jsonify({
#         'response': response,
#         'messages': updated_messages
#     })


# @chat_bp.route('/generate-final-report', methods=['POST'])
# @jwt_required()
# def generate_final_report():
#     data = request.get_json()
#     idea = data['problem_response']
#     userIdeasId = data.get('userideasId')
#     current_user = get_jwt_identity()
#     print("UserIdea ID:", userIdeasId)

#     # Use the combined workflow file from blob storage.
#     file_path = f"user_cache/{current_user}/{current_user}-{userIdeasId}.json"
#     print("Combined file blob path:", file_path)

#     # Generate the final report using the combined workflow file.
#     report = generate_full_final_parallel_executed_report(idea, current_user, file_path=file_path)

#     new_report_data = ReportCreate(
#         user_id=current_user,
#         user_idea_id=userIdeasId,
#         report_file_path=file_path,  # this is the combined file blob path
#         created_at=datetime.now(timezone.utc),
#         updated_at=datetime.now(timezone.utc),
#         report_content=report
#     )

#     # Insert the report into the database.
#     created_report = create_report(new_report_data)
#     print("Created report:", created_report["_id"])
#     report_id = created_report["_id"]

#     # Build the blob name for the final report.
#     blob_report_path = f"user_cache/{current_user}/{current_user}-{userIdeasId}-{report_id}.json"
#     report_json = json.dumps(report, indent=4, default=json_converter)
    
#     # Upload the final report to Azure Blob Storage.
#     upload_blob_data(blob_report_path, report_json.encode("utf-8"))

#     return jsonify(report), 200

# Route to get a report based on report_id and current user
# @chat_bp.route('/get-report/<user_idea_id>', methods=['GET'])
# @jwt_required()  # Protect the route so only authenticated users can access
# def get_report_route(user_idea_id: str):
#     try:
#         # Get the current user's ID from the JWT token
#         current_user = get_jwt_identity()
#         print(user_idea_id)

#         # Fetch the report for the current user and report_id
#         report = get_report_by_user_idea_id(current_user, user_idea_id)

#         # Return the report as a JSON response
#         return jsonify({"message": "Report fetched successfully", "data": report}), 200
    
#     except Exception as e:
#         return jsonify({"message": str(e)}), 400
    
# Route to get a report based on report_id slug and current user
@chat_bp.route('/get-report/<slug>', methods=['GET'])
@jwt_required()  # Protect the route so only authenticated users can access
def get_report_route(slug: str):
    try:
        # Get the current user's ID from the JWT token
        current_user = get_jwt_identity()
        print(slug)

        # Fetch the report for the current user and report_id
        report = get_report_by_user_id_and_slug(current_user, slug)

        # Return the report as a JSON response
        return jsonify({"message": "Report fetched successfully", "data": report}), 200
    
    except Exception as e:
        return jsonify({"message": str(e)}), 400