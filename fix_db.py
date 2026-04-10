import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from alembic.config import Config

async def main():
    alembic_cfg = Config("alembic.ini")
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version;"))
        
    print("✅ Orphaned version table dropped successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())