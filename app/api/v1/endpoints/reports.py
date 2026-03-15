from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.future import select
from app.db.session import get_db
from app.api.deps import RoleChecker, get_current_user
from app.models.models import User, Order, OrderStatus, UserRole, Offer, Transaction
from typing import List  
from app.schemas.reports import AdminDashboard, CustomerStats 
from sqlalchemy.ext.asyncio import AsyncSession 
router = APIRouter()

@router.get("/admin/dashboard", 
    response_model=AdminDashboard,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def get_admin_dashboard(db: AsyncSession = Depends(get_db)):
    # Total Customers
    cust_count = await db.execute(select(func.count(User.id)).where(User.role == UserRole.CUSTOMER))
    
    # Order counts by status
    new_o = await db.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.NEW_ORDER))
    picked_o = await db.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.PICKED_UP))
    delivered_o = await db.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED))
    
    # Total Revenue (Sum of all received amounts in Transactions)
    revenue = await db.execute(select(func.sum(Transaction.received_amount)))
    
    # Active Offers
    offers = await db.execute(select(func.count(Offer.id)).where(Offer.is_active == True))

    return {
        "total_customers": cust_count.scalar() or 0,
        "new_orders": new_o.scalar() or 0,
        "picked_up_orders": picked_o.scalar() or 0,
        "delivered_orders": delivered_o.scalar() or 0,
        "total_revenue": revenue.scalar() or 0.0,
        "active_offers": offers.scalar() or 0
    }

@router.get("/customer/my-stats", response_model=CustomerStats)
async def get_customer_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Total Orders
    total_o = await db.execute(select(func.count(Order.id)).where(Order.customer_id == current_user.id))
    
    # Total Discounts Received
    discounts = await db.execute(select(func.sum(Order.discount_applied)).where(Order.customer_id == current_user.id))
    
    # Monthly Spending (Last 30 days)
    import datetime
    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    spending = await db.execute(
        select(func.sum(Transaction.received_amount))
        .join(Order)
        .where(Order.customer_id == current_user.id, Transaction.delivery_date >= thirty_days_ago)
    )

    return {
        "total_orders": total_o.scalar() or 0,
        "monthly_spending": spending.scalar() or 0.0,
        "total_discounts": discounts.scalar() or 0.0
    }