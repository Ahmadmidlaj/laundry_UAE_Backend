from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.models import UserRole

class UserBase(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    mobile: str
    flat_number: Optional[str] = None
    building_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.CUSTOMER # Default role

class UserResponse(UserBase):
    id: int
    role: UserRole

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = True
    flat_number: Optional[str] = None
    building_name: Optional[str] = None