from flask import Blueprint, request, jsonify
import json
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.google_search_service import get_search_queries_result
from utils.json_converter import json_converter
from services.idea_service import update_idea


search_bp = Blueprint('google-search', __name__)

@search_bp.route('/query-google-search', methods = ['POST'])
@jwt_required()
def get_queries_google_search_result():
    try: 
        current_user = get_jwt_identity()
        print(current_user)
        data = request.get_json()
        input_search_queries = data.get('input_search_queries')
        userIdeasId = data.get('userideasId')


        if not input_search_queries and userIdeasId: 
            return jsonify({"Error : input search query is missing or in not the correct format. "}), 400
        
        query_links = get_search_queries_result(input_search_queries)

        # data_to_be_updated = {
        #     "query_links" : query_links
        # }
        # try:
        #     updated_userIdeas = update_idea(userIdeasId, data_to_be_updated)
        #     print(updated_userIdeas)
        #     # print("\nUpdated the userIdea with user id : ", userIdeasId , " and user id is ", current_user, updated_userIdeas)
        # except Exception as e: 
        #     print(f"Error updating idea : {e} ")

        # with open(f'{current_user}-{userIdeasId}.json', 'w') as f:
        #     json.dump(updated_userIdeas, f, indent=4, default=json_converter)

        
        return jsonify(query_links), 200
    except Exception as e: 
        return ({"error" : str(e)}), 500
    
