from pydantic import BaseModel, Field
from typing import Optional

class ItemBase(BaseModel):
    name: str = Field(..., example="Silk Shirt")
    base_price: float = Field(..., gt=0, example=15.50)

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    base_price: Optional[float] = None

class ItemResponse(ItemBase):
    id: int

    class Config:
        from_attributes = True