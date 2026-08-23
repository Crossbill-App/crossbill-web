from fastapi import APIRouter

from src.config import get_settings
from src.feature_flags import get_feature_flags
from src.infrastructure.common.schemas import AppSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_app_settings() -> AppSettingsResponse:
    """
    Get public application settings.

    Returns non-user-specific settings that affect application behavior.
    This is a public endpoint that doesn't require authentication.
    """
    return AppSettingsResponse(feature_flags=get_feature_flags(), version=get_settings().VERSION)
