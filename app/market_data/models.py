from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AssetType = Literal["equity", "etf", "option", "crypto", "future"]


class MarketSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    asset_type: AssetType = "equity"
    price: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    previous_close: Decimal | None = None
    volume: int | None = None
    timestamp: datetime
    source: str
    raw_payload: dict = Field(default_factory=dict)


class HistoricalBar(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None = None
