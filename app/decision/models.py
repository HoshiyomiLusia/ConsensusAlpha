from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.conference.models import ConferenceRunResponse
from app.proposals.models import MarketProposal, ProposalRunResponse


PortfolioReviewAction = Literal["KEEP", "ADD", "REDUCE", "EXIT", "STOP_LOSS", "TAKE_PROFIT"]
PlanSource = Literal["portfolio_review", "opportunity_scan"]


class DecisionRunRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    max_proposals: int = Field(default=5, ge=1, le=10)
    max_notional: Decimal = Field(default=Decimal("1000"), gt=0)
    use_llm: bool = True
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: Decimal | None = None


class PortfolioReviewItem(BaseModel):
    symbol: str
    asset_type: Literal["equity", "etf"]
    quantity: Decimal
    average_price: Decimal
    market_value: Decimal
    last_price: Decimal
    unrealized_pnl_pct: Decimal
    review_action: PortfolioReviewAction
    proposed_action: Literal["BUY", "SELL", "HOLD"]
    priority_score: float
    thesis: str
    risk_notes: list[str] = Field(default_factory=list)
    suggested_max_notional: Decimal


class DecisionPlanItem(BaseModel):
    source: PlanSource
    symbol: str
    asset_type: Literal["equity", "etf"]
    intent: str
    proposed_action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    priority_score: float
    thesis: str
    suggested_max_notional: Decimal
    conference_id: str | None = None
    final_action: Literal["BUY", "SELL", "HOLD"] | None = None
    risk_approved: bool | None = None
    order_id: str | None = None
    live_preview_id: str | None = None


class DecisionPlan(BaseModel):
    plan_id: str
    summary: str
    next_step: str
    selected_source: PlanSource
    selected_symbol: str
    selected_intent: str
    final_action: Literal["BUY", "SELL", "HOLD"]
    order_required: bool
    risk_approved: bool
    order_id: str | None = None
    live_preview_id: str | None = None
    portfolio_review_count: int
    opportunity_count: int
    items: list[DecisionPlanItem]


class DecisionRunResponse(BaseModel):
    proposal_run: ProposalRunResponse
    portfolio_review: list[PortfolioReviewItem] = Field(default_factory=list)
    decision_plan: DecisionPlan
    selected_proposal: MarketProposal
    conference: ConferenceRunResponse
