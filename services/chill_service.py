# services/chill_service.py
from models.chill import ChillCreate, ChillInDB
from utils.mongodb import get_db  # MongoDB connection utility
from bson.objectid import ObjectId
from pydantic import ValidationError

def create_chill_text(user_id: str, chill_text: str):
    """Create a new chill text for a specific user."""
    try:
        # Validate the input data using the ChillCreate Pydantic model
        chill = ChillCreate(user_id=user_id, chill_text=chill_text)

        # Get MongoDB connection
        db = get_db()
        chill_data = {
            "user_id": chill.user_id,
            "chill_text": chill.chill_text,
            "created_at": db.command("serverStatus")["localTime"]  # Timestamp
        }

        # Insert the chill text into MongoDB
        chill_id = db['chill_texts'].insert_one(chill_data).inserted_id

        # Return the created chill text with the ID
        created_chill = db['chill_texts'].find_one({"_id": ObjectId(chill_id)})
        created_chill['_id'] = str(created_chill['_id'])  # Convert ObjectId to string
        return created_chill

    except ValidationError as e:
        return {"message": "Invalid chill text data", "errors": e.errors()}
    except Exception as e:
        return {"message": "Error creating chill text", "error": str(e)}

def get_chill_text_with_user(user_id: str):
    """Get chill text for a specific user and their associated user details."""
    try:
        db = get_db()
        
        # Fetch chill text based on user_id
        chill = db['chill_texts'].find_one({"user_id": user_id})
        
        if chill:
            # Get associated user based on user_id (manual join)
            user = db['users'].find_one({"_id": ObjectId(user_id)})
            if user:
                # Add the user data to the chill text
                chill['_id'] = str(chill['_id'])  # Convert ObjectId to string
                chill['user'] = {
                    "id": str(user["_id"]),
                    "email": user["email"],
                    "name": user["name"],
                    "role": user["role"],
                    "picture": user["picture"]
                }
                return chill
            else:
                return {"message": "User not found"}
        else:
            return {"message": "Chill text not found for this user"}

    except Exception as e:
        return {"message": "Error fetching chill text and user", "error": str(e)}
