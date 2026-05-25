from app.brokers.models import BrokerProviderError, OrderIntent
from app.core.config import Settings
from app.execution.models import ExecutionOrder


class LiveExecutor:
    def __init__(self, settings: Settings, provider):
        self.settings = settings
        self.provider = provider

    async def place(self, order: OrderIntent) -> ExecutionOrder:
        if not self.settings.enable_live_trading:
            raise BrokerProviderError("live trading is disabled", code="live_disabled")
        if self.settings.trading_mode != "live":
            raise BrokerProviderError("TRADING_MODE must be live", code="live_mode_required")
        return await self.provider.place_order(order)
