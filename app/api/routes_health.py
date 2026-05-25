from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.core.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_app_settings)) -> dict:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "broker_provider": settings.broker_provider,
        "webull_env": settings.webull_env,
    }
