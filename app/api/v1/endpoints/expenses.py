# app/api/v1/endpoints/expenses.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from app.db.session import get_db
from app.api.deps import RoleChecker
from app.models.models import Expense, ExpenseCategory, UserRole
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseCategoryCreate, ExpenseCategoryResponse

router = APIRouter(dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])

# --- CATEGORIES ---
@router.get("/categories", response_model=List[ExpenseCategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExpenseCategory))
    return result.scalars().all()

@router.post("/categories", response_model=ExpenseCategoryResponse)
async def create_category(category_in: ExpenseCategoryCreate, db: AsyncSession = Depends(get_db)):
    db_obj = ExpenseCategory(**category_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

# --- EXPENSES ---
@router.get("/", response_model=List[ExpenseResponse])
async def get_expenses(db: AsyncSession = Depends(get_db)):
    # selectinload eagerly loads the related category so Pydantic can parse it
    result = await db.execute(
        select(Expense).options(selectinload(Expense.category)).order_by(Expense.expense_date.desc())
    )
    return result.scalars().all()

@router.post("/", response_model=ExpenseResponse)
async def log_expense(expense_in: ExpenseCreate, db: AsyncSession = Depends(get_db)):
    # Verify category exists
    cat_result = await db.execute(select(ExpenseCategory).where(ExpenseCategory.id == expense_in.category_id))
    if not cat_result.scalars().first():
        raise HTTPException(status_code=400, detail="Invalid Expense Category")

    db_obj = Expense(**expense_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    
    # Fetch again to populate the nested category relation for the response
    final_result = await db.execute(
        select(Expense).options(selectinload(Expense.category)).where(Expense.id == db_obj.id)
    )
    return final_result.scalars().first()


from app.schemas.expense import ExpenseUpdate # Don't forget to import this at the top!

@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int, 
    expense_in: ExpenseUpdate, 
    db: AsyncSession = Depends(get_db)
):
    # 1. Find the expense
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Expense not found")

    # 2. Update only the provided fields
    update_data = expense_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    # 3. Save and reload with category relations
    await db.commit()
    await db.refresh(db_obj)
    
    final_result = await db.execute(
        select(Expense).options(selectinload(Expense.category)).where(Expense.id == db_obj.id)
    )
    return final_result.scalars().first()