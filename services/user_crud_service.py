from models.user import UserCreate, UserInDB, Credits
from utils.mongodb import get_db  # MongoDB connection utility
from bson.objectid import ObjectId
from pydantic import ValidationError
from typing import Dict, Any


# Function to create a new user
def create_user(user_data: UserCreate) -> UserInDB:
    user_dict = user_data.model_dump()
    try:
        db = get_db()
        collection = db['users']
        result = collection.insert_one(user_dict).inserted_id

        if result:
            print("User inserted successfully.", result)

        user_dict = collection.find_one({"_id": ObjectId(result)})
        user_dict['_id'] = str(user_dict['_id'])
        return user_dict

    except Exception as e:
        raise Exception(f"Error creating user: {e}")


# Function to update an existing user
def update_user(user_id: str, updated_data: Dict[str, Any]) -> UserInDB:
    try:
        db = get_db()
        collection = db['users']
        
        # Update query to set the updated data
        update_query = {'$set': updated_data}
        
        # Perform the update
        result = collection.update_one({'_id': ObjectId(user_id)}, update_query)
        
        if result.modified_count == 0:
            raise Exception("No document was updated")
        
        updated_user = collection.find_one({'_id': ObjectId(user_id)})
        updated_user['_id'] = str(updated_user['_id'])
        return updated_user

    except Exception as e:
        raise Exception(f"Error updating user: {e}")


# Function to delete a user
def delete_user(user_id: str) -> bool:
    try:
        db = get_db()
        collection = db['users']
        
        result = collection.delete_one({'_id': ObjectId(user_id)})
        
        if result.deleted_count == 0:
            raise Exception("No document was deleted")
        
        return True
    
    except Exception as e:
        raise Exception(f"Error deleting user: {e}")


# Function to fetch a user's credits based on their user ID
def get_user_credits(user_id: str) -> int:
    try:
        db = get_db()
        collection = db['users']
        
        user = collection.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            raise Exception("User not found")
        
        return user.get("credits", 0)

    except Exception as e:
        raise Exception(f"Error fetching user credits: {e}")


# def update_user_credits(user_id: str, amount: int) -> Dict[str, Any]:
#     """
#     Increment or decrement the user's credits by the given amount.
#     A positive `amount` will increment, while a negative `amount` will decrement the credits.

#     Args:
#     - user_id (str): The ID of the user whose credits are being updated.
#     - amount (int): The number of credits to add (positive) or subtract (negative).

#     Returns:
#     - Dict[str, Any]: The updated user document containing the user's ID and updated credits.

#     Raises:
#     - Exception: If an error occurs during the update operation.
#     """
#     try:
#         db = get_db()
#         collection = db['users']

#         # Update query to increment or decrement the credits
#         update_query = {'$inc': {'credits': amount}}

#         # Perform the update
#         result = collection.update_one({'_id': ObjectId(user_id)}, update_query)

#         if result.modified_count == 0:
#             raise Exception("No document was updated")

#         # Fetch the updated user document
#         updated_user = collection.find_one({'_id': ObjectId(user_id)})
#         updated_user['_id'] = str(updated_user['_id'])

#         # Return the updated user document
#         return updated_user

#     except Exception as e:
#         raise Exception(f"Error updating user credits: {e}")


from typing import Dict, Any
from bson import ObjectId
from utils.mongodb import get_db
from models.user import Credits

def update_user_credits_by_type(user_id: str, amount: int, credit_type: str) -> Dict[str, Any]:
    """
    Update the user's credits explicitly based on the credit type: 'free' or 'paid'.

    Args:
    - user_id (str): The ID of the user whose credits are being updated.
    - amount (int): Number of credits to add (positive) or subtract (negative).
    - credit_type (str): Type of credit to update ('free' or 'paid').

    Returns:
    - Dict[str, Any]: Updated user document with new credit balances.

    Raises:
    - ValueError: If invalid credit type is provided.
    - Exception: If user not found or update fails.
    """
    try:
        if credit_type not in ['free', 'paid']:
            raise ValueError("Invalid credit type. Must be 'free' or 'paid'.")

        db = get_db()
        collection = db['users']

        user = collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            raise Exception("User not found")

        current_credits = user['credits'][f'{credit_type}_credits']

        if amount < 0 and abs(amount) > current_credits:
            raise Exception(f"Insufficient {credit_type} credits")

        update_query = {
            '$inc': {
                f'credits.{credit_type}_credits': amount
            }
        }

        result = collection.update_one({'_id': ObjectId(user_id)}, update_query)

        if result.modified_count == 0:
            raise Exception("Credit update failed")

        updated_user = collection.find_one({'_id': ObjectId(user_id)})
        updated_user['_id'] = str(updated_user['_id'])
        return updated_user

    except Exception as e:
        raise Exception(f"Error updating user credits: {e}")


