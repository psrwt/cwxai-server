from pydantic import BaseModel, EmailStr
from typing import Optional, List

class UserFormData(BaseModel):
    user_id: str  # foreign key reference to UserInDB.id
    fullName: str
    email: EmailStr
    country: str
    role: str
    experience: str
    goals: List[str]
    currentFocus: str
    audience: List[str]
    domains: List[str]
    reportFormat: str
    contentStyle: str
    newsletters: List[str]
    challenge: Optional[str] = None
    highlight: Optional[str] = None
    consent: bool

    class Config:
        form_attributes = True
