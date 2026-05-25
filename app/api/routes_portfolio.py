from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings
from app.brokers.factory import build_broker_provider
from app.core.config import Settings
from app.portfolio.service import get_effective_positions
from app.storage.database import get_db

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/positions")
async def positions(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> list[dict]:
    provider = build_broker_provider(settings)
    rows = await get_effective_positions(db=db, settings=settings, provider=provider)
    return [row.model_dump(mode="json") for row in rows]
