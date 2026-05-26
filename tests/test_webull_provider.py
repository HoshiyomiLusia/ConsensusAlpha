from decimal import Decimal

from app.brokers.models import OrderIntent
from app.brokers.webull_provider import WebullProvider
from app.core.config import Settings


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeMarketData:
    def get_snapshot(self, symbols, category):
        return FakeResponse(
            {
                "data": [
                    {
                        "symbol": symbols[0],
                        "lastPrice": "101.25",
                        "open": "100",
                        "high": "102",
                        "low": "99",
                        "volume": 12345,
                    }
                ]
            }
        )


class FakeDataClient:
    market_data = FakeMarketData()


class FakeAccountV2:
    def get_account_list(self):
        return FakeResponse(
            {
                "data": [
                    {
                        "accountId": "acct-1",
                        "accountType": "MARGIN",
                        "status": "ACTIVE",
                        "currency": "USD",
                    }
                ]
            }
        )

    def get_account_balance(self, account_id):
        return FakeResponse({"data": {"account_id": account_id, "equity": "100000", "buyingPower": "50000"}})

    def get_account_position(self, account_id):
        return FakeResponse({"data": [{"symbol": "AAPL", "quantity": "2", "avgPrice": "100", "marketValue": "200"}]})


class FakeOrderV2:
    def preview_order(self, account_id, orders, client_combo_order_id):
        return FakeResponse({"data": {"ok": True, "client_order_id": client_combo_order_id}})

    def place_order(self, account_id, orders, client_combo_order_id):
        return FakeResponse({"data": {"orderId": "wb-123", "client_order_id": client_combo_order_id}})


class FakeTradeClient:
    account_v2 = FakeAccountV2()
    order_v2 = FakeOrderV2()


def _provider(enable_live=False):
    settings = Settings(
        broker_provider="webull",
        webull_app_key="key",
        webull_app_secret="secret",
        webull_account_id="acct-1",
        trading_mode="live" if enable_live else "paper",
        enable_live_trading=enable_live,
    )
    provider = WebullProvider(settings)
    provider._data_client = FakeDataClient()
    provider._trade_client = FakeTradeClient()
    return provider


def test_webull_provider_maps_snapshot_account_and_positions():
    provider = _provider()

    import asyncio

    snapshot = asyncio.run(provider.get_market_snapshot("AAPL"))
    account = asyncio.run(provider.get_account_summary())
    positions = asyncio.run(provider.get_positions())
    accounts = asyncio.run(provider.list_accounts())

    assert snapshot.price == Decimal("101.25")
    assert account.equity == Decimal("100000")
    assert positions[0].market_value == Decimal("200")
    assert accounts[0]["account_id"] == "acct-1"


def test_webull_provider_maps_preview_and_place_order():
    provider = _provider(enable_live=True)
    order = OrderIntent(
        client_order_id="client-1",
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("1"),
        notional=Decimal("101.25"),
    )

    import asyncio

    preview = asyncio.run(provider.preview_order(order))
    execution = asyncio.run(provider.place_order(order))

    assert preview.account_id == "acct-1"
    assert execution.order_id == "wb-123"
    assert execution.status == "ACCEPTED"
