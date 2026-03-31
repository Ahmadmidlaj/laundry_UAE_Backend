from app.services.order_service import admin_force_update_order
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import RoleChecker, get_current_user
from app.models.models import User, Order, OrderItem, OrderStatus, LaundryItem, UserRole
from app.schemas.order import AdminOrderUpdate, OrderCreate, OrderResponse
from app.services.pricing_service import calculate_order_price
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

router = APIRouter()


@router.get("/all", response_model=list[OrderResponse], dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def get_all_orders_admin(db: AsyncSession = Depends(get_db)):
    """ADMIN ONLY: Fetch every single order in the system."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.customer), 
            selectinload(Order.items).joinedload(OrderItem.item)
        )
        .order_by(Order.id.desc())
    )
    return result.scalars().all()


@router.get("/", response_model=list[OrderResponse])
async def get_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all orders for the logged-in customer."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == current_user.id)
        .options(selectinload(Order.customer), 
            # THE FIX: Added joinedload here
            selectinload(Order.items).joinedload(OrderItem.item))  # <--- THIS IS THE FIX
        .order_by(Order.id.desc())
    )
    return result.scalars().all()

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.customer),selectinload(Order.items).joinedload(OrderItem.item) # <--- ADD THIS so details show customer info
        )
    )
           
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    return order

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


    order_id = new_order.id

    # 3. Add the items to the order
    for item_data in order_in.items:
        # Fetch current unit price to "lock it in"
        res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
        li = res.scalars().first()
        
        oi = OrderItem(
            order_id=order_id,
            item_id=item_data.item_id,
            estimated_quantity=item_data.estimated_quantity,
            unit_price=li.base_price if li else 0.0
        )
        db.add(oi)
    

    await db.commit()
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.customer), 
            # THE FIX: Added joinedload here so the newly created order returns names
            selectinload(Order.items).joinedload(OrderItem.item)) 
    )
    final_order = result.scalars().first()
    # await db.refresh(new_order)
    # return new_order
    return final_order





@router.patch("/{order_id}/admin", response_model=OrderResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_order_admin(
    order_id: int,
    update_data: AdminOrderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """ADMIN ONLY: Force update any order detail (quantities, status, dates)."""
    return await admin_force_update_order(db, order_id, update_data)