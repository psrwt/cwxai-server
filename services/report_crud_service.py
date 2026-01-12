from models.report_schmea import ReportCreate, ReportInDB  # Assuming the Report models are in the report file
from utils.mongodb import get_db  # MongoDB connection utility
from bson.objectid import ObjectId
from pydantic import ValidationError
from typing import Dict, Any
from datetime import datetime


# Function to create a new report
def create_report(report_data: ReportCreate) -> ReportInDB:
    report_dict = report_data.dict()  # Convert Pydantic model to dict
    try:
        db = get_db()
        collection = db['reports']
        
        # Insert the report data into the MongoDB collection
        result = collection.insert_one(report_dict).inserted_id

        if result:
            print("Report inserted successfully.", result)

        # Fetch the newly inserted report from the database
        report_dict = collection.find_one({"_id": ObjectId(result)})
        report_dict['_id'] = str(report_dict['_id'])  # Convert ObjectId to string

        # Return the report data as a Pydantic model
        return report_dict

    except Exception as e:
        raise Exception(f"Error creating report: {e}")


# Function to get a report by its ID
def get_report(report_id: str) -> ReportInDB:
    try:
        db = get_db()
        collection = db['reports']
        
        # Find the report by its ObjectId
        report_dict = collection.find_one({"_id": ObjectId(report_id)})

        if report_dict:
            report_dict['_id'] = str(report_dict['_id'])  # Convert ObjectId to string
            return report_dict
        else:
            raise Exception(f"Report with id {report_id} not found.")
    
    except Exception as e:
        raise Exception(f"Error fetching report: {e}")


# Function to update an existing report
def update_report(report_id: str, update_data: Dict[str, Any]) -> ReportInDB:
    try:
        db = get_db()
        collection = db['reports']
        
        # Update the report using its ObjectId
        result = collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise Exception(f"No report found with id {report_id}.")

        # Fetch the updated report data
        updated_report = collection.find_one({"_id": ObjectId(report_id)})
        updated_report['_id'] = str(updated_report['_id'])  # Convert ObjectId to string
        
        return updated_report

    except Exception as e:
        raise Exception(f"Error updating report: {e}")


# Function to delete a report by its ID
def delete_report(report_id: str) -> bool:
    try:
        db = get_db()
        collection = db['reports']
        
        # Delete the report using its ObjectId
        result = collection.delete_one({"_id": ObjectId(report_id)})
        
        if result.deleted_count == 0:
            raise Exception(f"No report found with id {report_id}.")
        
        return True

    except Exception as e:
        raise Exception(f"Error deleting report: {e}")
    
# Service function to get a report by user_id and user_idea_id
# def get_report_by_user_idea_id(user_id: str, user_idea_id: str) -> ReportInDB:
#     try:
#         db = get_db()
#         collection = db['reports']
        
#         # Query to find the report by user_id and user_idea_id
#         report_dict = collection.find_one({"user_id": user_id, "user_idea_id": user_idea_id})

#         if report_dict:
#             report_dict['_id'] = str(report_dict['_id'])  # Convert ObjectId to string
#             return report_dict
#         else:
#             raise Exception(f"Report for user {user_id} and user_idea_id {user_idea_id} not found.")
    
#     except Exception as e:
#         raise Exception(f"Error fetching report for user {user_id} and user_idea_id {user_idea_id}: {e}")
    

# Service function to get a report by user_id and user_idea_id
def get_report_by_user_id_and_slug(user_id: str, slug: str) -> ReportInDB:
    try:
        db = get_db()
        collection = db['reports']
        
        # Trim and ensure proper format
        user_id = user_id.strip()  # Strip any spaces
        slug = slug.strip().lower()  # Strip and lowercase slug to ensure uniformity
        
        # Debugging: Print the values you're querying for
        print(f"Querying for user_id: {user_id}, slug: {slug}")

        # Query to find the report by user_id and slug
        report_dict = collection.find_one({"user_id": user_id, "slug": slug})

        if report_dict:
            # Convert ObjectId to string for serialization
            report_dict['_id'] = str(report_dict['_id'])
            return report_dict
        else:
            raise Exception(f"Report for user {user_id} and slug {slug} not found.")
    
    except Exception as e:
        raise Exception(f"Error fetching report for user {user_id} and slug {slug}: {e}")


# print(get_report_by_user_id_and_slug("67b24f45f0c1a4308cc198dc", "hello-23-40-05"))


# # Create a new report instance
# new_report_data = ReportCreate(
#     user_id="user123",
#     user_idea_id="idea456",
#     report_file_path="path/to/report/file.pdf",
#     created_at=datetime.utcnow(),
#     updated_at=datetime.utcnow(),
#     report_content="This is a summary of the report."
# )

# # Call the create_report function to insert it into the database
# created_report = create_report(new_report_data)
# print("Created report:", created_report)


# from crud.report_crud import get_report

# report_id = "605c72ef1532073ee88345fb"  # This would be the ObjectId of the report you want to fetch

# try:
#     report = get_report(report_id)
#     print("Report fetched:", report)
# except Exception as e:
#     print(f"Error: {e}")


# from crud.report_crud import update_report

# report_id = "605c72ef1532073ee88345fb"
# update_data = {
#     "report_content": "Updated content for the report.",
#     "updated_at": datetime.utcnow()  # Update timestamp as well
# }

# try:
#     updated_report = update_report(report_id, update_data)
#     print("Updated report:", updated_report)
# except Exception as e:
#     print(f"Error: {e}")



# from crud.report_crud import delete_report

# report_id = "605c72ef1532073ee88345fb"  # This would be the ObjectId of the report you want to delete

# try:
#     is_deleted = delete_report(report_id)
#     if is_deleted:
#         print(f"Report with ID {report_id} has been deleted.")
# except Exception as e:
#     print(f"Error: {e}")
