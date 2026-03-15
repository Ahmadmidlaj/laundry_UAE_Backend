from pydantic import BaseModel
from typing import List

class AdminDashboard(BaseModel):
    total_customers: int
    new_orders: int
    picked_up_orders: int
    delivered_orders: int
    total_revenue: float
    active_offers: int

class CustomerStats(BaseModel):
    total_orders: int
    monthly_spending: float
    total_discounts: float