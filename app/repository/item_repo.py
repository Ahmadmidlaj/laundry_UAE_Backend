from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.models import LaundryItem, ItemServicePrice
from app.schemas.item import ItemCreate, ItemUpdate

async def create_item(db: AsyncSession, item_in: ItemCreate):
    # Separate the nested services from the base item
    data = item_in.model_dump()
    services_data = data.pop("services", [])
    
    db_item = LaundryItem(**data)
    db.add(db_item)
    await db.flush() # Flush to get the item ID
    
    # Add matrix prices
    for svc in services_data:
        db.add(ItemServicePrice(
            item_id=db_item.id,
            service_category_id=svc["service_category_id"],
            price=svc["price"]
        ))
        
    await db.commit()
    await db.refresh(db_item) # <--- THE MAGIC FIX: Reloads basic attributes like name & base_price
    
    # Return the newly created item with all relations loaded to satisfy Pydantic
    result = await db.execute(
        select(LaundryItem)
        .where(LaundryItem.id == db_item.id)
        .options(selectinload(LaundryItem.services).joinedload(ItemServicePrice.category))
    )
    return result.scalars().first()
    
    # # Return the newly created item with all relations loaded to satisfy Pydantic
    # result = await db.execute(
    #     select(LaundryItem)
    #     .where(LaundryItem.id == db_item.id)
    #     .options(selectinload(LaundryItem.services).joinedload(ItemServicePrice.category))
    # )
    # return result.scalars().first()

async def get_all_items(db: AsyncSession):
    # THE FIX: Eagerly load the services and category names
    result = await db.execute(
        select(LaundryItem)
        .options(selectinload(LaundryItem.services).joinedload(ItemServicePrice.category))
    )
    return result.scalars().unique().all()


async def update_item(db: AsyncSession, item_id: int, item_in: ItemUpdate):
    result = await db.execute(select(LaundryItem).where(LaundryItem.id == item_id))
    db_item = result.scalars().first()
    
    if not db_item:
        return None
        
    update_data = item_in.model_dump(exclude_unset=True)
    services_data = update_data.pop("services", None)
    
    # Update base fields
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    # Update matrix prices if provided
    if services_data is not None:
        # Clear old services
        from sqlalchemy import delete
        await db.execute(delete(ItemServicePrice).where(ItemServicePrice.item_id == item_id))
        
        # Insert new services
        for svc in services_data:
            db.add(ItemServicePrice(
                item_id=item_id,
                service_category_id=svc["service_category_id"],
                price=svc["price"]
            ))

    await db.commit()
    await db.refresh(db_item) # <--- THE MAGIC FIX: Reloads basic attributes
    
    # Return the updated item with all relations loaded to satisfy Pydantic
    final_result = await db.execute(
        select(LaundryItem)
        .where(LaundryItem.id == item_id)
        .options(selectinload(LaundryItem.services).joinedload(ItemServicePrice.category))
    )
    return final_result.scalars().first()


# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from app.models.models import LaundryItem
# from app.schemas.item import ItemCreate, ItemUpdate

# async def create_item(db: AsyncSession, item_in: ItemCreate):
#     db_item = LaundryItem(**item_in.model_dump())
#     db.add(db_item)
#     await db.commit()
#     await db.refresh(db_item)
#     return db_item

# async def get_all_items(db: AsyncSession):
#     result = await db.execute(select(LaundryItem))
#     return result.scalars().all()

# async def update_item(db: AsyncSession, item_id: int, item_in: ItemUpdate):
#     result = await db.execute(select(LaundryItem).where(LaundryItem.id == item_id))
#     db_item = result.scalars().first()
#     if db_item:
#         update_data = item_in.model_dump(exclude_unset=True)
#         for key, value in update_data.items():
#             setattr(db_item, key, value)
#         await db.commit()
#         await db.refresh(db_item)
#     return db_item