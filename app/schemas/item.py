from pydantic import BaseModel, Field
from typing import Optional, List


# --- NEW SCHEMAS ---
class ServiceCategoryResponse(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class ItemServicePriceBase(BaseModel):
    service_category_id: int
    price: float

class ItemServicePriceResponse(ItemServicePriceBase):
    id: int
    category: ServiceCategoryResponse
    class Config:
        from_attributes = True

class ItemBase(BaseModel):
    name: str = Field(..., example="Silk Shirt")
    # base_price: float = Field(..., gt=0, example=15.50)

class ItemCreate(ItemBase):
    services: List[ItemServicePriceBase] = Field(..., min_length=1)# Admin can pass matrix prices

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    base_price: Optional[float] = None
    services: Optional[List[ItemServicePriceBase]] = None

class ItemResponse(ItemBase):
    id: int
    services: List[ItemServicePriceResponse] = [] # Exposes matrix to frontend

    class Config:
        from_attributes = True