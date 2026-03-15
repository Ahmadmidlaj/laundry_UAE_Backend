from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import Order, OrderItem, OrderStatus, LaundryItem, Transaction
from app.services.pricing_service import calculate_order_price
from app.schemas.pickup import PickupCreate
from app.schemas.delivery import DeliveryCreate
from fastapi import HTTPException

async def process_pickup(db: AsyncSession, order_id: int, pickup_data: PickupCreate) -> Order:
    # 1. Fetch Order with Items
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    
    if not order or order.status != OrderStatus.NEW_ORDER:
        raise HTTPException(status_code=400, detail="Order not found or already picked up")

    # 2. Recalculate Final Price using actual quantities
    pricing_input = [{"item_id": i.item_id, "quantity": i.final_quantity} for i in pickup_data.items]
    totals = await calculate_order_price(db, pricing_input)

    # 3. Update OrderItems
    # We'll clear existing items and replace with the verified ones for simplicity & accuracy
    await db.execute(select(OrderItem).where(OrderItem.order_id == order_id)) # Warm up cache if needed
    
    # Logic: Delete existing order_items for this order and re-insert
    # A more advanced version would 'upsert', but replacing ensures the list is exactly what staff saw.
    from sqlalchemy import delete
    await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))

    for p_item in pickup_data.items:
        res = await db.execute(select(LaundryItem).where(LaundryItem.id == p_item.item_id))
        li = res.scalars().first()
        
        new_oi = OrderItem(
            order_id=order.id,
            item_id=p_item.item_id,
            final_quantity=p_item.final_quantity,
            unit_price=li.base_price if li else 0.0
        )
        db.add(new_oi)

    # 4. Update Order Header
    order.final_price = totals["final_total"]
    order.discount_applied = totals["discount_applied"]
    order.status = OrderStatus.PICKED_UP
    
    await db.commit()
    await db.refresh(order)
    return order


async def process_delivery(db: AsyncSession, order_id: int, delivery_data: DeliveryCreate) -> Order:
    # 1. Fetch Order
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Validation: Must be PICKED_UP to be DELIVERED
    if order.status != OrderStatus.PICKED_UP:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot deliver order in {order.status} status. Must be PICKED_UP first."
        )

    # 2. Create Transaction Record
    new_transaction = Transaction(
        order_id=order.id,
        received_amount=delivery_data.received_amount,
        payment_method=delivery_data.payment_method,
        delivery_date=delivery_data.delivery_date
    )
    db.add(new_transaction)

    # 3. Update Order Header
    order.status = OrderStatus.DELIVERED
    # Optional: Logic to handle partial payments could go here
    
    await db.commit()
    await db.refresh(order)
    return order