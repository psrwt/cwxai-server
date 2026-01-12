from flask import Blueprint, request, jsonify
import json
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.llm_functions import get_detailed_problem_statement, get_required_evaluation_headings, generate_queries_per_heading, re_evaluate_problem_statement
from models.idea_check import IdeaCreate, IdeaInDB
from utils.json_converter import json_converter
from services.idea_service import create_idea, update_idea, delete_idea, get_ideas_by_userid
from datetime import datetime, timezone
from utils.slug_create import generate_slug

# Create a Blueprint for problem-related routes
problem_bp = Blueprint('problem', __name__)

# Example of a protected API route
@problem_bp.route('/protected-route', methods=['GET'])
# @jwt_required()  # Ensure that the route is protected
def protected_route():
    current_user = get_jwt_identity()
    print(current_user)
    return jsonify({"message": "This is a protected route!"})

@problem_bp.route('/get-problem-statement', methods=['POST'])
@jwt_required()  # Ensure that the route is protected
def problem_statement():
    try:
        current_user = get_jwt_identity()
        print(current_user)
        # Get the data from the request
        data = request.get_json()


        idea = data.get('idea')
        title = data.get('title')
        location = data.get('location')
        slug = generate_slug(title)
        
        # If no idea is provided, return an error
        if not idea:
            return jsonify({"error": "Idea is required"}), 400

        # Call the function to get the detailed problem statement
        result = get_detailed_problem_statement(idea,location)
        print(result)

        idea_data = IdeaCreate(
        user_id=current_user,
        problem=idea,
        title = title,
        slug = slug,
        location=location,
        problem_response=result,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
        # heading={"title": "Efficiency Improvement Ideas", "category": "Operations"},
        # content={"details": "Detailed explanation on methodology and implementation."},
        # summary={"key_points": ["Increase productivity", "Minimize waste", "Streamline processes"]}
        )
        new_idea = create_idea(idea_data)
        print(new_idea["_id"])
        print(new_idea["slug"])


        # # Save the result to a problem.json file
        # with open(f'{current_user}-{new_idea["_id"]}.json', 'w') as f:
        #     json.dump(result, f, indent=4)

        # Return the result as a JSON response
        return jsonify(new_idea), 200

    except Exception as e:
        # Handle any exceptions and return an error
        return jsonify({"error": str(e)}), 500

@problem_bp.route('/re-evaluate', methods=['POST'])
@jwt_required()  # Ensure the route is protected
def re_evaluate_idea():
    try:
        # Get the current user from JWT identity
        current_user = get_jwt_identity()
        print(f"Current user: {current_user}")

        # Get the data from the request
        data = request.get_json()

        idea = data.get('idea')
        title = data.get('title')
        location = data.get('location')
        additional_input = data.get('additionalInput')
        current_response = data.get('currentResponse')
        userIdeasId = data.get('userideasId')

        # If no idea is provided, return an error
        if not idea:
            return jsonify({"error": "Idea is required"}), 400

        # Call the function to re-evaluate the problem statement based on new data
        result = re_evaluate_problem_statement(idea, title, additional_input, current_response,location)

        # Save the re-evaluated result to the database (adjust to your logic)
        # idea_data = IdeaCreate(
        #     user_id=current_user,
        #     problem=idea,
        #     title=title,
        #     problem_response=result['content'],
        #     created_at=datetime.now(timezone.utc)
        # )
        # new_idea = create_idea(idea_data)
        # print(f"New idea created with ID: {new_idea['_id']}")


        data_to_be_updated = {
            "user_id": current_user,
            "problem": idea,
            "title": title,
            "problem_response": result['content'],
            "updated_at": datetime.now(timezone.utc)
        }

        try:
            updated_userIdeas = update_idea(userIdeasId, data_to_be_updated)
            # print(updated_userIdeas)
            updated_userIdeas = json_converter(updated_userIdeas)
            # print("\nUpdated the userIdea with user id : ", userIdeasId , " and user id is ", current_user, updated_userIdeas)
        except Exception as e: 
            print(f"Error updating idea : {e} ")

        # with open(f'{current_user}-{userIdeasId}.json', 'w') as f:
        #     json.dump(updated_userIdeas, f, indent=4, default=json_converter)

        # Return the updated result as a JSON response
        return jsonify(updated_userIdeas), 200

    except Exception as e:
        # Handle any exceptions and return an error
        return jsonify({"error": str(e)}), 500



@problem_bp.route('/get-user-ideas', methods = ['GET'])
@jwt_required()
def user_ideas():
    try: 
        current_user = get_jwt_identity()
        ideas_for_current_user = get_ideas_by_userid(current_user, limit = 100, skip= 0)
        if not ideas_for_current_user: 
            return jsonify({"Error occured while fetching the data for the user" : ideas_for_current_user}), 500
        
        return jsonify(ideas_for_current_user), 200
        
    except Exception as e: 
        return jsonify({"Error " : str(e)}), 500

@problem_bp.route('/get-required-headings', methods = ['POST'])
@jwt_required()
def problem_required_headings():
    try: 
        current_user = get_jwt_identity()
        print(current_user)
        data = request.get_json()
        detailed_problem_statement = data.get('problem_statement')
        userIdeasId = data.get('userideasId')
        location = data.get('location')
        
        # print(data)
        if not detailed_problem_statement and userIdeasId: 
            return jsonify({"Error : Problem statement or userIdeasId is missing"}), 400
                
        headings = get_required_evaluation_headings(detailed_problem_statement, location)

        # data_to_be_updated = {
        #     "headings" : headings
        # }
        # try:
        #     # updated_userIdeas = update_idea(userIdeasId, data_to_be_updated)
        #     # print(updated_userIdeas)
        #     # print("\nUpdated the userIdea with user id : ", userIdeasId , " and user id is ", current_user, updated_userIdeas)
        # except Exception as e: 
        #     print(f"Error updating idea : {e} ")

        # with open(f'{current_user}-{userIdeasId}.json', 'w') as f:
        #     json.dump(updated_userIdeas, f, indent=4, default=json_converter)

        return jsonify(headings), 200
    except Exception as e: 
        return jsonify({ "error": str(e)}), 500
    

@problem_bp.route('/get-queries-per-heading', methods = ['POST'])
@jwt_required()
def get_queries_per_heading():
    try:
        current_user = get_jwt_identity()
        print(current_user)
        data = request.get_json()
        list_of_headings = data.get('problem_headings')
        detailed_problem_statement = data.get('problem_statement')
        userIdeasId = data.get('userideasId')
        
        # print(data)

        if not list_of_headings and detailed_problem_statement and userIdeasId:
            return jsonify({"Error : Having problems with list of headings or it is missing."}), 400
        
        queries = generate_queries_per_heading(detailed_problem_statement, list_of_headings)

        # data_to_be_updated = {
        #     "queries" : queries
        # }
        # try:
        #     updated_userIdeas = update_idea(userIdeasId, data_to_be_updated)
        #     # print(updated_userIdeas)
        #     # print("\nUpdated the userIdea with user id : ", userIdeasId , " and user id is ", current_user, updated_userIdeas)
        # except Exception as e: 
        #     print(f"Error updating idea : {e} ")

        # with open(f'{current_user}-{userIdeasId}.json', 'w') as f:
        #     json.dump(updated_userIdeas, f, indent=4, default=json_converter)



        return jsonify(queries), 200
    except Exception as e: 
        return jsonify({"error : " : str(e)}), 500