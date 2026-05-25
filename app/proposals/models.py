from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.market_data.models import AssetType, MarketSnapshot


ProposalAction = Literal["BUY", "SELL", "HOLD"]


class ProposalRunRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    max_proposals: int = Field(default=5, ge=1, le=10)
    max_notional: Decimal = Field(default=Decimal("1000"), gt=0)
    use_llm: bool = True


class CandidateScanItem(BaseModel):
    symbol: str
    asset_type: AssetType
    snapshot: MarketSnapshot
    change_pct: float
    intraday_range_pct: float
    volume: int | None = None
    score: float
    reasons: list[str] = Field(default_factory=list)


class MarketProposal(BaseModel):
    symbol: str
    asset_type: AssetType
    proposed_action: ProposalAction
    confidence: float = Field(ge=0, le=1)
    thesis: str
    risks: list[str] = Field(default_factory=list)
    suggested_max_notional: Decimal
    source: str = "rules"
    rank: int
    scan_score: float
    raw_payload: dict = Field(default_factory=dict)


class ProposalRunResponse(BaseModel):
    proposal_run_id: str
    created_at: datetime
    candidate_count: int
    proposals: list[MarketProposal]
    scanned: list[CandidateScanItem]
    used_llm: bool
    llm_provider: str
    message: str


class ProposalConferenceItem(BaseModel):
    conference_id: str
    symbol: str
    final_action: ProposalAction
    consensus_reached: bool
    risk_approved: bool | None = None
    created_at: datetime


class ProposalRunDetail(ProposalRunResponse):
    conferences: list[ProposalConferenceItem] = Field(default_factory=list)


class ProposalListItem(BaseModel):
    proposal_run_id: str
    created_at: datetime
    candidate_count: int
    proposal_count: int
    used_llm: bool
    llm_provider: str
