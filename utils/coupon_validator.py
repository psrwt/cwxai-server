from datetime import datetime
from pymongo import MongoClient
import os

# Connect to MongoDB

mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["snapsearchdb"]
coupons_collection = db["coupons"]

def validate_coupon_code(user_id, coupon_code, plan_id, original_price):
    """
    Validate the given coupon code and return the discount details.
    """
    try:
        if not coupon_code:
            return {"error": "Coupon code is required"}, 400
        
        coupon_code = coupon_code.strip()

        if original_price is None or original_price <= 0:
            return {"error": "Valid original price is required"}, 400

        # Fetch coupon from DB
        coupon = coupons_collection.find_one({"coupon_code": coupon_code})

        if not coupon:
            return {"error": "Invalid coupon code"}, 400

        # **Check if coupon is applicable to the given plan**
        if "planId" in coupon and plan_id not in coupon["planId"]:
            return {"error": "Coupon code not applicable for this plan"}, 400

        # **Check if user has already used this coupon**
        if "used_by" in coupon and user_id in coupon["used_by"]:
            return {"error": "You have already used this coupon code"}, 400

        # **Check expiration**
        try:
            current_date = datetime.utcnow().date()
            coupon_expiry = datetime.strptime(coupon["expiry_date"], "%Y-%m-%d").date()

            if current_date > coupon_expiry:
                return {"error": "Coupon code has expired"}, 400
        except ValueError:
            return {"error": "Invalid expiry date format in coupon data"}, 500

        # **Check usage limit**
        if "used_count" in coupon and "usage_limit" in coupon:
            if coupon["used_count"] >= coupon["usage_limit"]:
                return {"error": "Coupon usage limit reached"}, 400
        else:
            return {"error": "Invalid coupon data: missing usage limit"}, 500

        # **Calculate discount**
        discount_percentage = coupon.get("discount_percentage", 0)

        if not isinstance(discount_percentage, (int, float)) or discount_percentage < 0:
            return {"error": "Invalid discount percentage in coupon data"}, 500

        discount_amount = round((discount_percentage / 100) * original_price, 2)
        final_price = round(max(original_price - discount_amount, 0), 2)

        return {
            "message": "Coupon applied successfully",
            "original_price": original_price,
            "discount_amount": discount_amount,
            "discount_percentage": discount_percentage,
            "final_price": final_price
        }, 200

    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}, 500