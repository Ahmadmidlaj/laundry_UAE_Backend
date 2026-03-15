from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import User, Order, OrderItem, OrderStatus, LaundryItem
from app.schemas.order import OrderCreate, OrderResponse
from app.services.pricing_service import calculate_order_price
from sqlalchemy.future import select

router = APIRouter()

@router.post("/", response_model=OrderResponse)
async def create_order(
    order_in: OrderCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Calculate pricing
    pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
    totals = await calculate_order_price(db, pricing_data)
    
    # 2. Create the Order header
    new_order = Order(
        customer_id=current_user.id,
        status=OrderStatus.NEW_ORDER,
        pickup_date=order_in.pickup_date,
        pickup_time=order_in.pickup_time,
        notes=order_in.notes,
        estimated_price=totals["final_total"],
        discount_applied=totals["discount_applied"]
    )
    db.add(new_order)
    await db.flush() # Get the order ID without committing yet

    # 3. Add the items to the order
    for item_data in order_in.items:
        # Fetch current unit price to "lock it in"
        res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
        li = res.scalars().first()
        
        oi = OrderItem(
            order_id=new_order.id,
            item_id=item_data.item_id,
            estimated_quantity=item_data.estimated_quantity,
            unit_price=li.base_price if li else 0.0
        )
        db.add(oi)

    await db.commit()
    await db.refresh(new_order)
    return new_order