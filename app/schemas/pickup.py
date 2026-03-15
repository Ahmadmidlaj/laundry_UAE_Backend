from pydantic import BaseModel
from typing import List

class PickupItemUpdate(BaseModel):
    item_id: int
    final_quantity: int

class PickupCreate(BaseModel):
    items: List[PickupItemUpdate]