from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

plans_bp = Blueprint('plans', __name__)

# Database configuration
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["snapsearchdb"]
plans_collection = db["plans"]


@plans_bp.route('/plans', methods=['GET'])
# @jwt_required()
def get_plans():
    """
    Retrieves all plans from the database.
    """
    try:
        # Fetch plans from the database
        plans_cursor = plans_collection.find().sort("credits",1)
        plans_list = list(plans_cursor)
        
        # Convert ObjectId to string for JSON serialization
        for plan in plans_list:
          plan['_id'] = str(plan['_id'])

        return jsonify({"plans": plans_list}), 200  # Return plans list inside object
    
    except Exception as e:
       logger.error(f"Error getting plans: {str(e)}")
       return jsonify({"message": "Failed to retrieve plans", "error": str(e)}), 500