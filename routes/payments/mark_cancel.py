from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from pymongo import MongoClient
import os
from utils.mongodb import get_db

mark_cancelled_bp = Blueprint('mark_cancel', __name__)

# Database configuration
# mongo_uri = os.environ.get("MONGO_URI")
# client = MongoClient(mongo_uri)
# db = client["snapsearchdb"]

db = get_db()
payments_collection = db["payments"]

@mark_cancelled_bp.route('/mark-cancelled', methods=['POST'])
@jwt_required()
def mark_cancelled():
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400

        # Fetch the current payment status
        payment = payments_collection.find_one({'order_id': order_id}, {'status': 1})

        if not payment:
            return jsonify({'error': 'Order not found'}), 400

        if payment['status'] == 'failed':
            return jsonify({'message': 'Order was already marked as failed'}), 200  # ✅ Handle gracefully

        if payment['status'] != 'pending':
            return jsonify({'error': 'Order already processed'}), 400  # Prevent double updates

        # Update payment status to "cancelled" if it's still pending
        update_result = payments_collection.update_one(
            {'order_id': order_id, 'status': 'pending'},
            {'$set': {'status': 'cancelled'}}
        )

        if update_result.modified_count > 0:
            return jsonify({'message': 'Order marked as cancelled'}), 200
        else:
            return jsonify({'message': 'Order status unchanged'}), 200  # Handle gracefully

    except Exception as e:
        return jsonify({'error': 'Failed to mark order as cancelled', 'details': str(e)}), 500
