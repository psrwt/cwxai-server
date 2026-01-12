from utils.mongodb import get_db
from models.user import UserCreate, Credits  # Import the UserCreate Pydantic model and Credits model

def save_user(user_info):
    """Save or update the user in the database."""
    db = get_db()
    users_collection = db["users"]

    # Validate user data using the Pydantic model
    user = UserCreate(**user_info)  # This will validate and create a UserCreate instance
    
    # Prepare the credits information for insertion
    credits_data = {
        "paid_credits": user.credits.paid_credits,
        "free_credits": user.credits.free_credits
    }

    # Check if the user already exists
    existing_user = users_collection.find_one({"email": user.email})
    if not existing_user:
        # Create new user with default credits (0 for both paid and free)
        user_id = users_collection.insert_one({
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "role": user.role,  # Include the role
            "credits": {"paid_credits": 0, "free_credits": 2},  # Initialize credits to 0
            "created_at": db.command("serverStatus")["localTime"]  # Timestamp
        }).inserted_id
    else:
        # Update existing user, keep existing credits if not explicitly changed
        update_data = {
            "name": user.name,
            "picture": user.picture,
            "role": user.role
        }

        # Only update credits if they were provided in the user data
        if user.credits.paid_credits != 0 or user.credits.free_credits != 0:
            update_data["credits"] = {
                "paid_credits": user.credits.paid_credits,
                "free_credits": user.credits.free_credits
            }

        # Apply the update
        users_collection.update_one(
            {"_id": existing_user["_id"]},
            {"$set": update_data}
        )
        user_id = existing_user["_id"]

    return user_id
