import json
from bson import ObjectId
from datetime import datetime

# Recursive function to serialize dictionaries with non-serializable types
def json_converter(obj):
    if isinstance(obj, dict):
        # If it's a dictionary, recursively serialize the keys and values
        return {key: json_converter(value) for key, value in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)  # Convert ObjectId to string
    elif isinstance(obj, datetime):
        return obj.isoformat()  # Convert datetime to ISO 8601 string
    return obj  # Return the value as is if it's already serializable