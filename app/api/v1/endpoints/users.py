from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.session import get_db
from app.api.deps import RoleChecker, get_current_user
from app.models.models import User, UserRole
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()



# CUSTOMER/ALL: Get own profile details
@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    return current_user

# CUSTOMER/ALL: Update own profile
@router.patch("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # We only allow updating specific fields for self
    update_data = user_in.model_dump(exclude_unset=True)
    
    # Security check: Prevent users from promoting themselves to ADMIN
    if "role" in update_data and current_user.role != UserRole.ADMIN:
        del update_data["role"]

    for key, value in update_data.items():
        setattr(current_user, key, value)
        
    await db.commit()
    await db.refresh(current_user)
    return current_user

# ADMIN ONLY: List all users (to see who to promote)
@router.get("/", response_model=List[UserResponse], dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()

# ADMIN ONLY: Change a user's role or status
@router.patch("/{user_id}", response_model=UserResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_user_role(user_id: int, user_in: UserUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
        
    await db.commit()
    await db.refresh(user)
    return user
