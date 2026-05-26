from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm_provider import build_llm_provider
from app.brokers.factory import build_broker_provider
from app.conference.models import (
    AgentOpinion,
    ConferenceDetail,
    ConferenceListItem,
    ConferenceResult,
    ConferenceRunRequest,
    ConferenceRunResponse,
    ModelUsageEvent,
    ModelUsageSummary,
)
from app.conference.orchestrator import ConferenceOrchestrator
from app.core.config import Settings
from app.api.dependencies import audit_actor, get_app_settings
from app.market_data.models import MarketSnapshot
from app.risk.models import RiskCheck, RiskDecision
from app.storage.database import get_db
from app.storage.repositories import create_audit_event, list_model_usage_events, list_recent_conferences
from app.storage.tables import (
    AgentOpinionTable,
    ConferenceRunTable,
    LiveOrderPreviewTable,
    MarketSnapshotTable,
    PaperOrderTable,
    RiskDecisionTable,
)

router = APIRouter(prefix="/conference", tags=["conference"])


@router.get("", response_model=list[ConferenceListItem])
def list_conferences(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[ConferenceListItem]:
    rows = list_recent_conferences(db, limit=limit)
    return [
        ConferenceListItem(
            conference_id=row.id,
            symbol=row.symbol,
            final_action=row.final_action,  # type: ignore[arg-type]
            consensus_reached=row.consensus_reached,
            risk_approved=None,
            order_id=row.order_id,
            live_preview_id=row.live_preview_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/run", response_model=ConferenceRunResponse)
async def run_conference(
    request: ConferenceRunRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ConferenceRunResponse:
    provider = build_broker_provider(settings)
    llm_provider = build_llm_provider(settings)
    orchestrator = ConferenceOrchestrator(
        settings=settings,
        provider=provider,
        llm_provider=llm_provider,
    )
    result = await orchestrator.run(db=db, request=request)
    create_audit_event(
        db,
        actor=audit_actor(http_request),
        action="conference.run",
        entity_type="conference",
        entity_id=result.conference_id,
        summary=f"{result.symbol} 会议完成，结果为 {result.final_action}",
        payload={
            "symbol": result.symbol,
            "final_action": result.final_action,
            "consensus_reached": result.consensus_reached,
            "risk_approved": result.risk_approved,
            "order_id": result.order_id,
            "live_preview_id": result.live_preview_id,
        },
    )
    db.commit()
    return result


@router.get("/{conference_id}", response_model=ConferenceDetail)
def get_conference(
    conference_id: str,
    db: Session = Depends(get_db),
) -> ConferenceDetail:
    run = db.get(ConferenceRunTable, conference_id)
    if run is None:
        raise HTTPException(status_code=404, detail="conference not found")

    snapshot = db.get(MarketSnapshotTable, run.snapshot_id) if run.snapshot_id else None
    opinion_rows = list(
        db.scalars(select(AgentOpinionTable).where(AgentOpinionTable.conference_id == run.id))
    )
    opinions = [_opinion_from_row(row) for row in opinion_rows]
    risk_row = db.get(RiskDecisionTable, run.risk_decision_id) if run.risk_decision_id else None
    risk_decision = _risk_from_row(risk_row) if risk_row else None
    model_usage = _model_usage_from_rows(list_model_usage_events(db, run.id))
    order_result = None
    if run.order_id:
        order_row = db.get(PaperOrderTable, run.order_id)
        if order_row:
            order_result = _paper_order_dict(order_row)
    live_preview = None
    if run.live_preview_id:
        preview_row = db.get(LiveOrderPreviewTable, run.live_preview_id)
        if preview_row:
            live_preview = _live_preview_dict(preview_row)

    consensus = ConferenceResult(
        conference_id=run.id,
        symbol=run.symbol,
        started_at=run.started_at,
        completed_at=run.completed_at or run.updated_at,
        opinions=opinions,
        final_action=run.final_action,  # type: ignore[arg-type]
        consensus_reached=run.consensus_reached,
        consensus_reason=run.consensus_reason,
        chairperson_summary=run.chairperson_summary,
    )
    return ConferenceDetail(
        conference_id=run.id,
        symbol=run.symbol,
        snapshot=_snapshot_from_row(snapshot) if snapshot else None,
        opinions=opinions,
        chairperson_summary=run.chairperson_summary,
        consensus_result=consensus,
        risk_decision=risk_decision,
        model_usage=model_usage,
        order_result=order_result,
        live_preview=live_preview,
    )


def _snapshot_from_row(row: MarketSnapshotTable) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=row.symbol,
        asset_type=row.asset_type,  # type: ignore[arg-type]
        price=Decimal(row.price),
        open=Decimal(row.open) if row.open else None,
        high=Decimal(row.high) if row.high else None,
        low=Decimal(row.low) if row.low else None,
        previous_close=Decimal(row.previous_close) if row.previous_close else None,
        volume=row.volume,
        timestamp=row.timestamp,
        source=row.source,
        raw_payload=row.raw_payload or {},
    )


def _opinion_from_row(row: AgentOpinionTable) -> AgentOpinion:
    return AgentOpinion(
        agent_id=row.agent_id,
        role=row.role,
        symbol=row.symbol,
        action=row.action,  # type: ignore[arg-type]
        confidence=row.confidence,
        thesis=row.thesis,
        concerns=row.concerns or [],
        blocking_concerns=row.blocking_concerns or [],
        suggested_max_position_pct=row.suggested_max_position_pct,
        suggested_stop_loss_pct=row.suggested_stop_loss_pct,
        prompt_version=row.prompt_version or None,
        raw_payload=row.raw_payload or {},
    )


def _risk_from_row(row: RiskDecisionTable) -> RiskDecision:
    checks = [RiskCheck.model_validate(check) for check in row.checks_payload or []]
    return RiskDecision(
        approved=row.approved,
        reason=row.reason,
        checks=checks,
        max_quantity=Decimal(row.max_quantity) if row.max_quantity else None,
        max_notional=Decimal(row.max_notional) if row.max_notional else None,
    )


def _model_usage_from_rows(rows) -> ModelUsageSummary:
    events = [
        ModelUsageEvent(
            role=row.role,
            operation=row.operation,
            provider=row.provider,
            model=row.model,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=row.total_tokens,
            estimated=row.estimated,
            prompt_version=row.prompt_version or None,
        )
        for row in rows
    ]
    return ModelUsageSummary(
        prompt_tokens=sum(event.prompt_tokens for event in events),
        completion_tokens=sum(event.completion_tokens for event in events),
        total_tokens=sum(event.total_tokens for event in events),
        estimated=any(event.estimated for event in events),
        events=events,
    )


def _paper_order_dict(row: PaperOrderTable) -> dict:
    return {
        "order_id": row.id,
        "client_order_id": row.client_order_id,
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


def _live_preview_dict(row: LiveOrderPreviewTable) -> dict:
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
        "mode": "paper" if row.environment == "paper" or row.account_id == "paper" else "live",
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
    }
