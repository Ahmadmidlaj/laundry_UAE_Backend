from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models.models import Offer, LaundryItem, ItemServicePrice
from typing import List, Dict
from fastapi import HTTPException


async def calculate_order_price(db: AsyncSession, items_input: List[Dict]) -> Dict:
    """
    items_input format: [{"item_id": 1, "service_category_id": 2, "quantity": 5, "unit_price": 15.0}, ...]
    """
    subtotal = 0.0

    # 1. Calculate Subtotal using the 2D Matrix OR the custom unit_price override
    for entry in items_input:
        cat_id = entry.get("service_category_id")
        custom_price = entry.get("unit_price") # <-- NEW: Extract override if it exists
        
        if not cat_id:
            raise HTTPException(status_code=400, detail=f"Missing service category for item")

        # --- THE MAGIC LOGIC: Use custom price if provided, else query DB ---
        if custom_price is not None:
            subtotal += custom_price * entry["quantity"]
        else:
            stmt = select(ItemServicePrice).where(
                ItemServicePrice.item_id == entry["item_id"],
                ItemServicePrice.service_category_id == cat_id
            )
            res = await db.execute(stmt)
            service_price = res.scalars().first()
            
            if not service_price:
                raise HTTPException(status_code=400, detail="Pricing matrix not found for selected item and service")
                
            subtotal += service_price.price * entry["quantity"]

    # 2. Find Applicable Offers
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    offer_query = await db.execute(
        select(Offer).where(
            Offer.is_active == True,
            Offer.min_order_amount <= subtotal,
            Offer.start_date <= now,
            Offer.end_date >= now
        )
    )
    offers = offer_query.scalars().all()

    discount = 0.0
    if offers:
        calculated_discounts = []
        for o in offers:
            if getattr(o, "discount_type", "FIXED") == "PERCENTAGE":
                calculated_discounts.append(subtotal * (o.discount_amount / 100.0))
            else:
                calculated_discounts.append(o.discount_amount)
        
        discount = max(calculated_discounts) if calculated_discounts else 0.0

    return {
        "subtotal": subtotal,
        "discount_applied": discount,
        "final_total": max(0, subtotal - discount)
    }

