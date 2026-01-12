from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal
from datetime import datetime

class ReportCreate(BaseModel):
    user_id: str  # Foreign Key to the user table
    user_idea_id: str  # Foreign Key to the Idea table
    slug: str

    access_level: Literal["free", "paid"] = "free"  # What the user is entitled to
    status: Literal["free", "upgraded", "paid", "processing", "error"] = "free"  # Report lifecycle

    free_report_content: Optional[Dict[str, Any]] = None  # Content for free version
    report_content: Optional[Dict[str, Any]] = None  # Full paid content
    report_json_content: Optional[Dict[str, Any]] = None # Full report json content
    report_file_path: Optional[str] = None  # Optional PDF file path

    created_at: datetime  # When the report record was created
    updated_at: datetime  # When it was last modified

    class Config:
        from_attributes = True

class ReportInDB(ReportCreate):
    id: str  # DB primary key (e.g., MongoDB ObjectId)

    class Config:
        from_attributes = True
