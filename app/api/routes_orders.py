from datetime import UTC, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import audit_actor, get_app_settings
from app.brokers.factory import build_broker_provider
from app.brokers.models import BrokerProviderError, OrderIntent
from app.core.config import Settings
from app.core.time import utc_now
from app.execution.live import LiveExecutor
from app.execution.paper import PaperExecutor
from app.market_data.models import MarketSnapshot
from app.storage.database import get_db
from app.storage.repositories import (
    create_audit_event,
    create_live_attempt,
    get_pending_live_preview,
    list_live_previews,
    list_paper_orders,
)
from app.storage.tables import ConferenceRunTable

router = APIRouter(prefix="/orders", tags=["orders"])


class ConfirmLiveOrderRequest(BaseModel):
    acknowledge_live_risk: bool = False
    production_confirmation_text: str | None = None
    confirm_symbol: str | None = None
    confirm_side: str | None = None
    confirm_quantity: str | None = None
    confirm_order_type: str | None = None
    confirm_estimated_notional: str | None = None
    confirm_account_id: str | None = None
    confirm_environment: str | None = None


@router.get("/paper")
def paper_orders(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "order_id": row.id,
            "client_order_id": row.client_order_id,
            "conference_id": row.conference_id,
            "symbol": row.symbol,
            "side": row.side,
            "quantity": row.quantity,
            "order_type": row.order_type,
            "limit_price": row.limit_price,
            "fill_price": row.fill_price,
            "notional": row.notional,
            "status": row.status,
            "mode": row.mode,
            "created_at": row.created_at,
        }
        for row in list_paper_orders(db, limit=limit)
    ]


@router.get("/previews")
@router.get("/live/previews")
def live_previews(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    return [_live_preview_dict(row) for row in list_live_previews(db, limit=limit)]


@router.post("/previews/{preview_id}/reject")
@router.post("/live/{preview_id}/reject")
def reject_live_preview(
    preview_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    row = get_pending_live_preview(db, preview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="live preview not found")
    if row.status != "PENDING_CONFIRMATION":
        raise HTTPException(status_code=409, detail=f"preview is already {row.status}")
    row.status = "REJECTED"
    mode_label = "模拟" if _is_paper_preview(row) else "实盘"
    create_audit_event(
        db,
        actor=audit_actor(request),
        action="order_preview.reject",
        entity_type="order_preview",
        entity_id=row.id,
        summary=f"拒绝 {row.symbol} {row.side} {mode_label}预览",
        payload={"symbol": row.symbol, "side": row.side, "quantity": row.quantity, "mode": _preview_mode(row)},
    )
    db.commit()
    return _live_preview_dict(row)


@router.post("/previews/{preview_id}/confirm")
@router.post("/live/{preview_id}/confirm")
async def confirm_live_preview(
    preview_id: str,
    request: ConfirmLiveOrderRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    row = get_pending_live_preview(db, preview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="live preview not found")
    if row.status != "PENDING_CONFIRMATION":
        raise HTTPException(status_code=409, detail=f"preview is already {row.status}")
    if _preview_expired(row.created_at, settings.live_preview_ttl_seconds):
        row.status = "EXPIRED"
        create_audit_event(
            db,
            actor=audit_actor(http_request),
            action="order_preview.expire",
            entity_type="order_preview",
            entity_id=row.id,
            summary=f"{row.symbol} {row.side} 订单预览已过期",
            payload={
                "symbol": row.symbol,
                "side": row.side,
                "quantity": row.quantity,
                "live_preview_ttl_seconds": settings.live_preview_ttl_seconds,
                "mode": _preview_mode(row),
            },
        )
        db.commit()
        raise HTTPException(status_code=409, detail="live preview expired")

    if _is_paper_preview(row):
        if not request.acknowledge_live_risk:
            raise HTTPException(status_code=400, detail="acknowledge_live_risk is required")
        order = _order_from_preview(row)
        snapshot = _snapshot_from_preview(row)
        execution = PaperExecutor().execute(
            db=db,
            conference_id=row.conference_id,
            order=order,
            snapshot=snapshot,
        )
        row.status = "FILLED"
        row.confirmed_at = utc_now()
        if row.conference_id:
            conference = db.get(ConferenceRunTable, row.conference_id)
            if conference:
                conference.order_id = execution.order_id
        create_audit_event(
            db,
            actor=audit_actor(http_request),
            action="paper_order.confirm",
            entity_type="order_preview",
            entity_id=row.id,
            summary=f"确认 {row.symbol} {row.side} 模拟订单",
            payload={
                "symbol": row.symbol,
                "side": row.side,
                "quantity": row.quantity,
                "paper_order_id": execution.order_id,
                "status": execution.status,
            },
        )
        db.commit()
        return {
            "preview": _live_preview_dict(row),
            "execution": execution.model_dump(mode="json"),
        }

    if not settings.live_ordering_enabled:
        raise HTTPException(status_code=403, detail="live trading is disabled")
    if not request.acknowledge_live_risk:
        raise HTTPException(status_code=400, detail="acknowledge_live_risk is required")
    if settings.webull_env == "production" or row.environment == "production":
        missing_config = _production_configuration_gaps(settings)
        if missing_config:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "production live configuration is incomplete",
                    "missing": missing_config,
                },
            )
        mismatches = _confirmation_mismatches(request, row)
        if mismatches:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "production confirmation details mismatch",
                    "mismatches": mismatches,
                },
            )
        expected = _production_confirmation_text(row)
        if request.production_confirmation_text != expected:
            raise HTTPException(
                status_code=400,
                detail=f"production confirmation text must be exactly: {expected}",
            )

    order = OrderIntent(
        client_order_id=row.client_order_id,
        symbol=row.symbol,
        side=row.side,  # type: ignore[arg-type]
        quantity=Decimal(row.quantity),
        order_type=row.order_type,  # type: ignore[arg-type]
        limit_price=Decimal(row.limit_price) if row.limit_price else None,
        notional=Decimal(row.estimated_notional) if row.estimated_notional else None,
    )
    provider = build_broker_provider(settings)
    executor = LiveExecutor(settings, provider)
    request_payload = {
        "preview_id": row.id,
        "order": order.model_dump(mode="json"),
        "acknowledge_live_risk": request.acknowledge_live_risk,
    }
    try:
        execution = await executor.place(order)
    except BrokerProviderError as exc:
        create_live_attempt(
            db,
            preview_id=row.id,
            status="FAILED",
            request_payload=request_payload,
            error_payload={"code": exc.code, "message": str(exc), "details": exc.details},
        )
        row.status = "FAILED"
        create_audit_event(
            db,
            actor=audit_actor(http_request),
            action="live_order.confirm_failed",
            entity_type="live_order_preview",
            entity_id=row.id,
            summary=f"{row.symbol} {row.side} 实盘确认失败",
            payload={"code": exc.code, "symbol": row.symbol, "side": row.side, "quantity": row.quantity},
        )
        db.commit()
        raise HTTPException(status_code=502, detail={"code": exc.code, "message": str(exc)})
    create_live_attempt(
        db,
        preview_id=row.id,
        status=execution.status,
        request_payload=request_payload,
        response_payload=execution.model_dump(mode="json"),
        provider_order_id=execution.order_id,
    )
    row.status = "CONFIRMED"
    row.confirmed_at = utc_now()
    create_audit_event(
        db,
        actor=audit_actor(http_request),
        action="live_order.confirm",
        entity_type="live_order_preview",
        entity_id=row.id,
        summary=f"确认 {row.symbol} {row.side} 实盘订单",
        payload={
            "symbol": row.symbol,
            "side": row.side,
            "quantity": row.quantity,
            "provider_order_id": execution.order_id,
            "status": execution.status,
        },
    )
    db.commit()
    return {
        "preview": _live_preview_dict(row),
        "execution": execution.model_dump(mode="json"),
    }