# def update_user_credits(user_id: str, amount: int) -> Dict[str, Any]:
#     """
#     Increment or decrement the user's credits by the given amount.
#     The logic for deduction is as follows:
#     - Deduct from `free_credits` first, and if `free_credits` are empty, subtract from `paid_credits`.
#     - Refunds (positive `amount`) are always added to `paid_credits`.

#     Args:
#     - user_id (str): The ID of the user whose credits are being updated.
#     - amount (int): The number of credits to add (positive) or subtract (negative).

#     Returns:
#     - Dict[str, Any]: The updated user document containing the user's ID and updated credits.

#     Raises:
#     - Exception: If an error occurs during the update operation.
#     """
#     try:
#         db = get_db()
#         collection = db['users']

#         # Fetch the current user's credits
#         user = collection.find_one({'_id': ObjectId(user_id)})
#         if not user:
#             raise Exception("User not found")

#         current_free_credits = user['credits']['free_credits']
#         current_paid_credits = user['credits']['paid_credits']

#         # Determine how to handle the update (deduct or add)
#         if amount < 0:
#             # Deduct from free credits first, if there's not enough, deduct from paid credits
#             if current_free_credits >= abs(amount):
#                 update_query = {
#                     '$inc': {
#                         'credits.free_credits': amount  # Subtract from free credits
#                     }
#                 }
#             else:
#                 remaining_deduction = abs(amount) - current_free_credits
#                 update_query = {
#                     '$inc': {
#                         'credits.free_credits': -current_free_credits,  # Exhaust free credits
#                         'credits.paid_credits': -remaining_deduction  # Deduct the remaining from paid credits
#                     }
#                 }
#         else:
#             # Add the credits to paid credits when it's a positive amount (refund or adding credits)
#             update_query = {
#                 '$inc': {
#                     'credits.paid_credits': amount  # Add to paid credits
#                 }
#             }

#         # Perform the update
#         result = collection.update_one({'_id': ObjectId(user_id)}, update_query)

#         if result.modified_count == 0:
#             raise Exception("No document was updated")

#         # Fetch the updated user document
#         updated_user = collection.find_one({'_id': ObjectId(user_id)})
#         updated_user['_id'] = str(updated_user['_id'])

#         # Return the updated user document
#         return updated_user

#     except Exception as e:
#         raise Exception(f"Error updating user credits: {e}")



# user_id = "67a8ee5de87492411bf8ff14"
# amount = 78  # Decrement by -1
# updated_user = update_user_credits(user_id, amount)
# print(updated_user)


# credits = get_user_credits("67a8ee5de87492411bf8ff14")
# print(credits)


# Deduct 1 free credit
# print(update_user_credits_by_type(user_id="67a8ee5de87492411bf8ff14", amount=20, credit_type="free"))


# take the user data from the form properly 
def get_or_update_form_filled_status(user_id: str, new_status: bool = None) -> bool:
    """
    Get or update the `formFilled` status of a user.

    Args:
    - user_id (str): The ID of the user.
    - new_status (bool, optional): If provided, updates the formFilled field to this value.

    Returns:
    - bool: The current or updated formFilled status.

    Raises:
    - Exception: If user not found or update fails.
    """
    try:
        db = get_db()
        collection = db['users']
        user_object_id = ObjectId(user_id)

        # Check if user exists
        user = collection.find_one({'_id': user_object_id})
        if not user:
            raise Exception("User not found")

        # If update is requested
        if new_status is not None:
            result = collection.update_one(
                {'_id': user_object_id},
                {'$set': {'formFilled': new_status}}
            )
            if result.modified_count == 0:
                raise Exception("Failed to update formFilled status")
            return new_status

        # If just retrieving status
        return user.get('formFilled', False)

    except Exception as e:
        raise Exception(f"Error getting or updating formFilled status: {e}")
    

