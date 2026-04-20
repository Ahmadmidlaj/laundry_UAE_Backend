from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.repository import item_repo
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse
from app.api.deps import RoleChecker
from app.models.models import UserRole

from app.models.models import ServiceCategory

router = APIRouter()

# PUBLIC/ALL ROLES: View the price list
@router.get("/", response_model=List[ItemResponse])
async def list_items(db: AsyncSession = Depends(get_db)):
    return await item_repo.get_all_items(db)

# ADMIN ONLY: Add new laundry service
@router.post("/", 
    response_model=ItemResponse, 
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def create_new_item(item_in: ItemCreate, db: AsyncSession = Depends(get_db)):
    return await item_repo.create_item(db, item_in)

# ADMIN ONLY: Update pricing
@router.patch("/{item_id}", 
    response_model=ItemResponse, 
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def update_existing_item(item_id: int, item_in: ItemUpdate, db: AsyncSession = Depends(get_db)):
    updated = await item_repo.update_item(db, item_id, item_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")
    return updated

