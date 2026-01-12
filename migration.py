from pymongo import MongoClient
from bson import ObjectId

# Connect to MongoDB
client = MongoClient("mongodb+srv://surajintellact:qcdXj4s5yCPayyNY@cluster0.iwgh7.mongodb.net/?retryWrites=true&w=majority")  # Change the URI if necessary
db = client["snapsearchdb"]
users_collection = db["users"]

# Migration function to update the user schema
def migrate_user_data():
    users = users_collection.find({"credits": {"$exists": True}})  # Find all users with the old credits format
    for user in users:
        # Check if the user has the old "credits" field
        if isinstance(user.get("credits"), int):  # Old format (e.g., `credits: 11`)
            paid_credits = user["credits"]
            free_credits = 0  # Set free_credits to 0 as it's not part of the old structure
            # Update the user's document with the new Credits structure
            users_collection.update_one(
                {"_id": ObjectId(user["_id"])},
                {"$set": {"credits": {"paid_credits": paid_credits, "free_credits": free_credits}}}
            )
            print(f"User {user['_id']} migrated")

# Run the migration
migrate_user_data()
