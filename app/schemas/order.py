from pydantic import BaseModel,Field
from typing import List, Optional
from datetime import datetime
from app.models.models import OrderStatus
from app.schemas.user import UserResponse

class OrderItemBase(BaseModel):
    item_id: int
    estimated_quantity: int

class SimpleItemResponse(BaseModel):
    name: str
    base_price: float
    
    class Config: 
        from_attributes = True

class OrderCreate(BaseModel):
    pickup_date: datetime
    pickup_time: str # e.g., "10:00 AM - 12:00 PM"
    notes: Optional[str] = None
    items: List[OrderItemBase]
    credits_to_use: Optional[float] = 0.0

class OrderItemResponse(OrderItemBase):
    unit_price: float
    final_quantity: int  # <-- ADDED: So staff/users can see the final count
    item: Optional[SimpleItemResponse] = None # <-- THE FIX: Tells Pydantic to include the joined LaundryItem!

    class Config: 
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    status: OrderStatus
    estimated_price: float
    discount_applied: float
    final_price: float = 0.0 # <-- ADDED: Good practice to include this too
    pickup_date: datetime
    pickup_time: Optional[str] = None
    

    expected_delivery_date: Optional[datetime] = None
    expected_delivery_time: Optional[str] = None

    items: List[OrderItemResponse]
    customer: Optional[UserResponse] = None
    created_at: Optional[datetime] = None    
    
    class Config: 
        from_attributes = True

class OrderItemUpdate(BaseModel):
    item_id: int
    final_quantity: int = Field(..., ge=0)

# 2. Then define the Admin update payload
class AdminOrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    pickup_date: Optional[datetime] = None
    pickup_time: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None
    expected_delivery_time: Optional[str] = None
    items: Optional[List[OrderItemUpdate]] = None 
    notes: Optional[str] = None