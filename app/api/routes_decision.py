from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.llm_provider import build_llm_provider
from app.api.dependencies import audit_actor, get_app_settings
from app.brokers.factory import build_broker_provider
from app.conference.models import ConferenceRunRequest
from app.conference.orchestrator import ConferenceOrchestrator
from app.core.config import Settings
from app.decision.models import DecisionRunRequest, DecisionRunResponse
from app.decision.service import build_decision_plan, choose_plan_proposal, review_portfolio
from app.proposals.models import ProposalRunRequest
from app.proposals.service import MarketProposalEngine
from app.storage.database import get_db
from app.storage.repositories import create_audit_event, save_proposal_run

router = APIRouter(prefix="/decision", tags=["decision"])


@router.post("/run", response_model=DecisionRunResponse)
async def run_decision(
    request: DecisionRunRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DecisionRunResponse:
    provider = build_broker_provider(settings)
    proposal_request = ProposalRunRequest(
        symbols=request.symbols,
        max_proposals=request.max_proposals,
        max_notional=request.max_notional,
        use_llm=request.use_llm,
    )
    proposal_result = await MarketProposalEngine(settings=settings, provider=provider).run(proposal_request)
    if not proposal_result.proposals:
        raise HTTPException(status_code=422, detail="no proposal generated")

    portfolio_review = await review_portfolio(
        db=db,
        settings=settings,
        provider=provider,
        max_notional=request.max_notional,
    )

    save_proposal_run(db, request=proposal_request, result=proposal_result)
    create_audit_event(
        db,
        actor=audit_actor(http_request),
        action="proposal.run",
        entity_type="proposal_run",
        entity_id=proposal_result.proposal_run_id,
        summary=f"一键决策生成 {len(proposal_result.proposals)} 个候选提案",
        payload={
            "candidate_count": proposal_result.candidate_count,
            "proposal_count": len(proposal_result.proposals),
            "used_llm": proposal_result.used_llm,
            "llm_provider": proposal_result.llm_provider,
            "symbols": [item.symbol for item in proposal_result.scanned],
            "source": "decision.run",
        },
    )
    db.commit()

    selected, selected_intent = choose_plan_proposal(
        portfolio_reviews=portfolio_review,
        opportunity_proposals=proposal_result.proposals,
    )
    selected_notional = selected.suggested_max_notional or request.max_notional
    if selected_notional <= 0:
        selected_notional = request.max_notional
    conference_request = ConferenceRunRequest(
        symbol=selected.symbol,
        asset_type=selected.asset_type,
        max_notional=selected_notional,
        order_type=request.order_type,
        limit_price=request.limit_price,
        mock_agent_action=selected.proposed_action,
        proposal_run_id=proposal_result.proposal_run_id,
    )
    conference_result = await ConferenceOrchestrator(
        settings=settings,
        provider=provider,
        llm_provider=build_llm_provider(settings),
    ).run(db=db, request=conference_request)

    create_audit_event(
        db,
        actor=audit_actor(http_request),
        action="conference.run",
        entity_type="conference",
        entity_id=conference_result.conference_id,
        summary=f"{conference_result.symbol} 一键会议完成，结果为 {conference_result.final_action}",
        payload={
            "symbol": conference_result.symbol,
            "final_action": conference_result.final_action,
            "consensus_reached": conference_result.consensus_reached,
            "risk_approved": conference_result.risk_approved,
            "order_id": conference_result.order_id,
            "live_preview_id": conference_result.live_preview_id,
            "proposal_run_id": proposal_result.proposal_run_id,
            "source": "decision.run",
        },
    )
    decision_plan = build_decision_plan(
        portfolio_reviews=portfolio_review,
        opportunity_proposals=proposal_result.proposals,
        selected=selected,
        selected_intent=selected_intent,
        conference=conference_result,
    )
    create_audit_event(
        db,
        actor=audit_actor(http_request),
        action="decision.run",
        entity_type="decision",
        entity_id=decision_plan.plan_id,
        summary=f"组合决策完成：{decision_plan.summary}",
        payload={
            "proposal_run_id": proposal_result.proposal_run_id,
            "plan_id": decision_plan.plan_id,
            "portfolio_review_count": len(portfolio_review),
            "opportunity_count": len(proposal_result.proposals),
            "selected_source": decision_plan.selected_source,
            "selected_symbol": selected.symbol,
            "selected_action": selected.proposed_action,
            "conference_id": conference_result.conference_id,
            "order_id": conference_result.order_id,
            "live_preview_id": conference_result.live_preview_id,
            "next_step": decision_plan.next_step,
        },
    )
    db.commit()
    return DecisionRunResponse(
        proposal_run=proposal_result,
        portfolio_review=portfolio_review,
        decision_plan=decision_plan,
        selected_proposal=selected,
        conference=conference_result,
    )
