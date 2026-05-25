from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AssetType = Literal["equity", "etf", "option", "crypto", "future"]

BarInterval = Literal["1m", "5m", "15m", "1h", "1d"]


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


class TimeframeFeatures(BaseModel):
    interval: str
    bar_count: int
    last_close: Decimal | None = None
    sma_short: Decimal | None = None
    sma_long: Decimal | None = None
    ema_fast: Decimal | None = None
    ema_slow: Decimal | None = None
    rsi_14: float | None = None
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None
    bb_upper: Decimal | None = None
    bb_lower: Decimal | None = None
    bb_position: float | None = None
    atr_14: Decimal | None = None
    vwap: Decimal | None = None
    momentum_5: float | None = None
    momentum_20: float | None = None
    realized_volatility: float | None = None
    trend: Literal["up", "down", "range", "unknown"] = "unknown"

    def summary(self) -> dict:
        return {k: v for k, v in self.model_dump(mode="json").items() if v is not None and v != "unknown"}


class LiquidityProfile(BaseModel):
    average_daily_volume: int | None = None
    average_dollar_volume: Decimal | None = None
    relative_volume: float | None = None
    spread_estimate_bps: float | None = None


class MarketContext(BaseModel):
    snapshot: MarketSnapshot
    timeframes: dict[str, TimeframeFeatures] = Field(default_factory=dict)
    liquidity: LiquidityProfile | None = None
    relative_strength: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @property
    def symbol(self) -> str:
        return self.snapshot.symbol

    @property
    def price(self) -> Decimal:
        return self.snapshot.price

    @property
    def primary_timeframe(self) -> TimeframeFeatures | None:
        for interval in ("1d", "1h", "15m", "5m", "1m"):
            features = self.timeframes.get(interval)
            if features is not None and features.bar_count > 0:
                return features
        return None

    def to_prompt_dict(self) -> dict:
        """Compact, non-null view for LLM prompts."""
        return {
            "symbol": self.symbol,
            "snapshot": self.snapshot.model_dump(mode="json"),
            "timeframes": {interval: tf.summary() for interval, tf in self.timeframes.items()},
            "liquidity": self.liquidity.model_dump(mode="json", exclude_none=True) if self.liquidity else {},
            "relative_strength": self.relative_strength,
            "notes": self.notes,
        }

    @classmethod
    def from_snapshot(cls, snapshot: MarketSnapshot, *, notes: list[str] | None = None) -> "MarketContext":
        return cls(snapshot=snapshot, notes=notes or [])
