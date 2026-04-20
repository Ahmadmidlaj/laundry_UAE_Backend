from pydantic import BaseModel

class SystemConfigBase(BaseModel):
    referral_system_enabled: bool = False
    reward_credits_per_referral: float = 50.0
    credit_conversion_rate: float = 1.0

class SystemConfigUpdate(SystemConfigBase):
    """Used for PUT requests to update settings."""
    pass

class SystemConfigResponse(SystemConfigBase):
    """Used for GET responses."""
    id: int
    
    model_config = {"from_attributes": True} 

