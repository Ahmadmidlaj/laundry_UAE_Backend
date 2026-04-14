from pydantic import BaseModel
from typing import List
from datetime import datetime

class PickupItemUpdate(BaseModel):
    item_id: int
    service_category_id: int
    final_quantity: int
  

class PickupCreate(BaseModel):
    items: List[PickupItemUpdate]
    expected_delivery_date: datetime  # Changed to datetime per your note
    expected_delivery_time: str