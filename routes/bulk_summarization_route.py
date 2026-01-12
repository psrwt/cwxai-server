from flask import Blueprint, request, jsonify
import json
from flask_jwt_extended import jwt_required, get_jwt_identity
# from services.scrape_list_of_websites import generate_content_of_all_search_query_links
from services.bulk_summarization_service import parallel_summarization_processing
from utils.json_converter import json_converter
from services.idea_service import update_idea
# from services.scrape_website_list import generate_content_of_all_search_query_links

summarization_bp = Blueprint('bulk_summarization_blueprint', __name__)

@summarization_bp.route('/bulk-summarization', methods=['POST'])
@jwt_required()
def get_scraped_website_summaries():
    try: 
        current_user = get_jwt_identity()
        print(current_user)
        data = request.get_json()
        results = data.get('summarization_content')
        userIdeasId = data.get('userideasId')
        # print(data)

        if not results: 
            return jsonify({"Error : input search links not present or it's not in correct format please cross check."}), 400
        if not userIdeasId: 
            return jsonify({"Error : user ideas id is not present."}), 400
        
        processed_summarization = parallel_summarization_processing(results)

        # data_to_be_updated = {
        #     "summary" : processed_summarization
        # }
        # try:
        #     updated_userIdeas = update_idea(userIdeasId, data_to_be_updated)
        #     print(updated_userIdeas)
        #     # print("\nUpdated the userIdea with user id : ", userIdeasId , " and user id is ", current_user, updated_userIdeas)
        # except Exception as e: 
        #     print(f"Error updating idea : {e} ")

        # with open(f'{current_user}-{userIdeasId}.json', 'w') as f:
        #     json.dump(updated_userIdeas, f, indent=4, default=json_converter)


        return jsonify(processed_summarization), 200

    except Exception as e: 
        return jsonify({"error " :  str(e)}), 500
