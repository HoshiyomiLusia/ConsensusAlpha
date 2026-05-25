from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.storage.database import get_db
from app.storage.repositories import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEvent(BaseModel):
    event_id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    payload: dict
    created_at: datetime


@router.get("", response_model=list[AuditEvent])
def audit_events(limit: int = 100, db: Session = Depends(get_db)) -> list[AuditEvent]:
    return [
        AuditEvent(
            event_id=row.id,
            actor=row.actor,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            summary=row.summary,
            payload=row.payload or {},
            created_at=row.created_at,
        )
        for row in list_audit_events(db, limit=limit)
    ]
