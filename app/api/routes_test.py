from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import audit_actor, get_app_settings
from app.core.config import Settings
from app.storage.database import get_db
from app.storage.repositories import create_audit_event, reset_paper_trading_state

router = APIRouter(prefix="/test", tags=["test"])


class ResetPaperStateResponse(BaseModel):
    message: str
    deleted: dict[str, int]


@router.post("/paper/reset")
def reset_paper_state(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ResetPaperStateResponse:
    if settings.app_env.lower() == "production":
        raise HTTPException(status_code=403, detail="test reset is not available in production")

    deleted = reset_paper_trading_state(db)
    create_audit_event(
        db,
        actor=audit_actor(request),
        action="test.paper_reset",
        entity_type="paper_account",
        entity_id=None,
        summary="重置测试环境模拟账户",
        payload={"deleted": deleted, "app_env": settings.app_env},
    )
    db.commit()
    return ResetPaperStateResponse(message="测试环境模拟账户已重置", deleted=deleted)