def _live_preview_dict(row) -> dict:
    return {
        "preview_id": row.id,
        "client_order_id": row.client_order_id,
        "conference_id": row.conference_id,
        "symbol": row.symbol,
        "side": row.side,
        "quantity": row.quantity,
        "order_type": row.order_type,
        "limit_price": row.limit_price,
        "estimated_notional": row.estimated_notional,
        "status": row.status,
        "account_id": row.account_id,
        "environment": row.environment,
        "mode": _preview_mode(row),
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
    }


def _preview_mode(row) -> str:
    return "paper" if _is_paper_preview(row) else "live"


def _is_paper_preview(row) -> bool:
    return row.environment == "paper" or row.account_id == "paper"


def _order_from_preview(row) -> OrderIntent:
    return OrderIntent(
        client_order_id=row.client_order_id,
        symbol=row.symbol,
        side=row.side,  # type: ignore[arg-type]
        quantity=Decimal(row.quantity),
        order_type=row.order_type,  # type: ignore[arg-type]
        limit_price=Decimal(row.limit_price) if row.limit_price else None,
        notional=Decimal(row.estimated_notional) if row.estimated_notional else None,
    )


def _snapshot_from_preview(row) -> MarketSnapshot:
    payload = row.preview_payload or {}
    snapshot_payload = payload.get("snapshot")
    if isinstance(snapshot_payload, dict):
        return MarketSnapshot.model_validate(snapshot_payload)
    raise HTTPException(status_code=409, detail="paper preview snapshot is unavailable")


def _preview_expired(created_at, ttl_seconds: int) -> bool:
    value = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    return utc_now() - value > timedelta(seconds=ttl_seconds)


def _confirmation_mismatches(request: ConfirmLiveOrderRequest, row) -> list[str]:
    expected = {
        "confirm_symbol": row.symbol,
        "confirm_side": row.side,
        "confirm_quantity": row.quantity,
        "confirm_order_type": row.order_type,
        "confirm_estimated_notional": row.estimated_notional or "",
        "confirm_account_id": row.account_id,
        "confirm_environment": row.environment,
    }
    mismatches: list[str] = []
    for field, expected_value in expected.items():
        actual = getattr(request, field)
        if actual != expected_value:
            mismatches.append(field)
    return mismatches


def _production_confirmation_text(row) -> str:
    notional = row.estimated_notional or "UNKNOWN"
    return (
        f"CONFIRM {row.symbol} {row.side} {row.quantity} "
        f"{row.order_type} {notional} {row.account_id} {row.environment}"
    )


def _production_configuration_gaps(settings: Settings) -> list[str]:
    missing: list[str] = []
    if settings.broker_provider != "webull":
        missing.append("broker_provider must be webull")
    if not settings.has_webull_credentials:
        missing.append("webull credentials")
    if not settings.webull_account_id:
        missing.append("webull account id")
    if not settings.api_auth_required or not settings.api_auth_token:
        missing.append("api authentication")
    return missing