def set_form_filled_default_for_all_users():
    """
    Add `formFilled: False` to all user documents that do not have it.
    """
    try:
        db = get_db()
        users_collection = db['users']

        # Find and update all users where 'formFilled' field is missing
        result = users_collection.update_many(
            {'formFilled': {'$exists': False}},
            {'$set': {'formFilled': False}}
        )

        print(f"Updated {result.modified_count} users with formFilled: False")

    except Exception as e:
        raise Exception(f"Error updating users: {e}")
    

# set_form_filled_default_for_all_users()


def add_access_and_status_to_all_collections():
    """
    Add `access_level` and `status` fields to all collections in the database,
    except the 'report' collection where these fields will be set to 'paid'.
    """
    try:
        db = get_db()  # Replace with your actual DB connection if needed
        collection_names = db.list_collection_names()

        for name in collection_names:
            collection = db[name]
            if name == 'report':
                # Set 'access_level' and 'status' to 'paid' for reports
                result = collection.update_many(
                    {},
                    {'$set': {
                        'access_level': 'paid',
                        'status': 'paid'
                    }}
                )
                print(f"Updated {result.modified_count} documents in '{name}' collection to paid.")
            else:
                # Add fields only if they do not exist
                result = collection.update_many(
                    {
                        '$or': [
                            {'access_level': {'$exists': False}},
                            {'status': {'$exists': False}}
                        ]
                    },
                    {'$set': {
                        'access_level': 'free',
                        'status': 'free'
                    }}
                )
                print(f"Updated {result.modified_count} documents in '{name}' collection with default values.")

    except Exception as e:
        raise Exception(f"Error updating collections: {e}")


# add_access_and_status_to_all_collections()

def remove_access_and_status_from_all_collections():
    """
    Remove `access_level` and `status` fields from all collections in the database.
    """
    try:
        db = get_db()  # Replace with your actual DB connection if needed
        collection_names = db.list_collection_names()

        for name in collection_names:
            collection = db[name]
            result = collection.update_many(
                {
                    '$or': [
                        {'access_level': {'$exists': True}},
                        {'status': {'$exists': True}}
                    ]
                },
                {'$unset': {
                    'access_level': "",
                    'status': ""
                }}
            )
            print(f"Removed fields from {result.modified_count} documents in '{name}' collection.")

    except Exception as e:
        raise Exception(f"Error reverting collections: {e}")
# remove_access_and_status_from_all_collections()


def set_paid_access_for_reports():
    """
    Set `access_level` and `status` to 'paid' for all documents in the 'reports' collection.
    """
    try:
        db = get_db()  # Replace with your actual DB connection if needed
        collection = db['reports']

        result = collection.update_many(
            {},
            {'$set': {
                'access_level': 'paid',
                'status': 'paid'
            }}
        )

        print(f"Updated {result.modified_count} documents in 'reports' collection with paid access.")

    except Exception as e:
        raise Exception(f"Error updating reports collection: {e}")
# set_paid_access_for_reports()

def assign_two_free_credits_to_all_users():
    """
    Set `credits.free_credits` to 2 for all users in the 'users' collection.
    """
    try:
        db = get_db()  # Replace with your actual DB connection if needed
        users_collection = db['users']

        result = users_collection.update_many(
            {},
            {'$set': {'credits.free_credits': 2}}
        )

        print(f"Updated {result.modified_count} users with 2 free credits.")

    except Exception as e:
        raise Exception(f"Error updating user credits: {e}")
    
# assign_two_free_credits_to_all_users()

def add_paid_status_to_payments():
    """
    Add `status: 'paid'` to all documents in the 'payments' collection that don't already have a status.
    """
    try:
        db = get_db()  # Replace with your actual DB connection
        payments_collection = db['payments']

        result = payments_collection.update_many(
            {'status': {'$exists': False}},  # Only documents without a status field
            {'$set': {'status': 'paid'}}
        )

        print(f"Added status 'paid' to {result.modified_count} payments.")

    except Exception as e:
        raise Exception(f"Error updating payments collection: {e}")
add_paid_status_to_payments()