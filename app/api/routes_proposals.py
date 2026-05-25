from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import audit_actor, get_app_settings
from app.brokers.factory import build_broker_provider
from app.core.config import Settings
from app.proposals.models import (
    CandidateScanItem,
    MarketProposal,
    ProposalConferenceItem,
    ProposalListItem,
    ProposalRunDetail,
    ProposalRunRequest,
    ProposalRunResponse,
)
from app.proposals.service import MarketProposalEngine
from app.storage.database import get_db
from app.storage.repositories import (
    get_proposal_run,
    create_audit_event,
    list_conferences_for_proposal,
    list_proposal_items,
    list_recent_proposals,
    save_proposal_run,
)
from app.storage.tables import RiskDecisionTable

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("", response_model=list[ProposalListItem])
def proposals(db: Session = Depends(get_db)) -> list[ProposalListItem]:
    return [
        ProposalListItem(
            proposal_run_id=row.id,
            created_at=row.created_at,
            candidate_count=row.candidate_count,
            proposal_count=row.proposal_count,
            used_llm=row.used_llm,
            llm_provider=row.llm_provider,
        )
        for row in list_recent_proposals(db)
    ]


@router.get("/{proposal_run_id}", response_model=ProposalRunDetail)
def proposal_detail(proposal_run_id: str, db: Session = Depends(get_db)) -> ProposalRunDetail:
    row = get_proposal_run(db, proposal_run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="proposal run not found")

    proposal_items = [_proposal_from_row(item) for item in list_proposal_items(db, proposal_run_id)]
    scanned = [CandidateScanItem.model_validate(item) for item in (row.scan_payload or [])]
    conferences = []
    for conference in list_conferences_for_proposal(db, proposal_run_id):
        risk = db.get(RiskDecisionTable, conference.risk_decision_id) if conference.risk_decision_id else None
        conferences.append(
            ProposalConferenceItem(
                conference_id=conference.id,
                symbol=conference.symbol,
                final_action=conference.final_action,  # type: ignore[arg-type]
                consensus_reached=conference.consensus_reached,
                risk_approved=risk.approved if risk else None,
                created_at=conference.created_at,
            )
        )

    return ProposalRunDetail(
        proposal_run_id=row.id,
        created_at=row.created_at,
        candidate_count=row.candidate_count,
        proposals=proposal_items,
        scanned=scanned,
        used_llm=row.used_llm,
        llm_provider=row.llm_provider,
        message=row.message,
        conferences=conferences,
    )


@router.post("/run", response_model=ProposalRunResponse)
async def run_proposals(
    request: ProposalRunRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ProposalRunResponse:
    provider = build_broker_provider(settings)
    engine = MarketProposalEngine(settings=settings, provider=provider)
    result = await engine.run(request)
    save_proposal_run(db, request=request, result=result)
    create_audit_event(
        db,
        actor=audit_actor(http_request),
        action="proposal.run",
        entity_type="proposal_run",
        entity_id=result.proposal_run_id,
        summary=f"生成 {len(result.proposals)} 个候选提案",
        payload={
            "candidate_count": result.candidate_count,
            "proposal_count": len(result.proposals),
            "used_llm": result.used_llm,
            "llm_provider": result.llm_provider,
            "symbols": [item.symbol for item in result.scanned],
        },
    )
    db.commit()
    return result


def _proposal_from_row(row) -> MarketProposal:
    if row.raw_payload:
        return MarketProposal.model_validate(row.raw_payload)
    return MarketProposal(
        symbol=row.symbol,
        asset_type=row.asset_type,
        proposed_action=row.proposed_action,
        confidence=row.confidence,
        thesis=row.thesis,
        risks=row.risks,
        suggested_max_notional=Decimal(row.suggested_max_notional),
        source=row.source,
        rank=row.rank,
        scan_score=row.scan_score,
        raw_payload={},
    )
