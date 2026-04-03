from pydantic import BaseModel, EmailStr, field_validator
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
    referral_code: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_must_be_numeric(cls, v: str) -> str:
        # Check if password is only digits and >= 4
        if not v.isdigit():
            raise ValueError('Password must contain only numbers')
        if len(v) < 4:
            raise ValueError('Password must be at least 4 digits')
        return v

class UserResponse(UserBase):
    id: int
    role: UserRole
    referral_code: Optional[str] = None
    wallet_balance: Optional[float] = 0.0
    referred_by_id: Optional[int] = None

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
    password: Optional[str] = None