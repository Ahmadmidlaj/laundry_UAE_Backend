# app/api/v1/endpoints/reports.py
from fastapi import APIRouter, Depends, Query
import datetime
from sqlalchemy import func
from sqlalchemy.future import select
from app.db.session import get_db
from app.api.deps import RoleChecker, get_current_user
from app.models.models import LaundryItem, OrderItem, User, Order, OrderStatus, UserRole, Offer, Transaction, Expense
from typing import List  ,Optional
from app.schemas.reports import AdminDashboard, CustomerStats 
from sqlalchemy.ext.asyncio import AsyncSession 

router = APIRouter()

@router.get("/admin/dashboard", 
    response_model=AdminDashboard,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def get_admin_dashboard(
    days: Optional[int] = Query(None, description="Filter stats by the last X days"),
    db: AsyncSession = Depends(get_db)
):
    # 1. Base Statements
    cust_stmt = select(func.count(User.id)).where(User.role == UserRole.CUSTOMER)
    new_o_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.NEW_ORDER)
    picked_o_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.PICKED_UP)
    del_o_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
    rev_stmt = select(func.sum(Transaction.received_amount))
    exp_stmt = select(func.sum(Expense.amount))
    off_stmt = select(func.count(Offer.id)).where(Offer.is_active == True)

    # 2. Apply Dynamic Date Filters if 'days' is provided
    if days:
        now = datetime.datetime.now()
        
        if days == 1:
            # STRICTLY TODAY: Force cutoff to 12:00 AM (Midnight) today
            cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # HISTORICAL ROLLING WINDOW: Exactly 7, 30, or 365 days ago
            cutoff_date = now - datetime.timedelta(days=days)
            
        new_o_stmt = new_o_stmt.where(Order.created_at >= cutoff_date)
        picked_o_stmt = picked_o_stmt.where(Order.created_at >= cutoff_date)
        del_o_stmt = del_o_stmt.where(Order.created_at >= cutoff_date)
        rev_stmt = rev_stmt.where(Transaction.delivery_date >= cutoff_date)
        exp_stmt = exp_stmt.where(Expense.expense_date >= cutoff_date)
        # Note: Total Customers and Offers generally remain all-time metrics

    # 3. Execute Queries
    cust_count = await db.execute(cust_stmt)
    new_o = await db.execute(new_o_stmt)
    picked_o = await db.execute(picked_o_stmt)
    delivered_o = await db.execute(del_o_stmt)
    
    # FINANCIAL ENGINE
    revenue_res = await db.execute(rev_stmt)
    revenue = revenue_res.scalar() or 0.0
    
    expense_res = await db.execute(exp_stmt)
    total_expenses = expense_res.scalar() or 0.0
    
    net_profit = revenue - total_expenses
    
    offers = await db.execute(off_stmt)

    return {
        "total_customers": cust_count.scalar() or 0,
        "new_orders": new_o.scalar() or 0,
        "picked_up_orders": picked_o.scalar() or 0,
        "delivered_orders": delivered_o.scalar() or 0,
        "total_revenue": revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "active_offers": offers.scalar() or 0
    }
# @router.get("/admin/dashboard", 
#     response_model=AdminDashboard,
#     dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
# )
# async def get_admin_dashboard(
#     days: Optional[int] = Query(None, description="Filter stats by the last X days"),
#     db: AsyncSession = Depends(get_db)
# ):
#     # 1. Base Statements
#     cust_stmt = select(func.count(User.id)).where(User.role == UserRole.CUSTOMER)
#     new_o_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.NEW_ORDER)
#     picked_o_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.PICKED_UP)
#     del_o_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
#     rev_stmt = select(func.sum(Transaction.received_amount))
#     exp_stmt = select(func.sum(Expense.amount))
#     off_stmt = select(func.count(Offer.id)).where(Offer.is_active == True)

#     # 2. Apply Dynamic Date Filters if 'days' is provided
#     if days:
#         cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
#         new_o_stmt = new_o_stmt.where(Order.created_at >= cutoff_date)
#         picked_o_stmt = picked_o_stmt.where(Order.created_at >= cutoff_date)
#         del_o_stmt = del_o_stmt.where(Order.created_at >= cutoff_date)
#         rev_stmt = rev_stmt.where(Transaction.delivery_date >= cutoff_date)
#         exp_stmt = exp_stmt.where(Expense.expense_date >= cutoff_date)
#         # Note: Total Customers and Offers generally remain all-time metrics, 
#         # but you can filter them here too if you add `created_at` to those tables.

#     # 3. Execute Queries
#     cust_count = await db.execute(cust_stmt)
#     new_o = await db.execute(new_o_stmt)
#     picked_o = await db.execute(picked_o_stmt)
#     delivered_o = await db.execute(del_o_stmt)
    
#     # FINANCIAL ENGINE
#     revenue_res = await db.execute(rev_stmt)
#     revenue = revenue_res.scalar() or 0.0
    
#     expense_res = await db.execute(exp_stmt)
#     total_expenses = expense_res.scalar() or 0.0
    
#     net_profit = revenue - total_expenses
    
#     offers = await db.execute(off_stmt)

#     return {
#         "total_customers": cust_count.scalar() or 0,
#         "new_orders": new_o.scalar() or 0,
#         "picked_up_orders": picked_o.scalar() or 0,
#         "delivered_orders": delivered_o.scalar() or 0,
#         "total_revenue": revenue,
#         "total_expenses": total_expenses,
#         "net_profit": net_profit,
#         "active_offers": offers.scalar() or 0
#     }

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

@router.get("/admin/analytics", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def get_advanced_analytics(db: AsyncSession = Depends(get_db)):
    # 1. Monthly Revenue Trend (Last 6 Months)
    revenue_stmt = (
        select(
            func.strftime('%Y-%m', Transaction.delivery_date).label('month'),
            func.sum(Transaction.received_amount).label('total')
        )
        .group_by('month')
        .order_by('month')
        .limit(6)
    )
    revenue_res = await db.execute(revenue_stmt)
    revenue_trend = [{"month": r.month, "amount": r.total} for r in revenue_res.all()]

    # 2. Top Performing Items (Most Ordered)
    item_stmt = (
        select(LaundryItem.name, func.sum(OrderItem.final_quantity).label('qty'))
        .join(OrderItem, LaundryItem.id == OrderItem.item_id)
        .group_by(LaundryItem.name)
        .order_by(func.sum(OrderItem.final_quantity).desc())
        .limit(5)
    )
    item_res = await db.execute(item_stmt)
    top_items = [{"name": r.name, "count": r.qty} for r in item_res.all()]

    return {
        "revenue_trend": revenue_trend,
        "top_items": top_items,
        "summary": await get_admin_dashboard(db) # Reuses the logic to include new profit metrics
    }