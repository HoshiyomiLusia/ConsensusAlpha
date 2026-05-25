import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.brokers.models import AccountSummary, OrderIntent, OrderPreview, Position, ProviderStatus
from app.core.time import utc_now
from app.execution.models import ExecutionOrder
from app.market_data.models import HistoricalBar, MarketSnapshot


_INTERVAL_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86_400,
}


class MockBrokerProvider:
    def __init__(self, account_id: str = "mock-account"):
        self.account_id = account_id

    async def get_market_snapshot(self, symbol: str, asset_type: str = "equity") -> MarketSnapshot:
        base_price = self._base_price(symbol)
        symbol = symbol.upper()

        return MarketSnapshot(
            symbol=symbol,
            asset_type=asset_type,  # type: ignore[arg-type]
            price=base_price,
            open=base_price - Decimal("1.00"),
            high=base_price + Decimal("2.00"),
            low=base_price - Decimal("2.00"),
            previous_close=base_price - Decimal("0.50"),
            volume=1_000_000,
            timestamp=datetime.now(UTC),
            source="mock",
            raw_payload={"provider": "mock", "symbol": symbol},
        )

    async def get_historical_bars(
        self,
        symbol: str,
        interval: str,
        lookback: int,
        asset_type: str = "equity",
    ) -> list[HistoricalBar]:
        symbol = symbol.upper()
        if interval not in _INTERVAL_TO_SECONDS:
            return []
        step = _INTERVAL_TO_SECONDS[interval]
        base_price = self._base_price(symbol)
        # Deterministic synthetic series: gentle drift + sinusoidal cycle + symbol-tied seed
        seed = sum(ord(c) for c in symbol) or 1
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        bars: list[HistoricalBar] = []
        for i in range(lookback):
            idx = lookback - i
            ts = now - timedelta(seconds=step * idx)
            drift = (i - lookback / 2) / max(lookback, 1) * 0.04  # +/-2% gentle drift
            cycle = math.sin((i + seed) / 8.0) * 0.015
            noise = math.sin((i * seed) / 5.0) * 0.004
            multiplier = Decimal(str(1 + drift + cycle + noise))
            close = (base_price * multiplier).quantize(Decimal("0.01"))
            open_ = (close * Decimal(str(1 - noise * 0.3))).quantize(Decimal("0.01"))
            high = max(open_, close) + Decimal("0.30")
            low = min(open_, close) - Decimal("0.30")
            volume = int(900_000 + (seed * 137 + i * 17) % 250_000)
            bars.append(
                HistoricalBar(
                    timestamp=ts,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        return bars

    @staticmethod
    def _base_price(symbol: str) -> Decimal:
        symbol = symbol.upper()
        if symbol == "AAPL":
            return Decimal("195.25")
        if symbol == "MSFT":
            return Decimal("420.50")
        if symbol == "SPY":
            return Decimal("525.00")
        if symbol == "NVDA":
            return Decimal("950.00")
        if symbol == "TSLA":
            return Decimal("245.00")
        if symbol == "QQQ":
            return Decimal("495.00")
        return Decimal("100")

    async def get_account_summary(self) -> AccountSummary:
        return AccountSummary(
            account_id=self.account_id,
            equity=Decimal("100000"),
            buying_power=Decimal("50000"),
            cash=Decimal("50000"),
            currency="USD",
            raw_payload={"provider": "mock"},
        )

    async def get_positions(self) -> list[Position]:
        return [
            Position(
                symbol="SPY",
                asset_type="etf",
                quantity=Decimal("3"),
                average_price=Decimal("500"),
                market_value=Decimal("1500"),
                raw_payload={"provider": "mock"},
            )
        ]

    async def preview_order(self, order: OrderIntent) -> OrderPreview:
        estimated = order.notional
        return OrderPreview(
            client_order_id=order.client_order_id,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            estimated_notional=estimated,
            account_id=self.account_id,
            environment="mock",
            created_at=utc_now(),
            raw_payload={"provider": "mock", "order": order.model_dump(mode="json")},
        )

    async def place_order(self, order: OrderIntent) -> ExecutionOrder:
        return ExecutionOrder(
            order_id=f"mock-live-{order.client_order_id}",
            client_order_id=order.client_order_id,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            status="ACCEPTED",
            mode="live",
            created_at=utc_now(),
            raw_payload={"provider": "mock", "order": order.model_dump(mode="json")},
        )

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider="mock",
            healthy=True,
            environment="mock",
            trading_mode="paper",
            account_id=self.account_id,
            message="mock provider ready",
        )
