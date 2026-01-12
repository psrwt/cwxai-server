from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from bson import ObjectId
import logging
import time
from utils.mongodb import get_db

load_dotenv()

failed_payment_bp = Blueprint('failed_payment', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database configuration
# mongo_uri = os.environ.get("MONGO_URI")
# client = MongoClient(mongo_uri)
# db = client["snapsearchdb"]
db = get_db()
payments_collection = db["payments"]

@failed_payment_bp.route('/mark-failed', methods=['POST'])
@jwt_required()
def mark_payment_failed():
    """
    Marks a payment as failed in the database.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request, no JSON payload provided'}), 400

        user_id = get_jwt_identity()
        order_id = data.get('order_id')
        error_code = data.get('error_code')
        error_description = data.get('error_description')
        error_reason = data.get('error_reason')

        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400

        # Find the order in the database
        payment_record = payments_collection.find_one({"order_id": order_id})
        if not payment_record:
            return jsonify({'error': 'Payment record not found'}), 404

        # Update the status in the database
        update_result = payments_collection.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "status": "failed",
                    "failed_at": int(time.time()),  # Store timestamp
                    "error_code": error_code,
                    "error_description": error_description,
                    "error_reason": error_reason,
                }
            }
        )

        if update_result.modified_count == 0:
            return jsonify({'error': 'Failed to update payment status'}), 500

        return jsonify({"message": "Payment marked as failed"}), 200

    except Exception as e:
        logging.error(f"Error marking payment as failed: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred', 'details': str(e)}), 500
