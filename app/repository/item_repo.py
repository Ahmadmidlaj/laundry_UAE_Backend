from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import LaundryItem
from app.schemas.item import ItemCreate, ItemUpdate

async def create_item(db: AsyncSession, item_in: ItemCreate):
    db_item = LaundryItem(**item_in.model_dump())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def get_all_items(db: AsyncSession):
    result = await db.execute(select(LaundryItem))
    return result.scalars().all()

async def update_item(db: AsyncSession, item_id: int, item_in: ItemUpdate):
    result = await db.execute(select(LaundryItem).where(LaundryItem.id == item_id))
    db_item = result.scalars().first()
    if db_item:
        update_data = item_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_item, key, value)
        await db.commit()
        await db.refresh(db_item)
    return db_item