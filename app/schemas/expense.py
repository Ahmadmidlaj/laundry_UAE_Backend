# app/schemas/expense.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Categories ---
class ExpenseCategoryBase(BaseModel):
    name: str
    is_active: bool = True

class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass

class ExpenseCategoryResponse(ExpenseCategoryBase):
    id: int
    model_config = {"from_attributes": True}

# --- Expenses ---
class ExpenseBase(BaseModel):
    category_id: int
    amount: float
    expense_date: Optional[datetime] = None
    remarks: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseResponse(ExpenseBase):
    id: int
    category: ExpenseCategoryResponse # Includes the nested category object
    model_config = {"from_attributes": True}

class ExpenseUpdate(BaseModel):
    category_id: Optional[int] = None
    amount: Optional[float] = None
    expense_date: Optional[datetime] = None
    remarks: Optional[str] = None