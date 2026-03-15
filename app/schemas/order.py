from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.models.models import OrderStatus

class OrderItemBase(BaseModel):
    item_id: int
    estimated_quantity: int

class OrderCreate(BaseModel):
    pickup_date: datetime
    pickup_time: str # e.g., "10:00 AM - 12:00 PM"
    notes: Optional[str] = None
    items: List[OrderItemBase]

class OrderItemResponse(OrderItemBase):
    unit_price: float
    class Config: from_attributes = True

class OrderResponse(BaseModel):
    id: int
    status: OrderStatus
    estimated_price: float
    discount_applied: float
    pickup_date: datetime
    items: List[OrderItemResponse]
    
    class Config: from_attributes = True