from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class OfferBase(BaseModel):
    name: str
    min_order_amount: float
    discount_amount: float
    start_date: datetime
    end_date: datetime
    is_active: bool = True
    discount_type: str = "FIXED"

class OfferCreate(OfferBase):
    pass

class OfferResponse(OfferBase):
    id: int
    class Config: from_attributes = True