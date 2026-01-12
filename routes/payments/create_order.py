from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.coupon_validator import validate_coupon_code
import razorpay
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import logging
import time
from utils.mongodb import get_db

load_dotenv()

create_order_bp = Blueprint('create_order', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database configuration
# mongo_uri = os.environ.get("MONGO_URI")
# client = MongoClient(mongo_uri)
# db = client["snapsearchdb"]

db = get_db()
plans_collection = db["plans"]
payments_collection = db["payments"]
users_collection = db['users']
coupons_collection = db['coupons']

# Razorpay configuration
razorpay_key_id = os.environ.get("RAZORPAY_KEY_ID")
razorpay_key_secret = os.environ.get("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))

@create_order_bp.route('/create-order', methods=['POST'])
@jwt_required()
def create_order():
    try:
        # 1. Get the plan_id and user information from request body
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request, no JSON payload provided'}), 400

        user_id = get_jwt_identity()
        plan_id = data.get('plan_id')
        coupon_code = data.get('coupon_code', None)  # Optional
        user_name = data.get('user_name')
        user_email = data.get('user_email')

        if not plan_id:
            return jsonify({'error': 'Plan ID is required'}), 400
        if not user_name or not user_email:
            return jsonify({'error': 'User name and email are required'}), 400

        # 2. Fetch plan details from the database
        plan = plans_collection.find_one({'planId': plan_id})
        if not plan:
            return jsonify({'error': 'Plan not found'}), 404

        original_price = plan.get('price')
        currency = plan.get('currency')
        credits = plan.get('credits')

        if original_price is None or original_price < 0:
            return jsonify({'error': 'Invalid plan pricing'}), 500

        # 3. Apply coupon discount if provided
        if coupon_code:
            try:
                result, status_code = validate_coupon_code(user_id, coupon_code, plan_id, original_price)
                if status_code != 200:
                    return jsonify(result), status_code

                final_price = result["final_price"]

                # If final price is 0, grant free credits instead of proceeding with payment
                if final_price == 0:
                    update_result = users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$inc": {"credits.free_credits": credits}}
                    )

                    if update_result.modified_count == 0:
                        return jsonify({'error': 'Failed to update user credits'}), 500

                    # Update coupon usage
                    coupon_update = coupons_collection.update_one(
                        {"coupon_code": coupon_code},
                        {
                            "$addToSet": {"used_by": user_id},
                            "$inc": {"used_count": 1}
                        }
                    )

                    if coupon_update.modified_count == 0:
                        return jsonify({'error': 'Failed to update coupon usage'}), 500

                    return jsonify({
                        "message": "Free credits granted successfully!",
                        "credits_added": credits
                    }), 200

                original_price = final_price

            except Exception as coupon_error:
                return jsonify({'error': 'Error processing coupon', 'details': str(coupon_error)}), 500

        # 4. Ensure amount is always an integer (convert to paise for Razorpay)
        amount = int(round(original_price * 100))  # Convert to paise
        if amount < 0:
            return jsonify({'error': 'Invalid final amount'}), 500

        # 5. Prepare data for Razorpay order
        order_data = {
            'amount': amount,
            'currency': currency,
            'receipt': f'order_rcpt_{plan_id}',
            'notes': {
                'user_id': user_id,
                'user_name': user_name,
                'user_email': user_email
            }
        }

        # 6. Create Razorpay order
        # try:
        #     razorpay_order = razorpay_client.order.create(data=order_data)
        #     order_id = razorpay_order['id']
        # except Exception as payment_error:
        #     return jsonify({'error': 'Failed to create Razorpay order', 'details': str(payment_error)}), 500
        

        # Before calling the Razorpay API, set a timeout on the session:
        razorpay_client.session.timeout = 30  # 30-second timeout; adjust as needed
        
        
        # 6. Create Razorpay order with retry logic
        max_retries = 3
        order_id = None
        for attempt in range(max_retries):
            try:
                print(order_data)
                logging.debug(f"Attempt {attempt+1}: Creating Razorpay Order with data: {order_data}")
                razorpay_order = razorpay_client.order.create(data=order_data, timeout=5)
                order_id = razorpay_order['id']
                logging.info(f"Razorpay Order Created: {order_id}")
                break  # Exit loop on success
            except razorpay.errors.BadRequestError as e:
                logging.error(f"Razorpay BadRequestError on attempt {attempt+1}: {e}")
                return jsonify({'error': 'Invalid request data', 'details': str(e)}), 400
            except razorpay.errors.ServerError as e:
                logging.error(f"Razorpay ServerError on attempt {attempt+1}: {e}")
                if attempt == max_retries - 1:
                    return jsonify({'error': 'Razorpay server error', 'details': str(e)}), 500
            except Exception as payment_error:
                logging.error(f"Unexpected Razorpay error on attempt {attempt+1}: {payment_error}")
                if attempt == max_retries - 1:
                    return jsonify({'error': 'Failed to create Razorpay order', 'details': str(payment_error)}), 500
            time.sleep(1)  # Brief delay before next retry


        # 7. Save payment record in the database
        try:
            payment = {
                'user_id': user_id,
                'user_name': user_name,
                'user_email': user_email,
                'plan_id': plan_id,
                'plan_name': plan['title'],
                'coupon_code': coupon_code,
                'credits': credits,
                'order_id': order_id,
                'amount': original_price,
                'currency': currency,
                'status': 'pending',
                'razorpay_payment_id': None,
                'razorpay_signature': None,
                'created_at': int(time.time())  # Unix timestamp
            }
            payments_collection.insert_one(payment)
        except Exception as db_error:
            return jsonify({'error': 'Failed to save payment record', 'details': str(db_error)}), 500

        # 8. Return order information to the client
        return jsonify({
            'message': "Order Created Successfully!",
            'order_id': order_id,
            'amount': amount,  # Amount in paise
            'currency': currency,
            'key_id': razorpay_key_id,
        }), 200

    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred', 'details': str(e)}), 500
    


@create_order_bp.route('/check-order/<order_id>', methods=['GET'])
@jwt_required()
def check_order_status(order_id):
    try:
        # Look up the payment record using the order_id
        # payment = payments_collection.find_one({"order_id": order_id}, {"status": 1})
        payment = payments_collection.find_one({"order_id": order_id}, {"status": 1, "order_id": 1})

        print(payment)
        if not payment:
            return jsonify({"error": "Order not found"}), 404

        # Return a status indicating the order was created
        return jsonify({
            "status": "created",
            "order_id": payment["order_id"],
            "payment_status": payment["status"]
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to check order status', 'details': str(e)}), 500
