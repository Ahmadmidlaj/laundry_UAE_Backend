from app.services.order_service import admin_force_update_order
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import RoleChecker, get_current_user
from app.models.models import SystemConfig, User, Order, OrderItem, OrderStatus, LaundryItem, UserRole
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

# app/api/v1/endpoints/orders.py

@router.post("/", response_model=OrderResponse)
async def create_order(
    order_in: OrderCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. INITIAL CHECKS
    config_res = await db.execute(select(SystemConfig).limit(1))
    config = config_res.scalars().first()
    
    # 2. PRICING & WALLET
    pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
    totals = await calculate_order_price(db, pricing_data)
    
    final_price = totals["final_total"]
    discount_applied = totals["discount_applied"]
    conversion_rate = config.credit_conversion_rate if config else 1.0

    credits_requested = getattr(order_in, 'credits_to_use', 0.0)
    actual_credits_used = 0.0 # Track this explicitly for safety
    
    if credits_requested > 0:
        if credits_requested > current_user.wallet_balance:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance.")
        
        wallet_discount_aed = credits_requested * conversion_rate
        if wallet_discount_aed > final_price:
            wallet_discount_aed = final_price
            actual_credits_used = wallet_discount_aed / conversion_rate
        else:
            actual_credits_used = credits_requested
            
        current_user.wallet_balance -= actual_credits_used
        final_price -= wallet_discount_aed
        discount_applied += wallet_discount_aed

    # 3. CREATE ORDER HEADER
    new_order = Order(
        customer_id=current_user.id,
        status=OrderStatus.NEW_ORDER,
        pickup_date=order_in.pickup_date,
        pickup_time=order_in.pickup_time,
        notes=order_in.notes,
        estimated_price=final_price,
        discount_applied=discount_applied,
        credits_used=actual_credits_used # Save the tracked deduction
    )
    db.add(new_order)
    await db.flush() 
    created_order_id = new_order.id 

    # 4. ADD ITEMS
    for item_data in order_in.items:
        res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
        li = res.scalars().first()
        db.add(OrderItem(
            order_id=created_order_id, 
            item_id=item_data.item_id,
            estimated_quantity=item_data.estimated_quantity,
            unit_price=li.base_price if li else 0.0
        ))
    
    # 5. COMMIT EVERYTHING
    await db.commit()
    
    # 6. FETCH FINAL RESULT FOR RESPONSE
    result = await db.execute(
        select(Order)
        .where(Order.id == created_order_id)
        .options(
            selectinload(Order.customer), 
            selectinload(Order.items).joinedload(OrderItem.item)
        ) 
    )
    
    final_order = result.scalars().first()
    return final_order

# @router.post("/", response_model=OrderResponse)
# async def create_order(
#     order_in: OrderCreate, 
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. INITIAL CHECKS
#     config_res = await db.execute(select(SystemConfig).limit(1))
#     config = config_res.scalars().first()
    
#     # 2. PRICING & WALLET
#     pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
#     totals = await calculate_order_price(db, pricing_data)
    
#     final_price = totals["final_total"]
#     discount_applied = totals["discount_applied"]
#     conversion_rate = config.credit_conversion_rate if config else 1.0

#     credits_requested = getattr(order_in, 'credits_to_use', 0.0)
#     if credits_requested > 0:
#         if credits_requested > current_user.wallet_balance:
#             raise HTTPException(status_code=400, detail="Insufficient wallet balance.")
        
#         wallet_discount_aed = credits_requested * conversion_rate
#         if wallet_discount_aed > final_price:
#             wallet_discount_aed = final_price
#             actual_credits_used = wallet_discount_aed / conversion_rate
#         else:
#             actual_credits_used = credits_requested
            
#         current_user.wallet_balance -= actual_credits_used
#         final_price -= wallet_discount_aed
#         discount_applied += wallet_discount_aed

#     # 3. CREATE ORDER HEADER
#     # (Referral reward logic has been safely migrated to the delivery service)
#     new_order = Order(
#         customer_id=current_user.id,
#         status=OrderStatus.NEW_ORDER,
#         pickup_date=order_in.pickup_date,
#         pickup_time=order_in.pickup_time,
#         notes=order_in.notes,
#         estimated_price=final_price,
#         discount_applied=discount_applied
#     )
#     db.add(new_order)
    
#     # We FLUSH here to generate the ID in the database
#     await db.flush() 
    
#     # CRITICAL FIX: Save the ID in a local variable NOW
#     # This prevents the "MissingGreenlet" error after commit
#     created_order_id = new_order.id 

#     # 4. ADD ITEMS
#     for item_data in order_in.items:
#         res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
#         li = res.scalars().first()
#         db.add(OrderItem(
#             order_id=created_order_id, # Use our safe variable
#             item_id=item_data.item_id,
#             estimated_quantity=item_data.estimated_quantity,
#             unit_price=li.base_price if li else 0.0
#         ))
    
#     # 5. COMMIT EVERYTHING
#     await db.commit()
    
#     # 6. FETCH FINAL RESULT FOR RESPONSE
#     # Use the safe 'created_order_id' variable here instead of 'new_order.id'
#     result = await db.execute(
#         select(Order)
#         .where(Order.id == created_order_id)
#         .options(
#             selectinload(Order.customer), 
#             selectinload(Order.items).joinedload(OrderItem.item)
#         ) 
#     )
    
#     final_order = result.scalars().first()
#     return final_order

# # app/api/v1/endpoints/orders.py

# @router.post("/", response_model=OrderResponse)
# async def create_order(
#     order_in: OrderCreate, 
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. INITIAL CHECKS
#     config_res = await db.execute(select(SystemConfig).limit(1))
#     config = config_res.scalars().first()
    
#     past_orders_res = await db.execute(select(Order.id).where(Order.customer_id == current_user.id).limit(1))
#     is_first_order = past_orders_res.scalars().first() is None

#     # 2. PRICING & WALLET
#     pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
#     totals = await calculate_order_price(db, pricing_data)
    
#     final_price = totals["final_total"]
#     discount_applied = totals["discount_applied"]
#     conversion_rate = config.credit_conversion_rate if config else 1.0

#     credits_requested = getattr(order_in, 'credits_to_use', 0.0)
#     if credits_requested > 0:
#         if credits_requested > current_user.wallet_balance:
#             raise HTTPException(status_code=400, detail="Insufficient wallet balance.")
        
#         wallet_discount_aed = credits_requested * conversion_rate
#         if wallet_discount_aed > final_price:
#             wallet_discount_aed = final_price
#             actual_credits_used = wallet_discount_aed / conversion_rate
#         else:
#             actual_credits_used = credits_requested
            
#         current_user.wallet_balance -= actual_credits_used
#         final_price -= wallet_discount_aed
#         discount_applied += wallet_discount_aed

#     # 3. REFERRAL REWARD (Referrer gets points)
#     if is_first_order and current_user.referred_by_id and config and config.referral_system_enabled:
#         referrer_res = await db.execute(select(User).where(User.id == current_user.referred_by_id))
#         referrer = referrer_res.scalars().first()
#         if referrer:
#             referrer.wallet_balance += config.reward_credits_per_referral

#     # 4. CREATE ORDER HEADER
#     new_order = Order(
#         customer_id=current_user.id,
#         status=OrderStatus.NEW_ORDER,
#         pickup_date=order_in.pickup_date,
#         pickup_time=order_in.pickup_time,
#         notes=order_in.notes,
#         estimated_price=final_price,
#         discount_applied=discount_applied
#     )
#     db.add(new_order)
    
#     # We FLUSH here to generate the ID in the database
#     await db.flush() 
    
#     # CRITICAL FIX: Save the ID in a local variable NOW
#     # This prevents the "MissingGreenlet" error after commit
#     created_order_id = new_order.id 

#     # 5. ADD ITEMS
#     for item_data in order_in.items:
#         res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
#         li = res.scalars().first()
#         db.add(OrderItem(
#             order_id=created_order_id, # Use our safe variable
#             item_id=item_data.item_id,
#             estimated_quantity=item_data.estimated_quantity,
#             unit_price=li.base_price if li else 0.0
#         ))
    
#     # 6. COMMIT EVERYTHING
#     await db.commit()
    
#     # 7. FETCH FINAL RESULT FOR RESPONSE
#     # Use the safe 'created_order_id' variable here instead of 'new_order.id'
#     result = await db.execute(
#         select(Order)
#         .where(Order.id == created_order_id)
#         .options(
#             selectinload(Order.customer), 
#             selectinload(Order.items).joinedload(OrderItem.item)
#         ) 
#     )
    
#     final_order = result.scalars().first()
#     return final_order





# @router.post("/", response_model=OrderResponse)
# async def create_order(
#     order_in: OrderCreate, 
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. FETCH CONFIG & CHECK FOR FIRST ORDER STATUS IMMEDIATELY
#     config_res = await db.execute(select(SystemConfig).limit(1))
#     config = config_res.scalars().first()
    
#     # Check if this is truly the first order BEFORE we create the new one
#     past_orders_res = await db.execute(
#         select(Order.id).where(Order.customer_id == current_user.id).limit(1)
#     )
#     is_first_order = past_orders_res.scalars().first() is None

#     # 2. PRICING LOGIC
#     pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
#     totals = await calculate_order_price(db, pricing_data)
    
#     final_price = totals["final_total"]
#     discount_applied = totals["discount_applied"]
#     conversion_rate = config.credit_conversion_rate if config else 1.0

#     # 3. WALLET USAGE (Existing Logic)
#     credits_requested = getattr(order_in, 'credits_to_use', 0.0)
#     if credits_requested > 0:
#         if credits_requested > current_user.wallet_balance:
#             raise HTTPException(status_code=400, detail="Insufficient wallet balance.")
        
#         wallet_discount_aed = credits_requested * conversion_rate
#         if wallet_discount_aed > final_price:
#             wallet_discount_aed = final_price
#             actual_credits_used = wallet_discount_aed / conversion_rate
#         else:
#             actual_credits_used = credits_requested
            
#         current_user.wallet_balance -= actual_credits_used
#         final_price -= wallet_discount_aed
#         discount_applied += wallet_discount_aed

#     # 4. REFERRAL REWARD TRIGGER (Using the boolean we set at the start)
#     if is_first_order and current_user.referred_by_id and config and config.referral_system_enabled:
#         referrer_res = await db.execute(select(User).where(User.id == current_user.referred_by_id))
#         referrer = referrer_res.scalars().first()
#         if referrer:
#             # Reward the referrer
#             referrer.wallet_balance += config.reward_credits_per_referral

#     # 5. CREATE ORDER
#     new_order = Order(
#         customer_id=current_user.id,
#         status=OrderStatus.NEW_ORDER,
#         pickup_date=order_in.pickup_date,
#         pickup_time=order_in.pickup_time,
#         notes=order_in.notes,
#         estimated_price=final_price,
#         discount_applied=discount_applied
#     )
#     db.add(new_order)
#     await db.flush() 

#     # 6. ADD ITEMS
#     for item_data in order_in.items:
#         res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
#         li = res.scalars().first()
#         db.add(OrderItem(
#             order_id=new_order.id,
#             item_id=item_data.item_id,
#             estimated_quantity=item_data.estimated_quantity,
#             unit_price=li.base_price if li else 0.0
#         ))
    
#     await db.commit()
    
#     # Return fresh order with relations
#     result = await db.execute(
#         select(Order).where(Order.id == new_order.id)
#         .options(selectinload(Order.customer), selectinload(Order.items).joinedload(OrderItem.item)) 
#     )
#     return result.scalars().first()

# @router.post("/", response_model=OrderResponse)
# async def create_order(
#     order_in: OrderCreate, 
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. Fetch Global Settings (Fallback to defaults if Admin hasn't configured it yet)
#     config_res = await db.execute(select(SystemConfig).limit(1))
#     config = config_res.scalars().first()
#     conversion_rate = config.credit_conversion_rate if config else 1.0
#     referral_enabled = config.referral_system_enabled if config else False
#     reward_credits = config.reward_credits_per_referral if config else 50.0

#     # 2. Calculate Base Pricing
#     pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
#     totals = await calculate_order_price(db, pricing_data)
    
#     final_price = totals["final_total"]
#     discount_applied = totals["discount_applied"]

#     # 3. NEW: Wallet Deduction Engine
#     credits_requested = getattr(order_in, 'credits_to_use', 0.0)
#     if credits_requested > 0:
#         if credits_requested > current_user.wallet_balance:
#             raise HTTPException(status_code=400, detail="Insufficient wallet balance.")
            
#         wallet_discount_aed = credits_requested * conversion_rate
        
#         # Safeguard: Do not discount more than the order total!
#         if wallet_discount_aed > final_price:
#             wallet_discount_aed = final_price
#             actual_credits_used = wallet_discount_aed / conversion_rate
#         else:
#             actual_credits_used = credits_requested
            
#         # Apply the deductions
#         current_user.wallet_balance -= actual_credits_used
#         final_price -= wallet_discount_aed
#         discount_applied += wallet_discount_aed

#     # 4. NEW: Referral Reward Trigger (Strictly checked against past orders)
#     if current_user.referred_by_id and referral_enabled:
#         past_orders = await db.execute(select(Order.id).where(Order.customer_id == current_user.id).limit(1))
#         # If this returns nothing, it is definitively their FIRST order
#         if not past_orders.scalars().first():
#             referrer_res = await db.execute(select(User).where(User.id == current_user.referred_by_id))
#             referrer = referrer_res.scalars().first()
#             if referrer:
#                 referrer.wallet_balance += reward_credits

#     # 5. Create the Order header
#     new_order = Order(
#         customer_id=current_user.id,
#         status=OrderStatus.NEW_ORDER,
#         pickup_date=order_in.pickup_date,
#         pickup_time=order_in.pickup_time,
#         notes=order_in.notes,
#         estimated_price=final_price,
#         discount_applied=discount_applied
#     )
#     db.add(new_order)
#     await db.flush() 

#     order_id = new_order.id

#     # 6. Add the items to the order
#     for item_data in order_in.items:
#         res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
#         li = res.scalars().first()
        
#         oi = OrderItem(
#             order_id=order_id,
#             item_id=item_data.item_id,
#             estimated_quantity=item_data.estimated_quantity,
#             unit_price=li.base_price if li else 0.0
#         )
#         db.add(oi)
    
#     # Commit changes (Order creation, User wallet deduction, Referrer wallet reward)
#     await db.commit()
    
#     result = await db.execute(
#         select(Order)
#         .where(Order.id == order_id)
#         .options(selectinload(Order.customer), 
#             selectinload(Order.items).joinedload(OrderItem.item)) 
#     )
#     return result.scalars().first()


# //deprecated
# @router.post("/", response_model=OrderResponse)
# async def create_order(
#     order_in: OrderCreate, 
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # 1. Calculate pricing
#     pricing_data = [{"item_id": i.item_id, "quantity": i.estimated_quantity} for i in order_in.items]
#     totals = await calculate_order_price(db, pricing_data)
    
#     # 2. Create the Order header
#     new_order = Order(
#         customer_id=current_user.id,
#         status=OrderStatus.NEW_ORDER,
#         pickup_date=order_in.pickup_date,
#         pickup_time=order_in.pickup_time,
#         notes=order_in.notes,
#         estimated_price=totals["final_total"],
#         discount_applied=totals["discount_applied"]
#     )
#     db.add(new_order)
#     await db.flush() # Get the order ID without committing yet


#     order_id = new_order.id

#     # 3. Add the items to the order
#     for item_data in order_in.items:
#         # Fetch current unit price to "lock it in"
#         res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
#         li = res.scalars().first()
        
#         oi = OrderItem(
#             order_id=order_id,
#             item_id=item_data.item_id,
#             estimated_quantity=item_data.estimated_quantity,
#             unit_price=li.base_price if li else 0.0
#         )
#         db.add(oi)
    

#     await db.commit()
#     result = await db.execute(
#         select(Order)
#         .where(Order.id == order_id)
#         .options(selectinload(Order.customer), 
#             # THE FIX: Added joinedload here so the newly created order returns names
#             selectinload(Order.items).joinedload(OrderItem.item)) 
#     )
#     final_order = result.scalars().first()
#     # await db.refresh(new_order)
#     # return new_order
#     return final_order





@router.patch("/{order_id}/admin", response_model=OrderResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_order_admin(
    order_id: int,
    update_data: AdminOrderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """ADMIN ONLY: Force update any order detail (quantities, status, dates)."""
    return await admin_force_update_order(db, order_id, update_data)