from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.brokers.factory import build_broker_provider
from app.core.config import Settings

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/positions")
async def positions(settings: Settings = Depends(get_app_settings)) -> list[dict]:
    provider = build_broker_provider(settings)
    rows = await provider.get_positions()
    return [row.model_dump(mode="json") for row in rows]
