from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RiskCheck(BaseModel):
    name: str
    passed: bool
    reason: str
    data: dict = Field(default_factory=dict)


class RiskDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approved: bool
    reason: str
    checks: list[RiskCheck]
    max_quantity: Decimal | None = None
    max_notional: Decimal | None = None


class RiskInput(BaseModel):
    symbol: str
    action: str
    trading_mode: str
    price: Decimal
    requested_notional: Decimal
    requested_quantity: Decimal
    order_type: str = "MARKET"
    limit_price: Decimal | None = None
    suggested_stop_loss_pct: float | None = None
