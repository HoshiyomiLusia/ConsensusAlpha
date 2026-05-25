from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.brokers.factory import build_broker_provider
from app.core.config import Settings

router = APIRouter(tags=["provider"])


@router.get("/provider/status")
async def provider_status(settings: Settings = Depends(get_app_settings)) -> dict:
    provider = build_broker_provider(settings)
    status = await provider.status()
    return status.model_dump(mode="json")
