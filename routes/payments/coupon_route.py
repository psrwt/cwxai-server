from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.coupon_validator import validate_coupon_code

coupon_bp = Blueprint('coupon', __name__)

@coupon_bp.route('/validate-coupon', methods=['POST'])
@jwt_required()
def validate_coupon():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data:
            return jsonify({"error": "Invalid request, no JSON payload provided"}), 400

        coupon_code = data.get("coupon_code")
        plan_id = data.get("plan_id")
        original_price = data.get("original_price")

        result, status_code = validate_coupon_code(user_id, coupon_code, plan_id, original_price)
        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500