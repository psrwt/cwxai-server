from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from utils.mongodb import get_db
import time

# Define the Blueprint (if not already done)
user_bp = Blueprint('user', __name__)

# User details route
@user_bp.route('/user', methods=['GET'])
@jwt_required()  # Ensures only authenticated users can access
def get_user_details():
    try:
        db = get_db()
        users_collection = db['users']
        payments_collection = db['payments']
        # Get the current user's ID from JWT
        user_id = get_jwt_identity()  

        print(user_id)


        # Fetch the user details from the database
        user = users_collection.find_one({'_id': ObjectId(user_id)}, {'_id': 0})  # Exclude ObjectId from response

        if not user:
            return jsonify({'message': 'User not found'}), 404

        # Fetch all payment transactions for this user
        payments = list(payments_collection.find(
            {'user_id': user_id}, 
            {'fee': 0, 'tax': 0, 'razorpay_signature': 0}  # Exclude fields
            ).sort('created_at', -1))  # Sort by created_at in descending order

        # Convert ObjectId to string and ensure created_at is an integer
        for payment in payments:
            payment['_id'] = str(payment['_id'])  # Convert ObjectId to string
            if 'created_at' in payment and isinstance(payment['created_at'], int):
                payment['created_at'] = int(payment['created_at'])  # Ensure integer format
            else:
                payment['created_at'] = int(time.time())  # Fallback to current timestamp

        return jsonify({
            'user': user,
            'transactions': payments
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
