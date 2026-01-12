from pydantic import BaseModel, EmailStr
from typing import Optional

class Credits(BaseModel):
    paid_credits: int = 0
    free_credits: int = 0

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    picture: Optional[str] = None
    role: str = "user"  # Default role for users (can be overwritten when needed)
    credits: Credits = Credits()  # Default to 0 paid and free credits 
    formFilled: bool = False

    class Config:
        # Allow ORM models to be used (if using with MongoDB or SQLAlchemy)
        form_attributes = True

class UserInDB(UserCreate):
    id: str  # MongoDB ObjectId as a string (assuming the _id field is a string)

    class Config:
        form_attributes = True


# user_data = UserCreate(
#     email="user@example.com",
#     name="John Doe",
#     credits=Credits(paid_credits=11, free_credits=1)
# )
# print(user_data)
