
# app/services/order_service.py
from app.schemas.order import AdminOrderUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete
from fastapi import HTTPException

# ADDED: SystemConfig and User for the referral logic
from app.models.models import Order, OrderItem, OrderStatus, LaundryItem, Transaction, SystemConfig, User
from app.services.pricing_service import calculate_order_price
from app.schemas.pickup import PickupCreate
from app.schemas.delivery import DeliveryCreate


async def _get_order_with_relations(db: AsyncSession, order_id: int) -> Order:
    """
    Helper to fetch an order with items and customer pre-loaded.
    This prevents 'MissingGreenlet' errors during Pydantic serialization.
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
           selectinload(Order.customer),selectinload(Order.items).joinedload(OrderItem.item)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def _handle_first_delivery_referral(db: AsyncSession, customer_id: int, current_order_id: int):
    """
    Private helper: Checks if this is the customer's first completed delivery.
    If yes, and they were referred, credits the referrer.
    """
    # 1. Verify customer and referral linkage
    customer_res = await db.execute(select(User).where(User.id == customer_id))
    customer = customer_res.scalars().first()
    if not customer or not customer.referred_by_id:
        return

    # 2. Check if referral system is active
    config_res = await db.execute(select(SystemConfig).limit(1))
    config = config_res.scalars().first()
    if not config or not config.referral_system_enabled:
        return

    # 3. Check if this is truly the first delivered order
    past_delivered_res = await db.execute(
        select(Order.id)
        .where(Order.customer_id == customer_id)
        .where(Order.status == OrderStatus.DELIVERED)
        .where(Order.id != current_order_id)
        .limit(1)
    )
    
    # If they already have a past delivered order, reward was already issued
    if past_delivered_res.scalars().first() is not None:
        return

    # 4. Credit the referrer
    referrer_res = await db.execute(select(User).where(User.id == customer.referred_by_id))
    referrer = referrer_res.scalars().first()
    if referrer:
        referrer.wallet_balance += config.reward_credits_per_referral


async def process_pickup(db: AsyncSession, order_id: int, pickup_data: PickupCreate) -> Order:
    # 1. Fetch Order (Initial check)
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    
    if not order or order.status != OrderStatus.NEW_ORDER:
        raise HTTPException(status_code=400, detail="Order not found or already picked up")

    # 2. Recalculate Final Price using actual quantities verified by staff
    pricing_input = [{"item_id": i.item_id, "quantity": i.final_quantity} for i in pickup_data.items]
    totals = await calculate_order_price(db, pricing_input)

    # 3. Update OrderItems (Delete & Re-insert for accuracy)
    await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))

    for p_item in pickup_data.items:
        res = await db.execute(select(LaundryItem).where(LaundryItem.id == p_item.item_id))
        li = res.scalars().first()
        
        new_oi = OrderItem(
            order_id=order.id,
            item_id=p_item.item_id,
            final_quantity=p_item.final_quantity,
            # Fallback to 0 if item not found, though in production you'd want a check
            unit_price=li.base_price if li else 0.0 
        )
        db.add(new_oi)

    # 4. Update Order Header
    order.final_price = totals["final_total"]
    order.discount_applied = totals["discount_applied"]
    order.status = OrderStatus.PICKED_UP

    order.expected_delivery_date = pickup_data.expected_delivery_date
    order.expected_delivery_time = pickup_data.expected_delivery_time
    
    await db.commit()
    
    # 5. RETURN with relations loaded
    return await _get_order_with_relations(db, order_id)


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
    
    # 4. Trigger referral evaluation hook before committing
    await _handle_first_delivery_referral(db, order.customer_id, order.id)
    
    await db.commit()
    
    # 5. RETURN with relations loaded
    return await _get_order_with_relations(db, order_id)




# app/services/order_service.py

async def admin_force_update_order(db: AsyncSession, order_id: int, update_data: AdminOrderUpdate) -> Order:
    order = await _get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    data = update_data.model_dump(exclude_unset=True)
    
    # Determine intent: Are we cancelling an order right now?
    status_changing_to_cancelled = (
        "status" in data and 
        data["status"] == OrderStatus.CANCELLED and 
        order.status != OrderStatus.CANCELLED
    )
    
    # Determine intent: Are we delivering an order right now?
    status_changed_to_delivered = (
        "status" in data and 
        data["status"] == OrderStatus.DELIVERED and 
        order.status != OrderStatus.DELIVERED
    )

    # Logic: Handle Item Overrides & Price Recalculation
    if "items" in data:
        new_items = data.pop("items")
        # 1. Clear existing items
        await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
        
        # 2. Recalculate totals using pricing service
        pricing_input = [{"item_id": i["item_id"], "quantity": i["final_quantity"]} for i in new_items]
        totals = await calculate_order_price(db, pricing_input)
        
        # 3. Re-insert items with current unit prices
        for i in new_items:
            res = await db.execute(select(LaundryItem).where(LaundryItem.id == i["item_id"]))
            li = res.scalars().first()
            db.add(OrderItem(
                order_id=order_id,
                item_id=i["item_id"],
                final_quantity=i["final_quantity"],
                unit_price=li.base_price if li else 0.0
            ))
            
        order.estimated_price = totals["final_total"] 
        order.discount_applied = totals["discount_applied"]

    # Update Header Fields (Status, Dates, etc.)
    for key, value in data.items():
        setattr(order, key, value)

  # --- THE HOOKS ---
    
    # Hook 1: Referral Check
    if status_changed_to_delivered:
        await _handle_first_delivery_referral(db, order.customer_id, order.id)
        
    # Hook 2: Cancellation & Refund Processing
    if status_changing_to_cancelled:
        # A. Safely extract credits (Fallback to 0.0 if the database row has NULL)
        credits_to_refund = order.credits_used if order.credits_used is not None else 0.0
        
        if credits_to_refund > 0:
            user_res = await db.execute(select(User).where(User.id == order.customer_id))
            customer = user_res.scalars().first()
            if customer:
                customer.wallet_balance += credits_to_refund
            
            # Reset credits_used to 0 so an admin cannot accidentally refund them twice 
            # by toggling the status back and forth
            order.credits_used = 0.0 
            
        # B. Zero out financial data so Reports & CSVs remain strictly accurate
        order.estimated_price = 0.0
        order.final_price = 0.0

    await db.commit()
    return await _get_order_with_relations(db, order_id)




# async def admin_force_update_order(db: AsyncSession, order_id: int, update_data: AdminOrderUpdate) -> Order:
#     order = await _get_order_with_relations(db, order_id)
#     if not order:
#         raise HTTPException(status_code=404, detail="Order not found")

#     data = update_data.model_dump(exclude_unset=True)
    
#     # Logic: Handle Item Overrides & Price Recalculation
#     if "items" in data:
#         new_items = data.pop("items")
#         # 1. Clear existing items
#         await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
        
#         # 2. Recalculate totals using pricing service
#         pricing_input = [{"item_id": i["item_id"], "quantity": i["final_quantity"]} for i in new_items]
#         totals = await calculate_order_price(db, pricing_input)
        
#         # 3. Re-insert items with current unit prices
#         for i in new_items:
#             res = await db.execute(select(LaundryItem).where(LaundryItem.id == i["item_id"]))
#             li = res.scalars().first()
#             db.add(OrderItem(
#                 order_id=order_id,
#                 item_id=i["item_id"],
#                 final_quantity=i["final_quantity"],
#                 unit_price=li.base_price if li else 0.0
#             ))
            
#         order.estimated_price = totals["final_total"] # Admin update sets the new 'estimate'
#         order.discount_applied = totals["discount_applied"]

#     # Evaluate if this admin override is marking the order as newly delivered
#     status_changed_to_delivered = False
#     if "status" in data and data["status"] == OrderStatus.DELIVERED and order.status != OrderStatus.DELIVERED:
#         status_changed_to_delivered = True

#     # Update Header Fields (Status, Dates, etc.)
#     for key, value in data.items():
#         setattr(order, key, value)

#     # Trigger referral evaluation hook if applicable
#     if status_changed_to_delivered:
#         await _handle_first_delivery_referral(db, order.customer_id, order.id)

#     await db.commit()
#     return await _get_order_with_relations(db, order_id)


# from app.schemas.order import AdminOrderUpdate
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from sqlalchemy.orm import selectinload
# from sqlalchemy import delete
# from fastapi import HTTPException

# from app.models.models import Order, OrderItem, OrderStatus, LaundryItem, Transaction
# from app.services.pricing_service import calculate_order_price
# from app.schemas.pickup import PickupCreate
# from app.schemas.delivery import DeliveryCreate

# async def _get_order_with_relations(db: AsyncSession, order_id: int) -> Order:
#     """
#     Helper to fetch an order with items and customer pre-loaded.
#     This prevents 'MissingGreenlet' errors during Pydantic serialization.
#     """
#     stmt = (
#         select(Order)
#         .where(Order.id == order_id)
#         .options(
#            selectinload(Order.customer),selectinload(Order.items).joinedload(OrderItem.item)
           
