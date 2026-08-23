from pydantic import BaseModel, Field

from src.feature_flags import FeatureFlags


class AppSettingsResponse(BaseModel):
    """Schema for returning public application settings."""

    feature_flags: FeatureFlags = Field(..., description="All feature flags")
    version: str = Field(..., description='Running server release, or "unknown"')
