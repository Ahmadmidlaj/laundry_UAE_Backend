from pydantic import BaseModel
from typing import List, Optional

class BuildingBase(BaseModel):
    name: str
    flats: List[str] = []
    is_active: bool = True

class BuildingCreate(BuildingBase):
    pass

class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    flats: Optional[List[str]] = None
    is_active: Optional[bool] = None

class BuildingResponse(BuildingBase):
    id: int

    # FIX: Pydantic V2 uses model_config instead of Config
    model_config = {
        "from_attributes": True
    }