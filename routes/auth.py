import logging
from datetime import timedelta, datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from utils.mongodb import get_db
import requests
import os
from bson.objectid import ObjectId
from flask_cors import cross_origin
from pydantic import ValidationError
from models.user import UserCreate, UserInDB  # Import your Pydantic models
from services.auth_service import save_user  # Import save_user from auth_service
from bson.objectid import ObjectId

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Helper function to rename _id to id
def rename_id_field(user_data):
    """Rename _id to id in user data."""
    if "_id" in user_data:
        user_data["id"] = str(user_data["_id"])  # Rename _id to id and convert to string
        del user_data["_id"]  # Remove _id after renaming
    return user_data

@auth_bp.route('/google-login', methods=['POST', 'OPTIONS'])
def google_login():
    """
    Handle Google login and user creation.
    """
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200

    data = request.get_json()
    token = data.get('token')

    if not token:
        logger.error("Token is missing in the request.")
        return jsonify({"message": "Token is required"}), 400

    try:
        # Step 1: Verify the Google token by calling Google's tokeninfo endpoint
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        response_data = response.json()

        if response.status_code != 200:
            logger.error(f"Google token verification failed: {response_data}")
            return jsonify({"message": "Invalid Google token"}), 400

        # Step 2: Extract user information from the response
        user_info = {
            "email": response_data.get('email'),
            "name": response_data.get('name'),
            "picture": response_data.get('picture'),
            "id": response_data.get('sub')  # Google unique user ID
        }

        # Step 3: Validate the token's audience (aud) matches your Google Client ID
        aud = response_data.get('aud')
        if aud != os.getenv("GOOGLE_CLIENT_ID"):
            logger.error(f"Invalid token audience: {aud}")
            return jsonify({"message": "Invalid token audience"}), 400

        # Step 4: Check if the user already exists in the database
        db = get_db()
        user = db['users'].find_one({"email": user_info["email"]})

        if not user:
            user_info["role"] = "user"
            user_info["formFilled"] = False
            user_id = save_user(user_info)  # Call save_user function from auth_service
            user = db['users'].find_one({"_id": ObjectId(user_id)})
        else:
            # If user exists but formFilled field is missing, add it
            if 'formFilled' not in user:
                db['users'].update_one(
                    {'_id': user['_id']},
                    {'$set': {'formFilled': False}}
                )
                user['formFilled'] = False

        # Rename _id to id before passing to Pydantic
        user = rename_id_field(user)

        logger.info(f"User data before Pydantic validation: {user}")

        # Step 5: Validate the user data with Pydantic
        try:
            user_schema = UserInDB(**user)  # Validate user data using Pydantic
            logger.info("User data validated successfully.")
            
        except ValidationError as e:
            logger.error(f"Pydantic validation error: {e.errors()}")
            return jsonify({"message": "Invalid user data", "errors": e.errors()}), 400
        
        
        # Step 6: Generate a JWT token for the user
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(days=30)  # This is the correct way to set the expiration
        access_token = create_access_token(identity=str(user['id']), expires_delta=expires_delta)

        # Step 7: Send back the user information and token
        return jsonify({
            "id": user['id'],
            "name": user['name'],
            "email": user['email'],
            "role": user['role'],
            "picture": user['picture'],
            "token": access_token,
            "formFilled": user['formFilled']  
        })

    except Exception as e:
        logger.error(f"Error occurred during Google login: {str(e)}")
        return jsonify({"message": "Google login failed", "error": str(e)}), 500
