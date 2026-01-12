from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from pydantic import ValidationError
from models.user_form_data_schema import UserFormData
from services.user_form_data_service import (
    create_user_form_data,
    get_user_form_data_by_user_id,
    update_user_form_data,
    delete_user_form_data,
)
from bson import ObjectId  # Import ObjectId here
from utils.mongodb import get_db

from services.user_crud_service import get_or_update_form_filled_status

user_form_bp = Blueprint("user_form", __name__, url_prefix="/user-form")


# check weather the user has the form filled or not 

@user_form_bp.route("/form-filled-check", methods=["GET"])
@jwt_required()
def check_user_filled_the_form_or_not():
    try:
        user_id = get_jwt_identity()
        status = get_or_update_form_filled_status(user_id)
        return jsonify({"formFilled": status}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    

# @user_form_bp.route("/user/form-filled-update", methods=["POST"])
# @jwt_required()
# def update_user_form_status():
#     try:
#         user_id = get_jwt_identity()
#         data = request.get_json()
#         new_status = data.get("formFilled")

#         print(f"New status received: {new_status}")
#         if not new_status:
#             return jsonify({"error": "Missing 'formFilled' boolean in request body"}), 400

#         if new_status is None or not isinstance(new_status, bool):
#             return jsonify({"error": "Invalid or missing 'formFilled' boolean in request body"}), 400

#         updated_status = get_or_update_form_filled_status(user_id, new_status)
#         return jsonify({"formFilled": updated_status}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 400



# Create or Submit Form Data
@user_form_bp.route("/", methods=["POST"])
@jwt_required()  # Ensures the user is authenticated
def submit_form():
    try:
        data = request.get_json()
        data['user_id'] = get_jwt_identity()
        form_data = UserFormData(**data)

        # Get user_id from JWT token
        user_id = get_jwt_identity()  # This will get the user_id from the JWT token
        form_data.user_id = user_id  # Assign the user_id to the form_data

        # Save form data
        form_id = create_user_form_data(form_data)

        # Update user's formFilled flag
        db = get_db()
        db['users'].update_one(
            {"_id": ObjectId(user_id)},  # Use user_id from JWT token
            {"$set": {"formFilled": True}}
        )

        return jsonify({"message": "Form submitted successfully", "form_id": form_id}), 201

    except ValidationError as ve:
        return jsonify({"message": "Validation failed", "errors": ve.errors()}), 400
    except Exception as e:
        return jsonify({"message": "Form submission failed", "error": str(e)}), 500

# Read Form Data
@user_form_bp.route("/", methods=["GET"])
@jwt_required()  # Ensures the user is authenticated
def get_form():
    try:
        # Get user_id from JWT token
        user_id = get_jwt_identity()

        form_data = get_user_form_data_by_user_id(user_id)
        if not form_data:
            return jsonify({"message": "Form data not found"}), 404
        return jsonify(form_data), 200
    except Exception as e:
        return jsonify({"message": "Failed to fetch form data", "error": str(e)}), 500

# Update Form Data
@user_form_bp.route("/", methods=["PUT"])
@jwt_required()  # Ensures the user is authenticated
def update_form():
    try:
        # Get user_id from JWT token
        user_id = get_jwt_identity()

        updated_data = request.get_json()
        form_data = update_user_form_data(user_id, updated_data)
        return jsonify({"message": "Form updated successfully", "form_data": form_data}), 200
    except Exception as e:
        return jsonify({"message": "Failed to update form data", "error": str(e)}), 500

# Delete Form Data
@user_form_bp.route("/", methods=["DELETE"])
@jwt_required()  # Ensures the user is authenticated
def delete_form():
    try:
        # Get user_id from JWT token
        user_id = get_jwt_identity()

        deleted = delete_user_form_data(user_id)
        if deleted:
            # Also update user's formFilled flag to False
            db = get_db()
            db['users'].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"formFilled": False}}
            )
            return jsonify({"message": "Form data deleted successfully"}), 200
        else:
            return jsonify({"message": "Form data not found"}), 404
    except Exception as e:
        return jsonify({"message": "Failed to delete form data", "error": str(e)}), 500
