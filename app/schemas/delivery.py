from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum

class PaymentMethod(str, Enum):
    CASH = "CASH"
    CARD = "CARD"

class DeliveryCreate(BaseModel):
    received_amount: float = Field(..., gt=0)
    payment_method: PaymentMethod
    notes: Optional[str] = None
    delivery_date: datetime = Field(default_factory=datetime.now)

    @field_validator('received_amount')
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Received amount must be greater than zero')
        return v