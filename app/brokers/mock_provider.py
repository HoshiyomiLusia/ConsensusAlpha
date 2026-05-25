from datetime import UTC, datetime
from decimal import Decimal

from app.brokers.models import AccountSummary, OrderIntent, OrderPreview, Position, ProviderStatus
from app.core.time import utc_now
from app.execution.models import ExecutionOrder
from app.market_data.models import MarketSnapshot


class MockBrokerProvider:
    def __init__(self, account_id: str = "mock-account"):
        self.account_id = account_id

    async def get_market_snapshot(self, symbol: str, asset_type: str = "equity") -> MarketSnapshot:
        base_price = Decimal("100")
        symbol = symbol.upper()
        if symbol == "AAPL":
            base_price = Decimal("195.25")
        elif symbol == "MSFT":
            base_price = Decimal("420.50")
        elif symbol == "SPY":
            base_price = Decimal("525.00")

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
