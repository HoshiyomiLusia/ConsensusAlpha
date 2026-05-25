from decimal import Decimal
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.conference.models import AgentOpinion
from app.market_data.models import MarketSnapshot
from app.proposals.models import ProposalRunRequest, ProposalRunResponse
from app.risk.models import RiskDecision
from app.storage.tables import (
    AgentOpinionTable,
    AuditEventTable,
    ConferenceRunTable,
    ConsensusResultTable,
    LiveOrderAttemptTable,
    LiveOrderPreviewTable,
    MarketSnapshotTable,
    ModelUsageEventTable,
    PaperFillTable,
    PaperOrderTable,
    PaperPositionTable,
    ProposalItemTable,
    ProposalRunTable,
    RiskCheckTable,
    RiskDecisionTable,
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def save_snapshot(db: Session, snapshot: MarketSnapshot) -> MarketSnapshotTable:
    row = MarketSnapshotTable(
        id=new_id("snap"),
        symbol=snapshot.symbol.upper(),
        asset_type=snapshot.asset_type,
        price=decimal_to_str(snapshot.price),
        open=decimal_to_str(snapshot.open),
        high=decimal_to_str(snapshot.high),
        low=decimal_to_str(snapshot.low),
        previous_close=decimal_to_str(snapshot.previous_close),
        volume=snapshot.volume,
        timestamp=snapshot.timestamp,
        source=snapshot.source,
        raw_payload=snapshot.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()
    return row


def save_opinions(db: Session, conference_id: str, opinions: list[AgentOpinion]) -> None:
    for opinion in opinions:
        db.add(
            AgentOpinionTable(
                id=new_id("op"),
                conference_id=conference_id,
                agent_id=opinion.agent_id,
                role=opinion.role,
                symbol=opinion.symbol.upper(),
                action=opinion.action,
                confidence=opinion.confidence,
                thesis=opinion.thesis,
                concerns=opinion.concerns,
                blocking_concerns=opinion.blocking_concerns,
                suggested_max_position_pct=opinion.suggested_max_position_pct,
                suggested_stop_loss_pct=opinion.suggested_stop_loss_pct,
                prompt_version=opinion.prompt_version or "",
                raw_payload=opinion.model_dump(mode="json"),
            )
        )


def save_model_usage_events(db: Session, conference_id: str, events: list[dict]) -> None:
    for event in events:
        db.add(
            ModelUsageEventTable(
                id=new_id("usage"),
                conference_id=conference_id,
                role=str(event.get("role") or "unknown"),
                operation=str(event.get("operation") or "unknown"),
                provider=str(event.get("provider") or "unknown"),
                model=str(event.get("model") or ""),
                prompt_tokens=int(event.get("prompt_tokens") or 0),
                completion_tokens=int(event.get("completion_tokens") or 0),
                total_tokens=int(event.get("total_tokens") or 0),
                estimated=bool(event.get("estimated", False)),
                prompt_version=str(event.get("prompt_version") or ""),
                raw_payload=event.get("raw_payload") or {},
            )
        )
    db.flush()


def save_risk_decision(
    db: Session, *, conference_id: str | None, decision: RiskDecision
) -> RiskDecisionTable:
    row = RiskDecisionTable(
        id=new_id("risk"),
        conference_id=conference_id,
        approved=decision.approved,
        reason=decision.reason,
        max_quantity=decimal_to_str(decision.max_quantity),
        max_notional=decimal_to_str(decision.max_notional),
        checks_payload=[check.model_dump(mode="json") for check in decision.checks],
    )
    db.add(row)
    db.flush()
    for check in decision.checks:
        db.add(
            RiskCheckTable(
                id=new_id("check"),
                risk_decision_id=row.id,
                name=check.name,
                passed=check.passed,
                reason=check.reason,
                data=check.data,
            )
        )
    db.flush()
    return row


def save_proposal_run(
    db: Session, *, request: ProposalRunRequest, result: ProposalRunResponse
) -> ProposalRunTable:
    row = ProposalRunTable(
        id=result.proposal_run_id,
        candidate_count=result.candidate_count,
        proposal_count=len(result.proposals),
        used_llm=result.used_llm,
        llm_provider=result.llm_provider,
        request_payload=request.model_dump(mode="json"),
        scan_payload=[item.model_dump(mode="json") for item in result.scanned],
        message=result.message,
    )
    db.add(row)
    db.flush()
    for proposal in result.proposals:
        db.add(
            ProposalItemTable(
                id=new_id("proposal_item"),
                proposal_run_id=result.proposal_run_id,
                symbol=proposal.symbol.upper(),
                asset_type=proposal.asset_type,
                proposed_action=proposal.proposed_action,
                confidence=proposal.confidence,
                thesis=proposal.thesis,
                risks=proposal.risks,
                suggested_max_notional=decimal_to_str(proposal.suggested_max_notional) or "0",
                source=proposal.source,
                rank=proposal.rank,
                scan_score=proposal.scan_score,
                raw_payload=proposal.model_dump(mode="json"),
            )
        )
    db.flush()
    return row


def list_recent_conferences(db: Session, limit: int = 50) -> list[ConferenceRunTable]:
    stmt = select(ConferenceRunTable).order_by(desc(ConferenceRunTable.created_at)).limit(limit)
    return list(db.scalars(stmt))


def create_audit_event(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    summary: str,
    payload: dict | None = None,
) -> AuditEventTable:
    row = AuditEventTable(
        id=new_id("audit"),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        payload=payload or {},
    )
    db.add(row)
    db.flush()
    return row


def list_audit_events(db: Session, limit: int = 100) -> list[AuditEventTable]:
    stmt = select(AuditEventTable).order_by(desc(AuditEventTable.created_at)).limit(limit)
    return list(db.scalars(stmt))


def list_model_usage_events(db: Session, conference_id: str) -> list[ModelUsageEventTable]:
    stmt = (
        select(ModelUsageEventTable)
        .where(ModelUsageEventTable.conference_id == conference_id)
        .order_by(ModelUsageEventTable.created_at)
    )
    return list(db.scalars(stmt))


def list_recent_proposals(db: Session, limit: int = 20) -> list[ProposalRunTable]:
    stmt = select(ProposalRunTable).order_by(desc(ProposalRunTable.created_at)).limit(limit)
    return list(db.scalars(stmt))


def get_proposal_run(db: Session, proposal_run_id: str) -> ProposalRunTable | None:
    return db.get(ProposalRunTable, proposal_run_id)


def list_proposal_items(db: Session, proposal_run_id: str) -> list[ProposalItemTable]:
    stmt = (
        select(ProposalItemTable)
        .where(ProposalItemTable.proposal_run_id == proposal_run_id)
        .order_by(ProposalItemTable.rank)
    )
    return list(db.scalars(stmt))


def list_conferences_for_proposal(db: Session, proposal_run_id: str) -> list[ConferenceRunTable]:
    rows = list_recent_conferences(db, limit=200)
    return [
        row
        for row in rows
        if (row.context_payload or {}).get("request", {}).get("proposal_run_id") == proposal_run_id
    ]


def list_paper_orders(db: Session, limit: int = 100) -> list[PaperOrderTable]:
    stmt = select(PaperOrderTable).order_by(desc(PaperOrderTable.created_at)).limit(limit)
    return list(db.scalars(stmt))


def list_paper_positions(db: Session) -> list[PaperPositionTable]:
    stmt = select(PaperPositionTable).order_by(PaperPositionTable.symbol)
    return list(db.scalars(stmt))


def list_live_previews(db: Session, limit: int = 100) -> list[LiveOrderPreviewTable]:
    stmt = select(LiveOrderPreviewTable).order_by(desc(LiveOrderPreviewTable.created_at)).limit(limit)
    return list(db.scalars(stmt))


def get_pending_live_preview(db: Session, preview_id: str) -> LiveOrderPreviewTable | None:
    stmt = select(LiveOrderPreviewTable).where(LiveOrderPreviewTable.id == preview_id)
    return db.scalar(stmt)


def create_live_attempt(
    db: Session,
    *,
    preview_id: str,
    status: str,
    request_payload: dict,
    response_payload: dict | None = None,
    error_payload: dict | None = None,
    provider_order_id: str | None = None,
) -> LiveOrderAttemptTable:
    row = LiveOrderAttemptTable(
        id=new_id("attempt"),
        preview_id=preview_id,
        provider_order_id=provider_order_id,
        status=status,
        request_payload=request_payload,
        response_payload=response_payload or {},
        error_payload=error_payload or {},
    )
    db.add(row)
    db.flush()
    return row
