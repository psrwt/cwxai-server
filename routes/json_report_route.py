from flask import Blueprint, request, jsonify
from services.generate_json_report import full_json_content_report
from services.generate_json_report import generate_executive_overview
from services.generate_json_report import generate_financials
from utils.mongodb import get_db
import json

db = get_db()
report_collection = db["reports"]

json_report_bp = Blueprint('json_report', __name__)

@json_report_bp.route('/generate-json-report', methods=['GET'])
def generate_report():
    # slug = "mindsync--ai-powered-mental-fitness-companion-04-08-32"
    # slug = "ideagenerator-13-51-31"
    # slug = "indian-restaurant-22-54-49"
    slug = "indian-restrau-00-08-24"
    
    # 1. for free reports
    document = report_collection.find_one({"slug": slug}, {"free_report_content": 1, "_id": 0})

    if not document or "free_report_content" not in document:
        return jsonify({"error": "Report not found or missing 'report_content'"}), 404

    free_report_content = document["free_report_content"]
    report_content = free_report_content["free_report_content"]
    
    
    
    # 2. for paid reports
    # document = report_collection.find_one({"slug": slug}, {"report_content": 1, "_id": 0})

    # if not document or "report_content" not in document:
    #     return jsonify({"error": "Report not found or missing 'report_content'"}), 404

    # report_content = document["report_content"]
    
    report_json_content = generate_executive_overview(report_content)

    if "error" in report_json_content:
        return jsonify(report_json_content), 500

    return jsonify(report_json_content)
