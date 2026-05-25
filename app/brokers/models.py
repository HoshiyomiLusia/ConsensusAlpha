from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]


class AccountSummary(BaseModel):
    account_id: str
    equity: Decimal
    buying_power: Decimal | None = None
    cash: Decimal | None = None
    currency: str = "USD"
    raw_payload: dict = Field(default_factory=dict)


class Position(BaseModel):
    symbol: str
    asset_type: Literal["equity", "etf"] = "equity"
    quantity: Decimal
    average_price: Decimal
    market_value: Decimal
    side: Literal["LONG", "SHORT"] = "LONG"
    raw_payload: dict = Field(default_factory=dict)


class OrderIntent(BaseModel):
    client_order_id: str
    symbol: str
    asset_type: Literal["equity", "etf"] = "equity"
    side: OrderSide
    quantity: Decimal
    order_type: OrderType = "MARKET"
    limit_price: Decimal | None = None
    notional: Decimal | None = None


class OrderPreview(BaseModel):
    preview_id: str | None = None
    client_order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType
    limit_price: Decimal | None = None
    estimated_notional: Decimal | None = None
    account_id: str
    environment: str
    created_at: datetime
    raw_payload: dict = Field(default_factory=dict)


class ProviderStatus(BaseModel):
    provider: Literal["mock", "webull"]
    healthy: bool
    environment: str
    trading_mode: str
    account_id: str | None = None
    message: str
    details: dict = Field(default_factory=dict)


class BrokerProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
