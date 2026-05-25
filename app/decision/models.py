from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.conference.models import ConferenceRunResponse
from app.proposals.models import MarketProposal, ProposalRunResponse


class DecisionRunRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    max_proposals: int = Field(default=3, ge=1, le=10)
    max_notional: Decimal = Field(default=Decimal("1000"), gt=0)
    use_llm: bool = True
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: Decimal | None = None


class DecisionRunResponse(BaseModel):
    proposal_run: ProposalRunResponse
    selected_proposal: MarketProposal
    conference: ConferenceRunResponse