#         )
#     )
#     result = await db.execute(stmt)
#     return result.scalars().first()

# async def process_pickup(db: AsyncSession, order_id: int, pickup_data: PickupCreate) -> Order:
#     # 1. Fetch Order (Initial check)
#     result = await db.execute(select(Order).where(Order.id == order_id))
#     order = result.scalars().first()
    
#     if not order or order.status != OrderStatus.NEW_ORDER:
#         raise HTTPException(status_code=400, detail="Order not found or already picked up")

#     # 2. Recalculate Final Price using actual quantities verified by staff
#     pricing_input = [{"item_id": i.item_id, "quantity": i.final_quantity} for i in pickup_data.items]
#     totals = await calculate_order_price(db, pricing_input)

#     # 3. Update OrderItems (Delete & Re-insert for accuracy)
#     await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))

#     for p_item in pickup_data.items:
#         res = await db.execute(select(LaundryItem).where(LaundryItem.id == p_item.item_id))
#         li = res.scalars().first()
        
#         new_oi = OrderItem(
#             order_id=order.id,
#             item_id=p_item.item_id,
#             final_quantity=p_item.final_quantity,
#             # Fallback to 0 if item not found, though in production you'd want a check
#             unit_price=li.base_price if li else 0.0 
#         )
#         db.add(new_oi)

