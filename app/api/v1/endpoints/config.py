# this route is for admins to manage referrals
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.api.deps import RoleChecker
from app.models.models import SystemConfig, UserRole
from app.schemas.config import SystemConfigUpdate, SystemConfigResponse

router = APIRouter()

@router.get("/", response_model=SystemConfigResponse)
async def get_system_config(db: AsyncSession = Depends(get_db)):
    """Publicly accessible (but read-only) config for frontend logic."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalars().first()
    
    if not config:
        # Auto-initialize with defaults if the table is empty
        config = SystemConfig(
            referral_system_enabled=False,
            reward_credits_per_referral=50.0,
            credit_conversion_rate=1.0
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        
    return config

@router.put("/", response_model=SystemConfigResponse, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_system_config(config_in: SystemConfigUpdate, db: AsyncSession = Depends(get_db)):
    """ADMIN ONLY: Update global settings."""
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalars().first()
    
    if not config:
        config = SystemConfig(**config_in.model_dump())
        db.add(config)
    else:
        for key, value in config_in.model_dump().items():
            setattr(config, key, value)
            
    await db.commit()
    await db.refresh(config)
    return config