from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import RoleChecker
from app.models.models import UserRole, Offer
from app.schemas.offer import OfferCreate, OfferResponse
from typing import List
from sqlalchemy import select 


router = APIRouter()

@router.post("/", response_model=OfferResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_offer(offer_in: OfferCreate, db: AsyncSession = Depends(get_db)):
    db_offer = Offer(**offer_in.model_dump())
    db.add(db_offer)
    await db.commit()
    await db.refresh(db_offer)
    return db_offer

@router.get("/", response_model=List[OfferResponse])
async def list_offers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Offer))
    return result.scalars().all()