#     # 4. Update Order Header
#     order.final_price = totals["final_total"]
#     order.discount_applied = totals["discount_applied"]
#     order.status = OrderStatus.PICKED_UP

#     order.expected_delivery_date = pickup_data.expected_delivery_date
#     order.expected_delivery_time = pickup_data.expected_delivery_time
    
#     await db.commit()
    
#     # 5. RETURN with relations loaded (The Fix)
#     return await _get_order_with_relations(db, order_id)


# async def process_delivery(db: AsyncSession, order_id: int, delivery_data: DeliveryCreate) -> Order:
#     # 1. Fetch Order
#     result = await db.execute(select(Order).where(Order.id == order_id))
#     order = result.scalars().first()
    
#     if not order:
#         raise HTTPException(status_code=404, detail="Order not found")
    
#     # Validation: Must be PICKED_UP to be DELIVERED
#     if order.status != OrderStatus.PICKED_UP:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"Cannot deliver order in {order.status} status. Must be PICKED_UP first."
#         )

#     # 2. Create Transaction Record
#     new_transaction = Transaction(
#         order_id=order.id,
#         received_amount=delivery_data.received_amount,
#         payment_method=delivery_data.payment_method,
#         delivery_date=delivery_data.delivery_date
#     )
#     db.add(new_transaction)

#     # 3. Update Order Header
#     order.status = OrderStatus.DELIVERED
    
#     await db.commit()
    
#     # 4. RETURN with relations loaded (The Fix)
#     return await _get_order_with_relations(db, order_id)



# async def admin_force_update_order(db: AsyncSession, order_id: int, update_data: AdminOrderUpdate) -> Order:
#     order = await _get_order_with_relations(db, order_id)
#     if not order:
#         raise HTTPException(status_code=404, detail="Order not found")

#     data = update_data.model_dump(exclude_unset=True)
    
#     # Logic: Handle Item Overrides & Price Recalculation
#     if "items" in data:
#         new_items = data.pop("items")
#         # 1. Clear existing items
#         await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
        
#         # 2. Recalculate totals using pricing service
#         pricing_input = [{"item_id": i["item_id"], "quantity": i["final_quantity"]} for i in new_items]
#         totals = await calculate_order_price(db, pricing_input)
        
#         # 3. Re-insert items with current unit prices
#         for i in new_items:
#             res = await db.execute(select(LaundryItem).where(LaundryItem.id == i["item_id"]))
#             li = res.scalars().first()
#             db.add(OrderItem(
#                 order_id=order_id,
#                 item_id=i["item_id"],
#                 final_quantity=i["final_quantity"],
#                 unit_price=li.base_price if li else 0.0
#             ))
            
#         order.estimated_price = totals["final_total"] # Admin update sets the new 'estimate'
#         order.discount_applied = totals["discount_applied"]

#     # Update Header Fields (Status, Dates, etc.)
#     for key, value in data.items():
#         setattr(order, key, value)

#     await db.commit()
#     return await _get_order_with_relations(db, order_id)


