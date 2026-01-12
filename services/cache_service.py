import pickle
import os
# from config.settings import Config
from typing import Any
from dotenv import load_dotenv

load_dotenv()


class CacheService:
    def __init__(self):
        os.makedirs(os.getenv("CACHE_DIR"), exist_ok=True)

    def save_to_cache(self, file_path: str, data: Any):
        try:
            with open(file_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"Error saving to cache {file_path}: {e}")

    def load_from_cache(self, file_path: str) -> Any:
        try:
            with open(file_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading from cache {file_path}: {e}")
            return None