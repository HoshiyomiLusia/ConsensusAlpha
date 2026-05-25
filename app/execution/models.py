from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExecutionOrder(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    client_order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: Decimal | None = None
    status: Literal["PENDING", "ACCEPTED", "FILLED", "REJECTED", "CANCELLED"]
    mode: Literal["paper", "live"]
    created_at: datetime
    raw_payload: dict = Field(default_factory=dict)


class PaperFill(BaseModel):
    fill_id: str
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    price: Decimal
    filled_at: datetime


class LiveOrderPreviewRecord(BaseModel):
    preview_id: str
    client_order_id: str
    conference_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: Decimal | None = None
    estimated_notional: Decimal | None = None
    status: Literal["PENDING_CONFIRMATION", "CONFIRMED", "REJECTED", "EXPIRED", "FAILED"]
    account_id: str
    environment: str
    created_at: datetime
    confirmed_at: datetime | None = None
    preview_payload: dict = Field(default_factory=dict)
