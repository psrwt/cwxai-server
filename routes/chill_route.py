# routes/chill_routes.py
from flask import Blueprint, request, jsonify
from services.chill_service import create_chill_text, get_chill_text_with_user  # Importing from the service layer
from playwright.sync_api import sync_playwright
from flask_jwt_extended import jwt_required, get_jwt_identity
chill_bp = Blueprint('chill', __name__)

@chill_bp.route('/chill-brother', methods = ['GET'] )
def chill_bro():
    return jsonify({"message" : "hey I'm working don't worry."}), 200


@chill_bp.route('/chill-bro', methods=['GET'])
def chill_brother():
    try:
        # Use Playwright's synchronous API to run a simple test
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            # Navigate to a test URL. You can change this URL as needed.
            page.goto("https://example.com", wait_until="domcontentloaded")
            # Retrieve the page title
            title = page.title()
            browser.close()
        
        return jsonify({
            "message": "Playwright test succeeded",
            "page_title": title
        }), 200
    except Exception as e:
        # Return an error message if something goes wrong
        return jsonify({
            "message": "Playwright test failed",
            "error": str(e)
        }), 500

# Route to create chill text for a user
@chill_bp.route('/create-chill', methods=['POST'])
@jwt_required()
def create_chill():
    """Create chill text for a user."""
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        # Expecting user_id and chill_text in the payload
        user_id = current_user
        chill_text = data.get('chill_text')

        if not user_id or not chill_text:
            return jsonify({"message": "User ID and chill text are required"}), 400

        # Call the service function to create chill text
        created_chill = create_chill_text(user_id, chill_text)
        
        if "error" in created_chill:
            return jsonify(created_chill), 500
        
        return jsonify({"message": "Chill text created", "chill": created_chill}), 201
    
    except Exception as e:
        return jsonify({"message": "Error creating chill text", "error": str(e)}), 500


# Route to get chill text with user details
@chill_bp.route('/get-chill/<user_id>', methods=['GET'])
def get_chill():
    """Get chill text for a user."""
    try:
        user_id = request.view_args['user_id']  # Extract user_id from URL parameter
        
        # Call the service function to get chill text and user details
        chill_with_user = get_chill_text_with_user(user_id)
        
        if "error" in chill_with_user:
            return jsonify(chill_with_user), 500
        
        return jsonify({"message": "Chill text retrieved", "chill": chill_with_user}), 200

    except Exception as e:
        return jsonify({"message": "Error fetching chill text", "error": str(e)}), 500
