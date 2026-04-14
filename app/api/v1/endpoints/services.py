from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.db.session import get_db
from app.api.deps import RoleChecker
from app.models.models import ServiceCategory, UserRole

router = APIRouter()

# --- Schemas ---
class CategoryCreate(BaseModel):
    name: str

class CategoryResponse(BaseModel):
    id: int
    name: str
    is_active: bool

# --- Endpoints ---

# PUBLIC: Fetch available service categories (Used by Frontend Booking & Admin)
@router.get("/categories", response_model=list[CategoryResponse])
async def list_service_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceCategory).where(ServiceCategory.is_active == True)
    )
    return result.scalars().all()

# ADMIN ONLY: Add a new category (e.g., "Shoe Cleaning")
@router.post("/categories", response_model=CategoryResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_service_category(cat_in: CategoryCreate, db: AsyncSession = Depends(get_db)):
    # Check if exists
    result = await db.execute(select(ServiceCategory).where(ServiceCategory.name == cat_in.name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Category already exists")
        
    new_cat = ServiceCategory(name=cat_in.name)
    db.add(new_cat)
    await db.commit()
    await db.refresh(new_cat)
    return new_cat

# ADMIN ONLY: Soft delete a category so it hides from the UI
@router.delete("/categories/{cat_id}", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_service_category(cat_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ServiceCategory).where(ServiceCategory.id == cat_id))
    cat = result.scalars().first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
        
    cat.is_active = False # Soft delete to protect old order history
    await db.commit()
    return {"message": "Category removed"}