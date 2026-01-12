from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class IdeaCreate(BaseModel):
    user_id: str
    problem: str
    title : str
    slug : str
    location : Optional[str] = None
    problem_response: Optional[Dict[str, Any]] = None  # JSON-like structure (dictionary)
    headings: Optional[Dict[str, Any]] = None  # JSON-like structure (dictionary)
    queries : Optional[Dict[str, Any]] = None # for storing the search queries
    query_links : Optional[Dict[str, Any]] = None # in order to store the searched query links
    content: Optional[Dict[str, Any]] = None  # JSON-like structure (dictionary)
    summary: Optional[Dict[str, Any]] = None  # JSON-like structure (dictionary)
    created_at: datetime  # Timestamp for when the report was created
    updated_at: datetime  # Timestamp for when the report was created

    class Config:
        from_attributes = True

class IdeaInDB(IdeaCreate):
    id: str  # MongoDB ObjectId as a string

    class Config:
        from_attributes = True
