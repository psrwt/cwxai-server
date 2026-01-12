from pydantic import BaseModel, EmailStr
from typing import Optional

class ChillCreate(BaseModel):
    user_id : str
    chill_text : str

    class Config:
        form_attributes = True

class ChillInDB(ChillCreate):
    id: str  # MongoDB ObjectId as a string

    class Config:
        form_attributes = True
 