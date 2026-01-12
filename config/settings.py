import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = os.getenv("MONGO_DB_NAME", "chat_history")
    CACHE_DIR = "./cache"
    CHUNK_SIZE = 1200
    CHUNK_OVERLAP = 200
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    FAISS_INDEX_DIR = "./cache/faiss_index"
        # JWT Configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    CORS_METHODS = os.getenv("CORS_METHODS", "GET,POST,OPTIONS").split(",")