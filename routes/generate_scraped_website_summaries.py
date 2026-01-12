from flask import Blueprint, request, jsonify
import asyncio
import json
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.scrape_list_of_websites import async_generate_content_of_all_search_query_links
from utils.json_converter import json_converter
from services.idea_service import update_idea
# from services.scrape_website_list import generate_content_of_all_search_query_links

scrape_bp = Blueprint('scrape_blueprint', __name__)

@scrape_bp.route('/scrape-list-of-sites', methods=['POST'])
@jwt_required()
def get_scraped_website_summaries():
    try: 
        current_user = get_jwt_identity()
        print(current_user)

        data = request.get_json()
        input_search_links = data.get('input_search_links')
        userIdeasId = data.get('userideasId')
        print(userIdeasId)
        # print(data)

        if not input_search_links: 
            return jsonify({"Error : input search links not present or it's not in correct format please cross check."}), 400
        if not userIdeasId:
            return jsonify({"Error : User Ideas id isn't present here. "}), 400
        if userIdeasId is None:
            return jsonify({"Error : User id isn't present here. "}), 400
        
        processed_output = asyncio.run(async_generate_content_of_all_search_query_links(input_search_links))

        data_to_be_updated = {
            "content" : processed_output
        }
        try:
            updated_userIdeas = update_idea(userIdeasId, data_to_be_updated)
            # print(updated_userIdeas)
            # print("\nUpdated the userIdea with user id : ", userIdeasId , " and user id is ", current_user, updated_userIdeas)
        except Exception as e: 
            print(f"Error updating idea : {e} ")

        with open(f'userfiles/{current_user}-{userIdeasId}.json', 'w') as f:
            json.dump(updated_userIdeas, f, indent=4, default=json_converter)

        return jsonify(processed_output), 200

    except Exception as e: 
        return jsonify({"error " :  str(e)}), 500
