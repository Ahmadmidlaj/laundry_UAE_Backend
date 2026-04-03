from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.session import get_db
from app.models.models import Building, User, UserRole
from app.schemas.building import BuildingCreate, BuildingUpdate, BuildingResponse
from app.api.deps import get_current_user

router = APIRouter()

# PUBLIC: Used by the Frontend Register Page
@router.get("/", response_model=List[BuildingResponse])
async def get_active_buildings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Building).where(Building.is_active == True))
    return result.scalars().all()

# PROTECTED: Admin Only
async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

@router.post("/", response_model=BuildingResponse)
async def create_building(
    building_in: BuildingCreate, 
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(Building).where(Building.name == building_in.name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Building already exists")
    
    db_building = Building(**building_in.dict())
    db.add(db_building)
    await db.commit()
    await db.refresh(db_building)
    return db_building

@router.put("/{building_id}", response_model=BuildingResponse)
async def update_building(
    building_id: int, 
    building_in: BuildingUpdate, 
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    result = await db.execute(select(Building).where(Building.id == building_id))
    db_building = result.scalars().first()
    if not db_building:
        raise HTTPException(status_code=404, detail="Building not found")
    
    update_data = building_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_building, key, value)
        
    await db.commit()
    await db.refresh(db_building)
    return db_building