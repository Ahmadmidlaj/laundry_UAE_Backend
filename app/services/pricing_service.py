from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models.models import Offer, LaundryItem
from typing import List, Dict

async def calculate_order_price(db: AsyncSession, items_input: List[Dict]) -> Dict:
    """
    Calculates estimated price and applies the best applicable discount.
    items_input format: [{"item_id": 1, "quantity": 5}, ...]
    """
    subtotal = 0.0
    
    # 1. Calculate Subtotal
    for entry in items_input:
        result = await db.execute(select(LaundryItem).where(LaundryItem.id == entry["item_id"]))
        item = result.scalars().first()
        if item:
            subtotal += item.base_price * entry["quantity"]

    # 2. Find Applicable Offers
    now = datetime.now(timezone.utc)
    offer_query = await db.execute(
        select(Offer).where(
            Offer.is_active == True,
            Offer.min_order_amount <= subtotal,
            Offer.start_date <= now,
            Offer.end_date >= now
        )
    )
    offers = offer_query.scalars().all()
    
    # Apply the highest discount available
    discount = 0.0
    if offers:
        discount = max(o.discount_amount for o in offers)

    return {
        "subtotal": subtotal,
        "discount_applied": discount,
        "final_total": max(0, subtotal - discount)
    }