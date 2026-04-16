# app/api/v1/endpoints/orders.py

from app.services.order_service import admin_force_update_order
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.db.session import get_db
from app.api.deps import RoleChecker, get_current_user
from app.models.models import ItemServicePrice, SystemConfig, User, Order, OrderItem, OrderStatus, LaundryItem, UserRole
from app.schemas.order import AdminOrderUpdate, CustomerOrderUpdate, OrderCreate, OrderResponse
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
            selectinload(Order.items).joinedload(OrderItem.item),           
            selectinload(Order.items).joinedload(OrderItem.service_category)  
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
        .options(
            selectinload(Order.customer), 
            selectinload(Order.items).joinedload(OrderItem.item),              # <-- KEEP THIS
            selectinload(Order.items).joinedload(OrderItem.service_category)   # <-- ADD THIS
        )  # <--- THIS IS THE FIX
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
            selectinload(Order.customer),
            selectinload(Order.items).joinedload(OrderItem.item),              # <-- KEEP THIS
            selectinload(Order.items).joinedload(OrderItem.service_category)   # <-- ADD THIS
        )
    )
           
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    return order


@router.patch("/{order_id}/customer", response_model=OrderResponse)
async def update_my_order(
    order_id: int,
    update_data: CustomerOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Customer-facing endpoint to safely update items, notes, reschedule, or cancel."""
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == current_user.id)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items).joinedload(OrderItem.item),
            selectinload(Order.items).joinedload(OrderItem.service_category)
        )
    )
    order = result.scalars().first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")

    # RULE 1: If DELIVERED, ONLY update notes
    if order.status == OrderStatus.DELIVERED:
        if update_data.notes is not None:
            order.notes = update_data.notes
            await db.commit()
            await db.refresh(order)
        return order

    # RULE 2: If NEW_ORDER, handle full edits
    if order.status == OrderStatus.NEW_ORDER:
        
        # A. Handle Cancellation
        if update_data.status == OrderStatus.CANCELLED:
            order.status = OrderStatus.CANCELLED
            if order.credits_used and order.credits_used > 0:
                current_user.wallet_balance += order.credits_used # Refund!
            await db.commit()
            await db.refresh(order)
            return order

        # B. Handle Item modifications (The Mini-Cart Update)
        if update_data.items is not None:
            # 1. Refund existing credits before doing any math
            if order.credits_used and order.credits_used > 0:
                current_user.wallet_balance += order.credits_used
                order.credits_used = 0.0

            # 2. Setup pricing config
            config_res = await db.execute(select(SystemConfig).limit(1))
            config = config_res.scalars().first()
            conversion_rate = config.credit_conversion_rate if config else 1.0

            # 3. Calculate new totals
            pricing_data = [{"item_id": i.item_id, "service_category_id": i.service_category_id, "quantity": i.estimated_quantity} for i in update_data.items]
            totals = await calculate_order_price(db, pricing_data)
            final_price = totals["final_total"]
            discount_applied = totals["discount_applied"]

            # 4. Process NEW wallet requests
            req_credits = update_data.credits_to_use or 0.0
            actual_credits_used = 0.0
            
            if req_credits > 0:
                if req_credits > current_user.wallet_balance:
                    raise HTTPException(status_code=400, detail="Insufficient wallet balance.")
                
                wallet_discount_aed = req_credits * conversion_rate
                if wallet_discount_aed > final_price:
                    wallet_discount_aed = final_price
                    actual_credits_used = wallet_discount_aed / conversion_rate
                else:
                    actual_credits_used = req_credits
                    
                current_user.wallet_balance -= actual_credits_used
                final_price -= wallet_discount_aed
                discount_applied += wallet_discount_aed

            # 5. Delete old items & Insert new ones strictly from Matrix
            await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
            
            for item_data in update_data.items:
                res = await db.execute(select(ItemServicePrice).where(
                    ItemServicePrice.item_id == item_data.item_id,
                    ItemServicePrice.service_category_id == item_data.service_category_id
                ))
                sp = res.scalars().first()
                if not sp: raise HTTPException(status_code=400, detail="Invalid service configuration.")

                db.add(OrderItem(
                    order_id=order.id,
                    item_id=item_data.item_id,
                    service_category_id=item_data.service_category_id,
                    estimated_quantity=item_data.estimated_quantity,
                    unit_price=sp.price 
                ))

            # 6. Update Header with new math
            order.estimated_price = final_price
            order.discount_applied = discount_applied
            order.credits_used = actual_credits_used

        # C. Handle Dates & Notes
        if update_data.pickup_date: order.pickup_date = update_data.pickup_date
        if update_data.pickup_time: order.pickup_time = update_data.pickup_time
        if update_data.notes is not None: order.notes = update_data.notes

        await db.commit()
        
        # 7. Return fully refreshed object
        final_res = await db.execute(
            select(Order).where(Order.id == order_id)
            .options(
                selectinload(Order.customer),
                selectinload(Order.items).joinedload(OrderItem.item),
                selectinload(Order.items).joinedload(OrderItem.service_category)
            )
        )
        return final_res.scalars().first()

    raise HTTPException(status_code=400, detail=f"Order cannot be modified while in {order.status} status.")

# @router.patch("/{order_id}/customer", response_model=OrderResponse)
# async def update_my_order(
#     order_id: int,
#     update_data: CustomerOrderUpdate,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Customer-facing endpoint to safely update notes, reschedule, or cancel."""
#     result = await db.execute(
#         select(Order)
#         .where(Order.id == order_id, Order.customer_id == current_user.id)
#         .options(
#             selectinload(Order.customer),
#             selectinload(Order.items).joinedload(OrderItem.item),
#             selectinload(Order.items).joinedload(OrderItem.service_category)
#         )
#     )
#     order = result.scalars().first()
    
#     if not order:
#         raise HTTPException(status_code=404, detail="Order not found")

#     # RULE 1: If DELIVERED, they can ONLY update notes/remarks
#     if order.status == OrderStatus.DELIVERED:
#         if update_data.notes is not None:
#             order.notes = update_data.notes
#             await db.commit()
#             await db.refresh(order)
#         return order

#     # RULE 2: If NEW_ORDER, allow cancellation & rescheduling
#     if order.status == OrderStatus.NEW_ORDER:
#         # Handle Cancellation
#         if update_data.status == OrderStatus.CANCELLED:
#             order.status = OrderStatus.CANCELLED
            
#             # CRITICAL: Refund wallet credits if they used any!
#             if order.credits_used and order.credits_used > 0:
#                 current_user.wallet_balance += order.credits_used
                
#             await db.commit()
#             await db.refresh(order)
#             return order

#         # Handle Reschedule / Notes Update
#         if update_data.pickup_date:
#             order.pickup_date = update_data.pickup_date
#         if update_data.pickup_time:
#             order.pickup_time = update_data.pickup_time
#         if update_data.notes is not None:
#             order.notes = update_data.notes

#         await db.commit()
#         await db.refresh(order)
#         return order

#     # Fallback safety
#     raise HTTPException(status_code=400, detail=f"Order cannot be modified while in {order.status} status.")

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
    pricing_data = [{
            "item_id": i.item_id, 
            "service_category_id": i.service_category_id, # <-- WE FORGOT THIS!
            "quantity": i.estimated_quantity
        }for i in order_in.items]
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
        credits_used=actual_credits_used, # Save the tracked deduction
        hanger_needed=order_in.hanger_needed
    )
    db.add(new_order)
    await db.flush() 
    created_order_id = new_order.id 

    # 4. ADD ITEMS
    for item_data in order_in.items:
        res = await db.execute(select(ItemServicePrice).where(
            ItemServicePrice.item_id == item_data.item_id,
            ItemServicePrice.service_category_id == item_data.service_category_id
        ))
        sp = res.scalars().first()
        if not sp:
            raise HTTPException(status_code=400, detail="Invalid service configuration for item")

        db.add(OrderItem(
            order_id=created_order_id,
            item_id=item_data.item_id,
            service_category_id=item_data.service_category_id,
            estimated_quantity=item_data.estimated_quantity,
            unit_price=sp.price # strictly from matrix
        ))
    # 4. ADD ITEMS
    # for item_data in order_in.items:
    #     res = await db.execute(select(LaundryItem).where(LaundryItem.id == item_data.item_id))
    #     li = res.scalars().first()
    #     db.add(OrderItem(
    #         order_id=created_order_id, 
    #         item_id=item_data.item_id,
    #         estimated_quantity=item_data.estimated_quantity,
    #         unit_price=li.base_price if li else 0.0
    #     ))
    
    # 5. COMMIT EVERYTHING
    await db.commit()
    
    # 6. FETCH FINAL RESULT FOR RESPONSE
    result = await db.execute(
        select(Order)
        .where(Order.id == created_order_id)
        .options(
            selectinload(Order.customer), 
            selectinload(Order.items).joinedload(OrderItem.item),              # <-- KEEP THIS
            selectinload(Order.items).joinedload(OrderItem.service_category)   # <-- ADD THIS
        )
    )
    
    final_order = result.scalars().first()
    return final_order

@router.patch("/{order_id}/admin", response_model=OrderResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_order_admin(
    order_id: int,
    update_data: AdminOrderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """ADMIN ONLY: Force update any order detail (quantities, status, dates)."""
    return await admin_force_update_order(db, order_id, update_data)