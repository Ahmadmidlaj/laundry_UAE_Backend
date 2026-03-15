from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.core import security
from app.models.models import User
from app.schemas.user import UserCreate, UserResponse, Token

from app.core.security import create_access_token
from datetime import timedelta

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if mobile already exists
    result = await db.execute(select(User).where(User.mobile == user_in.mobile))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Mobile number already registered")
    
    db_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        mobile=user_in.mobile,
        hashed_password=security.get_password_hash(user_in.password),
        role=user_in.role,
        flat_number=user_in.flat_number,
        building_name=user_in.building_name
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.post("/login/access-token", response_model=Token)
async def login(db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    result = await db.execute(select(User).where(User.mobile == form_data.username))
    user = result.scalars().first()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect mobile or password")
    
    return {
        "access_token": security.create_access_token(user.id),
        "token_type": "bearer",
    }

@router.post("/forgot-password")
async def forgot_password(mobile: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.mobile == mobile))
    user = result.scalars().first()
    if not user:
        # For security, don't confirm if the user exists or not
        return {"message": "If the account exists, a reset link has been generated."}
    
    # Generate a short-lived token (15 mins)
    reset_token = create_access_token(user.id, expires_delta=timedelta(minutes=15))
    # In a real app, you'd send this via SMS/Email. For now, we return it.
    return {"reset_token": reset_token}

@router.post("/reset-password")
async def reset_password(token: str, new_password: str, db: AsyncSession = Depends(get_db)):
    # Verify the token and get user ID
    user = await get_current_user(db, token) 
    
    user.hashed_password = security.get_password_hash(new_password)
    await db.commit()
    return {"message": "Password updated successfully"}