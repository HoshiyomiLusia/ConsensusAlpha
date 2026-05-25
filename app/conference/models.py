from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.market_data.models import AssetType, MarketSnapshot
from app.risk.models import RiskDecision


Action = Literal["BUY", "SELL", "HOLD"]


class AgentOpinion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    role: str
    symbol: str
    action: Action
    confidence: float = Field(ge=0, le=1)
    thesis: str
    concerns: list[str] = Field(default_factory=list)
    blocking_concerns: list[str] = Field(default_factory=list)
    suggested_max_position_pct: float | None = None
    suggested_stop_loss_pct: float | None = None
    prompt_version: str | None = None
    raw_payload: dict = Field(default_factory=dict)


class ConferenceResult(BaseModel):
    conference_id: str
    symbol: str
    started_at: datetime
    completed_at: datetime
    opinions: list[AgentOpinion]
    final_action: Action
    consensus_reached: bool
    consensus_reason: str
    chairperson_summary: str = ""


class ConferenceRunRequest(BaseModel):
    symbol: str
    asset_type: AssetType = "equity"
    max_notional: Decimal = Field(default=Decimal("1000"), gt=0)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: Decimal | None = None
    mock_agent_action: Action | None = None
    proposal_run_id: str | None = None


class ConferenceRunResponse(BaseModel):
    conference_id: str
    symbol: str
    final_action: Action
    consensus_reached: bool
    risk_approved: bool
    order_id: str | None = None
    live_preview_id: str | None = None


class ConferenceListItem(BaseModel):
    conference_id: str
    symbol: str
    final_action: Action
    consensus_reached: bool
    risk_approved: bool | None = None
    order_id: str | None = None
    live_preview_id: str | None = None
    created_at: datetime


class ModelUsageEvent(BaseModel):
    role: str
    operation: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated: bool = False
    prompt_version: str | None = None


class ModelUsageSummary(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False
    events: list[ModelUsageEvent] = Field(default_factory=list)


class ConferenceDetail(BaseModel):
    conference_id: str
    symbol: str
    snapshot: MarketSnapshot | None = None
    opinions: list[AgentOpinion]
    chairperson_summary: str
    consensus_result: ConferenceResult
    risk_decision: RiskDecision | None = None
    model_usage: ModelUsageSummary | None = None
    order_result: dict | None = None
    live_preview: dict | None = None
