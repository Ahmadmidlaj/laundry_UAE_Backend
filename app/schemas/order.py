from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.models.models import OrderStatus
from app.schemas.user import UserResponse

class OrderItemBase(BaseModel):
    item_id: int
    service_category_id: int # <-- STRICTLY REQUIRED NOW (No longer Optional)
    estimated_quantity: int

class SimpleItemResponse(BaseModel):
    name: str
    # DELETED: base_price (We rely purely on the matrix now)
    
    class Config: 
        from_attributes = True

# NEW: Added this so the frontend can display "(Dry Clean)" next to the item name
class SimpleCategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    pickup_date: datetime
    pickup_time: str # e.g., "10:00 AM - 12:00 PM"
    notes: Optional[str] = None
    items: List[OrderItemBase]
    credits_to_use: Optional[float] = 0.0
    hanger_needed: Optional[bool] = False

class OrderItemResponse(OrderItemBase):
    unit_price: float
    final_quantity: int  
    item: Optional[SimpleItemResponse] = None 
    service_category: Optional[SimpleCategoryResponse] = None # <-- ADDED FOR UI

    class Config: 
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    status: OrderStatus
    estimated_price: float
    discount_applied: float
    final_price: float = 0.0 
    pickup_date: datetime
    pickup_time: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None
    expected_delivery_time: Optional[str] = None

    items: List[OrderItemResponse]
    customer: Optional[UserResponse] = None
    created_at: Optional[datetime] = None    
    hanger_needed: bool = False
    notes: Optional[str] = None
    
    class Config: 
        from_attributes = True

class OrderItemUpdate(BaseModel):
    item_id: int
    service_category_id: int # <-- ADDED: So admin targets the exact matrix service when updating quantities
    final_quantity: int = Field(..., ge=0)
    unit_price: Optional[float] = None
    

# 2. Then define the Admin update payload
class AdminOrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    pickup_date: Optional[datetime] = None
    pickup_time: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None
    expected_delivery_time: Optional[str] = None
    items: Optional[List[OrderItemUpdate]] = None 
    notes: Optional[str] = None
    hanger_needed: Optional[bool] = None

class CustomerOrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    notes: Optional[str] = None
    pickup_date: Optional[datetime] = None
    pickup_time: Optional[str] = None

    items: Optional[List[OrderItemBase]] = None 
    credits_to_use: Optional[float] = None
    hanger_needed: Optional[bool] = None
