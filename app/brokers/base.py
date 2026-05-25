from typing import Protocol

from app.brokers.models import AccountSummary, OrderIntent, OrderPreview, Position, ProviderStatus
from app.execution.models import ExecutionOrder
from app.market_data.models import HistoricalBar, MarketSnapshot


class BrokerProvider(Protocol):
    async def get_market_snapshot(self, symbol: str, asset_type: str = "equity") -> MarketSnapshot: ...

    async def get_historical_bars(
        self,
        symbol: str,
        interval: str,
        lookback: int,
        asset_type: str = "equity",
    ) -> list[HistoricalBar]: ...

    async def get_account_summary(self) -> AccountSummary: ...

    async def get_positions(self) -> list[Position]: ...

    async def preview_order(self, order: OrderIntent) -> OrderPreview: ...

    async def place_order(self, order: OrderIntent) -> ExecutionOrder: ...

    async def status(self) -> ProviderStatus: ...
