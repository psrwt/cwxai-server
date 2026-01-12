from utils.mongodb import get_db
from models.user_form_data_schema import UserFormData
from bson.objectid import ObjectId

def create_user_form_data(form_data: UserFormData) -> str:
    """
    Create a new user form data document.

    Returns:
    - str: The inserted document ID as a string.
    """
    try:
        db = get_db()
        collection = db['user_data']
        result = collection.insert_one(form_data.model_dump())
        return str(result.inserted_id)
    except Exception as e:
        raise Exception(f"Error creating user form data: {e}")



def get_user_form_data_by_user_id(user_id: str) -> dict:
    """
    Retrieve form data by user_id.
    
    Returns:
    - dict: User form data or None if not found.
    """
    try:
        db = get_db()
        collection = db['user_data']
        form_data = collection.find_one({'user_id': user_id})
        if form_data:
            form_data['_id'] = str(form_data['_id'])
        return form_data
    except Exception as e:
        raise Exception(f"Error retrieving user form data: {e}")


def update_user_form_data(user_id: str, updated_data: dict) -> dict:
    """
    Update the user form data by user_id.

    Returns:
    - dict: Updated document.
    """
    try:
        db = get_db()
        collection = db['user_data']
        result = collection.update_one({'user_id': user_id}, {'$set': updated_data})

        if result.modified_count == 0:
            raise Exception("No document was updated")

        updated_doc = collection.find_one({'user_id': user_id})
        updated_doc['_id'] = str(updated_doc['_id'])
        return updated_doc
    except Exception as e:
        raise Exception(f"Error updating user form data: {e}")


def delete_user_form_data(user_id: str) -> bool:
    """
    Delete the user form data by user_id.

    Returns:
    - bool: True if deleted, False otherwise.
    """
    try:
        db = get_db()
        collection = db['user_data']
        result = collection.delete_one({'user_id': user_id})
        return result.deleted_count > 0
    except Exception as e:
        raise Exception(f"Error deleting user form data: {e}")


def list_all_user_form_data() -> list:
    """
    List all user form data documents.

    Returns:
    - list: List of user form data dicts.
    """
    try:
        db = get_db()
        collection = db['user_data']
        documents = list(collection.find({}))
        for doc in documents:
            doc['_id'] = str(doc['_id'])
        return documents
    except Exception as e:
        raise Exception(f"Error listing user form data: {e}")

