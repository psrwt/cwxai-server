from models.idea_check import IdeaCreate, IdeaInDB
from utils.mongodb import get_db  # MongoDB connection utility
from bson.objectid import ObjectId
from pydantic import ValidationError
from typing import Dict, Any

# Function to create a new idea (already provided)
def create_idea(idea_data: IdeaCreate) -> IdeaInDB:
    idea_dict = idea_data.model_dump()
    try:
        db = get_db()
        collection = db['userideas']
        result = collection.insert_one(idea_dict).inserted_id

        if result:
            print("idea inserted successfully.", result)

        idea_dict = collection.find_one({"_id": ObjectId(result)})
        # print(idea_dict)
      
        idea_dict['_id'] = str(idea_dict['_id'])
        return idea_dict
    
    except Exception as e:
        raise Exception(f"Error creating idea: {e}")

# Function to update an idea (already provided)
def update_idea(idea_id: str, updated_data: Dict[str, Any]) -> IdeaInDB:
    try:
        db = get_db()
        collection = db['userideas']
        
        # Update query to set the updated data
        update_query = {'$set': updated_data}
        
        # Perform the update
        result = collection.update_one({'_id': ObjectId(idea_id)}, update_query)
        
        if result.modified_count == 0:
            raise Exception("No document was updated")
        
        updated_idea = collection.find_one({'_id': ObjectId(idea_id)})
        # updated_idea['_id'] = str(updated_idea['_id'])
        return updated_idea
    
    except Exception as e:
        raise Exception(f"Error updating idea: {e}")

# Function to delete an idea (already provided)
def delete_idea(idea_id: str) -> bool:
    try:
        db = get_db()
        collection = db['userideas']
        
        result = collection.delete_one({'_id': ObjectId(idea_id)})
        
        if result.deleted_count == 0:
            raise Exception("No document was deleted")
        
        return True
    
    except Exception as e:
        raise Exception(f"Error deleting idea: {e}")
    


# def get_ideas_by_userid(user_id: str, limit: int = 50, skip: int = 0) -> list[IdeaInDB]:
    try:
        db = get_db()
        collection = db['userideas']

        # now filter ideas based on the user id
        filter_query = {'user_id' : user_id}

        # find ideas based on the matching filter with pagination things    
        idea_cursor = collection.find(filter_query).skip(skip).limit(limit)

        ideas = []

        for idea in idea_cursor:
            idea['_id'] = str(idea['_id'])
            ideas.append(idea)


        return ideas


    except Exception as e:
        raise Exception(f"Error fetching ideas for user {user_id} : {e}")

def get_idea_by_user_id_and_slug(user_id: str, slug: str) -> dict:
    try:
        db = get_db()
        collection = db['userideas']

        query = {
            "user_id": user_id,
            "slug": slug
        }

        idea = collection.find_one(query)
        if not idea:
            return None

        idea['_id'] = str(idea['_id'])
        return idea

    except Exception as e:
        raise Exception(f"Error fetching idea by user_id and slug: {e}")


def get_ideas_by_userid(user_id: str, limit: int = 50, skip: int = 0) -> list[dict]:
    try:
        db = get_db()
        ideas_collection = db['userideas']

        pipeline = [
            # 1. Filter ideas by the given user_id
            {"$match": {"user_id": user_id}},
            # 2. Apply pagination early
            {"$skip": skip},
            {"$limit": limit},
            # 3. Lookup associated report without report_content
            {"$lookup": {
                "from": "reports",
                "let": {"idea_id": {"$toString": "$_id"}},  # Convert idea _id to string
                "pipeline": [
                    {"$match": {
                        "$expr": {
                            "$and": [
                                {"$eq": ["$user_id", user_id]},       # Match user_id
                                {"$eq": ["$user_idea_id", "$$idea_id"]} # Match idea ID
                            ]
                        }
                    }},
                    # Project only the necessary fields (exclude report_content)
                    {"$project": {
                        "_id": {"$toString": "$_id"},
                        "report_file_path": 1,
                        "created_at": 1,
                        "updated_at": 1
                    }}
                ],
                "as": "report"
            }},
            # 4. Exclude ideas without an associated report
            {"$match": {"report": {"$ne": []}}},
            # 5. Project only the required fields from ideas
            {"$project": {
                "_id": {"$toString": "$_id"},
                "title": 1,
                "slug": 1,
                "problem": 1,
                "problem_response": 1,
                "created_at": 1,
                "updated_at": 1,
                "report": 1
            }}
        ]

        results = list(ideas_collection.aggregate(pipeline))

        # Convert the 'report' array to a single document if exists
        for idea in results:
            if idea.get("report") and isinstance(idea["report"], list):
                idea["report"] = idea["report"][0]

        return results

    except Exception as e:
        raise Exception(f"Error fetching ideas for user {user_id}: {e}")

# Example data to create a new idea
# idea_data = IdeaCreate(
#     user_id="surajacchahai11",
#     problem="How to improve efficiency?",
#     # problem_response={"approach": "Lean methodology", "expected_outcome": "10% efficiency boost"},
#     # headings={"title": "Efficiency Improvement Ideas", "category": "Operations"},
#     # content={"details": "Detailed explanation on methodology and implementation."},
    
# )

# Create idea
# try:
#     new_idea = create_idea(idea_data)
#     print("New Idea Created:")
#     print(new_idea)
# except Exception as e:
#     print(f"Error creating idea: {e}")

# Update idea
# idea_id = new_idea.id  # Using the id of the newly created idea

# updated_data = {
#     # "problem": "How to improve efficiency and reduce waste?",
#     "summary": {"key_points": ["Increase productivity", "Reduce waste", "Optimize processes"]}
# }

# try:
#     updated_idea = update_idea(idea_id, updated_data)
#     print("\nUpdated Idea:")
#     print(updated_idea)
# except Exception as e:
#     print(f"Error updating idea: {e}")

# Delete idea
# try:
#     deletion_success = delete_idea(idea_id)
#     if deletion_success:
#         print("\nIdea Deleted Successfully")
# except Exception as e:
#     print(f"Error deleting idea: {e}")



# idea = get_idea_by_user_id_and_slug("67a8ee5de87492411bf8ff14", "hii-22-40-22")
# if idea:
#     # print("Idea found:", idea)
#     print(idea["problem_response"]["content"])
# else:
#     print("No idea found with that user_id and slug.")
