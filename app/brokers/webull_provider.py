import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.brokers.models import (
    AccountSummary,
    BrokerProviderError,
    OrderIntent,
    OrderPreview,
    Position,
    ProviderStatus,
)
from app.core.config import Settings
from app.core.logging import redact_payload
from app.core.time import utc_now
from app.execution.models import ExecutionOrder
from app.market_data.models import HistoricalBar, MarketSnapshot


_WEBULL_BAR_PERIODS = {
    "1m": "m1",
    "5m": "m5",
    "15m": "m15",
    "1h": "h1",
    "1d": "d1",
}

logger = logging.getLogger(__name__)


class WebullProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._data_client = None
        self._trade_client = None

    async def get_market_snapshot(self, symbol: str, asset_type: str = "equity") -> MarketSnapshot:
        self._ensure_stock_or_etf(asset_type)
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.data_client.market_data.get_snapshot(
                [symbol.upper()], self._webull_category(asset_type)
            ),
        )
        payload = self._response_payload(response)
        item = self._first_item(payload)
        price = self._decimal_from_keys(
            item,
            "last_price",
            "lastPrice",
            "price",
            "close",
            "pPrice",
            "trade_price",
        )
        if price is None or price <= 0:
            raise BrokerProviderError(
                "Webull snapshot did not include a positive price",
                code="missing_price",
                details={"symbol": symbol, "payload": redact_payload(payload)},
            )
        timestamp = self._timestamp_from_payload(item)
        return MarketSnapshot(
            symbol=symbol.upper(),
            asset_type=asset_type,  # type: ignore[arg-type]
            price=price,
            open=self._decimal_from_keys(item, "open", "openPrice"),
            high=self._decimal_from_keys(item, "high", "highPrice"),
            low=self._decimal_from_keys(item, "low", "lowPrice"),
            previous_close=self._decimal_from_keys(
                item, "previous_close", "previousClose", "preClose", "close"
            ),
            volume=self._int_from_keys(item, "volume", "tradeVolume"),
            timestamp=timestamp,
            source=f"webull:{self.settings.webull_env}",
            raw_payload=redact_payload(payload),
        )

    async def get_historical_bars(
        self,
        symbol: str,
        interval: str,
        lookback: int,
        asset_type: str = "equity",
    ) -> list[HistoricalBar]:
        self._ensure_stock_or_etf(asset_type)
        period = _WEBULL_BAR_PERIODS.get(interval)
        if period is None:
            raise BrokerProviderError(
                f"Unsupported bar interval: {interval}",
                code="unsupported_interval",
                details={"interval": interval},
            )
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.data_client.market_data.get_history_bar(
                [symbol.upper()],
                self._webull_category(asset_type),
                period,
                int(lookback),
            ),
        )
        payload = self._response_payload(response)
        items = self._items(payload)
        bars: list[HistoricalBar] = []
        for item in items:
            close = self._decimal_from_keys(item, "close", "closePrice")
            if close is None:
                continue
            timestamp = self._timestamp_from_payload(item)
            open_ = self._decimal_from_keys(item, "open", "openPrice") or close
            high = self._decimal_from_keys(item, "high", "highPrice") or close
            low = self._decimal_from_keys(item, "low", "lowPrice") or close
            volume = self._int_from_keys(item, "volume", "tradeVolume")
            bars.append(
                HistoricalBar(
                    timestamp=timestamp,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        bars.sort(key=lambda bar: bar.timestamp)
        return bars

    async def get_account_summary(self) -> AccountSummary:
        account_id = self._account_id()
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.trade_client.account_v2.get_account_balance(account_id),
        )
        payload = self._response_payload(response)
        item = self._first_item(payload)
        equity = self._decimal_from_keys(
            item,
            "equity",
            "net_liquidation",
            "netLiquidation",
            "total_asset",
            "totalAsset",
            "account_equity",
            "accountEquity",
        )
        if equity is None or equity <= 0:
            raise BrokerProviderError(
                "Webull account balance did not include positive equity",
                code="missing_equity",
                details={"payload": redact_payload(payload)},
            )
        return AccountSummary(
            account_id=account_id,
            equity=equity,
            buying_power=self._decimal_from_keys(item, "buying_power", "buyingPower"),
            cash=self._decimal_from_keys(item, "cash", "cashBalance", "settledCash"),
            currency=str(item.get("currency") or item.get("totalAssetCurrency") or "USD"),
            raw_payload=redact_payload(payload),
        )

    async def get_positions(self) -> list[Position]:
        account_id = self._account_id()
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.trade_client.account_v2.get_account_position(account_id),
        )
        payload = self._response_payload(response)
        items = self._items(payload)
        positions: list[Position] = []
        for item in items:
            symbol = str(item.get("symbol") or item.get("ticker") or item.get("code") or "").upper()
            quantity = self._decimal_from_keys(item, "quantity", "qty", "position", "positionQty")
            average_price = self._decimal_from_keys(item, "average_price", "avgPrice", "costPrice")
            market_value = self._decimal_from_keys(item, "market_value", "marketValue")
            if not symbol or quantity is None:
                continue
            if average_price is None:
                average_price = Decimal("0")
            if market_value is None:
                market_value = quantity * average_price
            positions.append(
                Position(
                    symbol=symbol,
                    asset_type="etf" if str(item.get("instrument_type", "")).upper() == "ETF" else "equity",
                    quantity=quantity,
                    average_price=average_price,
                    market_value=market_value,
                    side="SHORT" if quantity < 0 else "LONG",
                    raw_payload=redact_payload(item),
                )
            )
        return positions

    async def list_accounts(self) -> list[dict[str, Any]]:
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.trade_client.account_v2.get_account_list(),
        )
        payload = self._response_payload(response)
        accounts: list[dict[str, Any]] = []
        for item in self._items(payload):
            account_id = self._string_from_keys(
                item,
                "account_id",
                "accountId",
                "account_no",
                "accountNo",
                "account",
                "id",
                "brokerAccountId",
                "secAccountId",
            )
            if not account_id:
                continue
            label = self._string_from_keys(
                item,
                "account_name",
                "accountName",
                "nickname",
                "name",
                "accountType",
            )
            accounts.append(
                {
                    "account_id": account_id,
                    "label": label or account_id,
                    "account_type": self._string_from_keys(item, "account_type", "accountType", "type"),
                    "status": self._string_from_keys(item, "status", "accountStatus"),
                    "currency": self._string_from_keys(item, "currency", "baseCurrency"),
                    "raw_payload": redact_payload(item),
                }
            )
        return accounts

    async def preview_order(self, order: OrderIntent) -> OrderPreview:
        self._ensure_stock_or_etf(order.asset_type)
        new_orders = [self._to_webull_order(order)]
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.trade_client.order_v2.preview_order(
                self._account_id(), new_orders, order.client_order_id
            ),
        )
        payload = self._response_payload(response)
        return OrderPreview(
            client_order_id=order.client_order_id,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            estimated_notional=order.notional,
            account_id=self._account_id(),
            environment=self.settings.webull_env,
            created_at=utc_now(),
            raw_payload=redact_payload(payload),
        )

    async def place_order(self, order: OrderIntent) -> ExecutionOrder:
        self._ensure_stock_or_etf(order.asset_type)
        if not self.settings.live_ordering_enabled:
            raise BrokerProviderError("live trading is disabled", code="live_disabled")
        new_orders = [self._to_webull_order(order)]
        response = await asyncio.to_thread(
            self._sdk_call,
            lambda: self.trade_client.order_v2.place_order(
                self._account_id(), new_orders, order.client_order_id
            ),
        )
        payload = self._response_payload(response)
        item = self._first_item(payload)
        provider_order_id = (
            item.get("order_id")
            or item.get("orderId")
            or item.get("client_order_id")
            or item.get("clientOrderId")
            or order.client_order_id
        )
        return ExecutionOrder(
            order_id=str(provider_order_id),
            client_order_id=order.client_order_id,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            status="ACCEPTED",
            mode="live",
            created_at=utc_now(),
            raw_payload=redact_payload(payload),
        )

    async def status(self) -> ProviderStatus:
        try:
            if not self.settings.has_webull_credentials:
                return ProviderStatus(
                    provider="webull",
                    healthy=False,
                    environment=self.settings.webull_env,
                    trading_mode=self.settings.trading_mode,
                    account_id=self._masked_account(),
                    message="missing Webull app key or app secret",
                    details={"region": self.settings.webull_region},
                )
            await self.get_account_summary()
            return ProviderStatus(
                provider="webull",
                healthy=True,
                environment=self.settings.webull_env,
                trading_mode=self.settings.trading_mode,
                account_id=self._masked_account(),
                message="Webull provider reachable",
                details={"region": self.settings.webull_region},
            )
        except Exception as exc:  # pragma: no cover - defensive status path
            return ProviderStatus(
                provider="webull",
                healthy=False,
                environment=self.settings.webull_env,
                trading_mode=self.settings.trading_mode,
                account_id=self._masked_account(),
                message=str(exc),
                details={"region": self.settings.webull_region},
            )

    @property
    def data_client(self):
        if self._data_client is None:
            api_client = self._build_api_client(self.settings.webull_market_data_endpoint)
            from webull.data.data_client import DataClient

            self._data_client = DataClient(api_client)
        return self._data_client

    @property
    def trade_client(self):
        if self._trade_client is None:
            api_client = self._build_api_client(self.settings.webull_trading_endpoint)
            from webull.trade.trade_client import TradeClient

            self._trade_client = TradeClient(api_client)
        return self._trade_client

    def _build_api_client(self, endpoint: str):
        if not self.settings.has_webull_credentials:
            raise BrokerProviderError("missing Webull API credentials", code="missing_credentials")
        from webull.core.client import ApiClient

        api_client = ApiClient(
            app_key=self.settings.webull_app_key,
            app_secret=self.settings.webull_app_secret,
            region_id=self.settings.webull_region,
            auto_retry=True,
            max_retry_num=2,
        )
        # The SDK installs stdout/file handlers by default; mark these configured so app logging controls output.
        api_client._stream_logger_set = True
        api_client._file_logger_set = True
        api_client.add_endpoint(self.settings.webull_region, endpoint)
        return api_client

    @retry(wait=wait_exponential(multiplier=0.2, min=0.2, max=1.5), stop=stop_after_attempt(3), reraise=True)
    def _sdk_call(self, call: Callable[[], Any]) -> Any:
        try:
            response = call()
            status_code = getattr(response, "status_code", None)
            if status_code is not None and int(status_code) >= 400:
                raise BrokerProviderError(
                    f"Webull request failed with HTTP {status_code}",
                    code="webull_http_error",
                    details={"status_code": status_code},
                )
            return response
        except BrokerProviderError:
            raise
        except Exception as exc:
            message = str(exc)
            logger.warning("webull_provider_error code=%s message=%s", type(exc).__name__, message)
            if "UNAUTHORIZED" in message or "HTTP Status: 401" in message:
                raise BrokerProviderError(
                    "Webull 授权失败：App Key / App Secret 与当前环境、OpenAPI 权限或账户类型不匹配。",
                    code="webull_unauthorized",
                    details={
                        "http_status": 401,
                        "reason": "请确认这组密钥来自 Webull OpenAPI，测试/生产环境选择正确，并且应用已绑定可用账户。",
                    },
                ) from exc
            raise BrokerProviderError(
                "Webull SDK request failed",
                code=type(exc).__name__,
                details={"message": message},
            ) from exc

    def _response_payload(self, response: Any) -> dict | list:
        if response is None:
            return {}
        if isinstance(response, dict | list):
            return response
        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception as exc:
                raise BrokerProviderError(
                    "Webull response was not valid JSON",
                    code="invalid_json",
                    details={"message": str(exc)},
                ) from exc
        if hasattr(response, "text"):
            return {"text": str(response.text)}
        return {"value": str(response)}

    def _items(self, payload: dict | list) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        for key in ("data", "items", "positions", "accounts", "list", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = self._items(value)
                if nested:
                    return nested
        return [payload]

    def _first_item(self, payload: dict | list) -> dict:
        items = self._items(payload)
        return items[0] if items else {}

    @staticmethod
    def _decimal_from_keys(item: dict, *keys: str) -> Decimal | None:
        for key in keys:
            value = item.get(key)
            if value is None or value == "":
                continue
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                continue
        return None

    @staticmethod
    def _int_from_keys(item: dict, *keys: str) -> int | None:
        for key in keys:
            value = item.get(key)
            if value is None or value == "":
                continue
            try:
                return int(float(str(value)))
            except ValueError:
                continue
        return None

    @staticmethod
    def _string_from_keys(item: dict, *keys: str) -> str | None:
        for key in keys:
            value = item.get(key)
            if value is None or value == "":
                continue
            return str(value)
        return None

    @staticmethod
    def _timestamp_from_payload(item: dict) -> datetime:
        for key in ("timestamp", "time", "tradeTime", "quoteTime", "updatedAt"):
            value = item.get(key)
            if value is None:
                continue
            try:
                numeric = float(value)
                if numeric > 10_000_000_000:
                    numeric = numeric / 1000
                return datetime.fromtimestamp(numeric, tz=UTC)
            except (TypeError, ValueError, OSError):
                if isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        continue
        return utc_now()

    @staticmethod
    def _webull_category(asset_type: str):
        from webull.data.common.category import Category

        if asset_type == "etf":
            return Category.US_ETF
        return Category.US_STOCK

    @staticmethod
    def _ensure_stock_or_etf(asset_type: str) -> None:
        if asset_type not in {"equity", "etf"}:
            raise BrokerProviderError(
                "v1 Webull real API supports only US equities and ETFs",
                code="unsupported_asset_type",
                details={"asset_type": asset_type},
            )

    def _account_id(self) -> str:
        if not self.settings.webull_account_id:
            raise BrokerProviderError("WEBULL_ACCOUNT_ID is required", code="missing_account_id")
        return self.settings.webull_account_id

    def _masked_account(self) -> str | None:
        account_id = self.settings.webull_account_id
        if not account_id:
            return None
        if len(account_id) <= 8:
            return "***"
        return f"{account_id[:4]}...{account_id[-4:]}"

    def _to_webull_order(self, order: OrderIntent) -> dict:
        payload = {
            "client_order_id": order.client_order_id,
            "instrument_type": "EQUITY",
            "market": "US",
            "symbol": order.symbol.upper(),
            "side": order.side,
            "order_type": order.order_type,
            "quantity": str(order.quantity),
            "time_in_force": "DAY",
            "entrust_type": "QTY",
        }
        if order.limit_price is not None:
            payload["limit_price"] = str(order.limit_price)
        return payload
