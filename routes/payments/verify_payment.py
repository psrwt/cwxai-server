from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import requests
import razorpay
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import hashlib
import hmac
import logging
from utils.mongodb import get_db

load_dotenv()

verify_payment_bp = Blueprint('verify_payment', __name__)

# Database configuration
# mongo_uri = os.environ.get("MONGO_URI")
# client = MongoClient(mongo_uri)
# db = client["snapsearchdb"]
db = get_db()
plans_collection = db["plans"]
payments_collection = db["payments"]
users_collection = db["users"]
coupons_collection = db["coupons"]

# Razorpay configuration
razorpay_key_id = os.environ.get("RAZORPAY_KEY_ID")
razorpay_key_secret = os.environ.get("RAZORPAY_KEY_SECRET")

RAZORPAY_API_URL = "https://api.razorpay.com/v1/payments"
razorpay_client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))

@verify_payment_bp.route('/verify-payment', methods=['POST'])
@jwt_required()
def verify_payment():
    try:
        # 1. Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request, no JSON payload provided'}), 400

        user_id = get_jwt_identity()

        razorpay_order_id = data.get('order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return jsonify({'error': 'Order ID, Payment ID, and Signature are required'}), 400

        # 2. Secure Signature Verification (using Razorpay's official method)
        try:
            params = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            razorpay_client.utility.verify_payment_signature(params)  # Raises an error if invalid
        except razorpay.errors.SignatureVerificationError:
            return jsonify({'error': 'Payment signature verification failed'}), 400

        # 3. Fetch payment status from Razorpay API
        try:
            response = requests.get(f"{RAZORPAY_API_URL}/{razorpay_payment_id}", auth=(razorpay_key_id, razorpay_key_secret))
            response.raise_for_status()  # Raises error for non-200 responses
            payment_data = response.json()
        except requests.exceptions.RequestException as api_error:
            logging.exception("Failed to verify payment status with Razorpay")
            return jsonify({'error': 'Failed to verify payment status with Razorpay', 'details': str(api_error)}), 400

        # 4. Ensure payment is successful
        if payment_data.get('status') != 'captured':
            return jsonify({'error': 'Payment not successful'}), 400

        # 5. Validate payment amount to prevent tampering
        payment = payments_collection.find_one({'order_id': razorpay_order_id})
        if not payment:
            return jsonify({'error': 'Order not found'}), 400

        expected_amount = int(payment['amount'] * 100)  # Convert to paise
        if payment_data.get('amount') != expected_amount:
            return jsonify({'error': 'Payment amount mismatch'}), 400

        # 6. Prevent replay attacks by ensuring the payment ID is not reused
        if payments_collection.find_one({'razorpay_payment_id': razorpay_payment_id}):
            return jsonify({'error': 'Duplicate payment detected'}), 400
        
        # 7. Extract Payment Method
        payment_method = payment_data.get('method', 'unknown')

        # 8. Atomic Update - Mark Payment as Completed & Add Credits
        
        # Update payment record in MongoDB
        update_result = payments_collection.update_one(
            {'order_id': razorpay_order_id, 'status': {'$in': ['pending', 'failed']}},  
            {'$set': {
                'status': 'paid',
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
                'fee': payment_data.get('fee') / 100 if payment_data.get('fee') else 0,
                'tax': payment_data.get('tax') / 100 if payment_data.get('tax') else 0,
                'payment_method': payment_method  # Store only payment method (card, upi, netbanking, wallet, etc.)
            }}
        )

        if update_result.modified_count == 0:
            return jsonify({'error': 'Payment already processed or invalid order'}), 400

        # 9. Add paid credits to user
        credit_update_result = users_collection.update_one(
            {'_id': ObjectId(payment['user_id'])},
            {'$inc': {"credits.paid_credits": payment['credits']}}
        )

        if credit_update_result.modified_count == 0:
            return jsonify({'error': 'Failed to update user credits'}), 500

        # 10. Update coupon usage if a coupon was applied
        if payment.get('coupon_code'):
            coupons_collection.update_one(
                {'coupon_code': payment['coupon_code']},
                {
                    '$inc': {'used_count': 1},
                    '$addToSet': {'used_by': user_id}
                }
            )

        return jsonify({
            'message': 'Payment successful',
            'credits_added': payment['credits']
            }), 200

    except Exception as e:
        logging.exception("Exception occurred during payment verification")
        return jsonify({'error': 'Payment verification failed', 'details': str(e)}), 400
    


@verify_payment_bp.route('/check-payment-status/<order_id>', methods=['GET'])
@jwt_required()
def check_payment_status(order_id):
    try:
        # Look up the payment record using the order_id
        payment = payments_collection.find_one({"order_id": order_id}, {"status": 1, "credits": 1})
        if not payment:
            return jsonify({"error": "Payment not found"}), 404

        # If payment status is 'paid', return success along with any credits added
        if payment["status"] == "paid":
            return jsonify({
                "status": "success",
                "credits_added": payment.get("credits", 0)
            }), 200
        else:
            # Otherwise, return the current status (such as 'pending' or 'failed')
            return jsonify({"status": payment["status"]}), 200
    except Exception as e:
        return jsonify({"error": "Failed to check payment status", "details": str(e)}), 500


@verify_payment_bp.route('/webhook', methods=['POST'])
def webhook():
    # Get the raw payload and signature header sent by Razorpay
    payload = request.data
    # Decode payload if it is bytes
    if isinstance(payload, bytes):
        payload_str = payload.decode('utf-8')
    else:
        payload_str = payload

    received_signature = request.headers.get("X-Razorpay-Signature")
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    if not webhook_secret:
        logging.error("Webhook secret not set in environment")
        return jsonify({"error": "Webhook secret not configured"}), 500

    # Verify the webhook signature. If invalid, reject the webhook.
    try:
        razorpay_client.utility.verify_webhook_signature(payload_str, received_signature, webhook_secret)
    except razorpay.errors.SignatureVerificationError:
        logging.error("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 400

    # Parse the JSON payload
    event = request.get_json()
    logging.info(f"Webhook received: {event.get('event')}")
    
    # Process only the payment captured event (you can add additional event types if needed)
    if event.get("event") == "payment.captured":
        payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id")
        
        if not order_id or not razorpay_payment_id:
            logging.error("Missing order_id or payment_id in webhook payload: %s", event)
            return jsonify({"error": "Invalid payload"}), 400

        # Look up the payment record using order_id
        payment = payments_collection.find_one({"order_id": order_id})
        if not payment:
            logging.error(f"Order {order_id} not found")
            return jsonify({"error": "Order not found"}), 404

        # If payment is already marked as paid, ignore duplicate events
        if payment.get("status") == "paid":
            logging.info(f"Order {order_id} already processed as paid")
            return jsonify({"message": "Payment already processed"}), 200

        # Update payment record in MongoDB
        update_result = payments_collection.update_one(
            {"order_id": order_id, "status": {"$in": ["pending", "failed"]}},
            {"$set": {
                "status": "paid",
                "razorpay_payment_id": razorpay_payment_id,
                "payment_method": payment_entity.get("method", "unknown")
            }}
        )
        if update_result.modified_count == 0:
            logging.error(f"Failed to update payment for order {order_id}. Update result: {update_result.raw_result}")
            return jsonify({"error": "Could not update payment status"}), 400

        # Add paid credits to user account
        credit_update_result = users_collection.update_one(
            {"_id": ObjectId(payment["user_id"])},
            {"$inc": {"credits.paid_credits": payment["credits"]}}
        )
        if credit_update_result.modified_count == 0:
            logging.error(f"Failed to update credits for user {payment['user_id']} for order {order_id}")
            # Optionally handle this situation as needed

        # (Optional) Update coupon usage if applicable
        if payment.get("coupon_code"):
            coupons_collection.update_one(
                {"coupon_code": payment["coupon_code"]},
                {
                    "$inc": {"used_count": 1},
                    "$addToSet": {"used_by": payment["user_id"]}
                }
            )

        logging.info(f"Payment for order {order_id} processed successfully via webhook")
        return jsonify({"message": "Payment processed successfully"}), 200

    # For events that you are not handling explicitly, simply acknowledge receipt.
    logging.info("Webhook received an unhandled event: %s", event.get("event"))
    return jsonify({"message": "Event received"}), 200
