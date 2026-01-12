import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
# print(MONGO_URI, MONGO_DB_NAME)

try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    logger.info(f"Connected to MongoDB database: {MONGO_DB_NAME}")
except Exception as e:
    logger.error("Failed to connect to MongoDB", exc_info=True)
    raise e

def get_db():
    """Return the database instance."""
    return db
