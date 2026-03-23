from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.db.session import get_db
from app.api.deps import RoleChecker
from app.models.models import OrderItem, UserRole, Order, OrderStatus
from app.schemas.order import OrderResponse
from app.schemas.pickup import PickupCreate
from app.schemas.delivery import DeliveryCreate 
from app.services.order_service import process_delivery, process_pickup
from sqlalchemy.orm import selectinload
router = APIRouter()

# 1. View Pickup Queue (NEW_ORDER status)
@router.get("/pickup-queue", 
    response_model=List[OrderResponse],
    dependencies=[Depends(RoleChecker([UserRole.EMPLOYEE, UserRole.ADMIN]))]
)
async def get_pickup_queue(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.status == OrderStatus.NEW_ORDER)
        .options(selectinload(Order.customer), selectinload(Order.items).joinedload(OrderItem.item))  # <--- ADDED
        .order_by(Order.pickup_date)         # <--- Also fixed .order_at to .order_by
    )
    return result.scalars().all()

# 2. Confirm Pickup (Create Pickup Document)
@router.post("/{order_id}/pickup", 
    response_model=OrderResponse,
    dependencies=[Depends(RoleChecker([UserRole.EMPLOYEE, UserRole.ADMIN]))]
)
async def confirm_pickup(
    order_id: int, 
    pickup_in: PickupCreate, 
    db: AsyncSession = Depends(get_db)
):
    return await process_pickup(db, order_id, pickup_in)


# 3. View Delivery Queue (PICKED_UP status)
@router.get("/delivery-queue", 
    response_model=List[OrderResponse],
    dependencies=[Depends(RoleChecker([UserRole.EMPLOYEE, UserRole.ADMIN]))]
)
async def get_delivery_queue(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.status == OrderStatus.PICKED_UP)
        .options(selectinload(Order.customer),selectinload(Order.items).joinedload(OrderItem.item))  # <--- ADDED
        .order_by(Order.id.desc())
    )
    return result.scalars().all()

# 4. Confirm Delivery (Create Delivery Document)
@router.post("/{order_id}/deliver", 
    response_model=OrderResponse,
    dependencies=[Depends(RoleChecker([UserRole.EMPLOYEE, UserRole.ADMIN]))]
)
async def confirm_delivery(
    order_id: int, 
    delivery_in: DeliveryCreate, 
    db: AsyncSession = Depends(get_db)
):
    return await process_delivery(db, order_id, delivery_in)