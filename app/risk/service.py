from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, ROUND_DOWN
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.brokers.models import AccountSummary, Position
from app.core.config import Settings
from app.risk.models import RiskCheck, RiskDecision, RiskInput
from app.storage.tables import LiveOrderAttemptTable, LiveOrderPreviewTable, PaperOrderTable


class RiskService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(
        self,
        *,
        db: Session | None,
        risk_input: RiskInput,
        account: AccountSummary | None,
        positions: list[Position],
    ) -> RiskDecision:
        checks: list[RiskCheck] = []

        def add(name: str, passed: bool, reason: str, data: dict | None = None) -> None:
            checks.append(RiskCheck(name=name, passed=passed, reason=reason, data=data or {}))

        if risk_input.action == "HOLD":
            add("final_action", False, "final action is HOLD")
            return self._decision(False, "final action is HOLD", checks)
        add("final_action", True, "final action permits risk evaluation")

        if risk_input.trading_mode == "live":
            live_ok = self.settings.live_ordering_enabled
            add(
                "live_trading_enabled",
                live_ok,
                "live trading enabled" if live_ok else "live trading is disabled",
                {
                    "enable_live_trading": self.settings.enable_live_trading,
                    "trading_mode": self.settings.trading_mode,
                },
            )
            if self.settings.webull_env == "production":
                production_ready, production_reason, production_data = self._production_live_configuration()
                add(
                    "production_live_configuration",
                    production_ready,
                    production_reason,
                    production_data,
                )
                market_hours_ok, market_hours_reason, market_hours_data = self._regular_market_hours_open()
                add(
                    "regular_market_hours",
                    market_hours_ok,
                    market_hours_reason,
                    market_hours_data,
                )
        else:
            add("live_trading_enabled", True, "paper mode does not require live trading")

        valid_numbers = (
            risk_input.price > 0
            and risk_input.requested_quantity > 0
            and risk_input.requested_notional > 0
        )
        add(
            "positive_price_quantity_notional",
            valid_numbers,
            "price, quantity, and notional are positive"
            if valid_numbers
            else "price, quantity, and notional must be positive",
            {
                "price": str(risk_input.price),
                "quantity": str(risk_input.requested_quantity),
                "notional": str(risk_input.requested_notional),
            },
        )

        if risk_input.order_type == "LIMIT":
            limit_price = risk_input.limit_price
            valid_limit = limit_price is not None and limit_price > 0
            if valid_limit:
                adverse_deviation = self._adverse_limit_deviation(
                    risk_input.action,
                    risk_input.price,
                    limit_price,
                )
                max_deviation = Decimal(str(self.settings.max_order_price_deviation_pct))
                passed = adverse_deviation <= max_deviation
                reason = (
                    "limit price deviation passed"
                    if passed
                    else "limit price deviates too far from snapshot"
                )
                data = {
                    "snapshot_price": str(risk_input.price),
                    "limit_price": str(limit_price),
                    "adverse_deviation": str(adverse_deviation),
                    "max_order_price_deviation_pct": str(max_deviation),
                }
            else:
                passed = False
                reason = "limit price must be positive"
                data = {"limit_price": str(limit_price) if limit_price is not None else None}
            add("limit_price_deviation", passed, reason, data)
        else:
            add("limit_price_deviation", True, "market order does not require limit price")

        equity_available = account is not None and account.equity > 0
        add(
            "account_equity_available",
            equity_available,
            "account equity available" if equity_available else "account equity is unavailable",
            {"equity": str(account.equity) if account else None},
        )

        if risk_input.action == "BUY":
            available_funds = self._available_funds(account)
            funds_ok = available_funds is not None and available_funds >= risk_input.requested_notional
            add(
                "buying_power_available",
                funds_ok,
                "buying power available" if funds_ok else "buying power is insufficient",
                {
                    "available_funds": str(available_funds) if available_funds is not None else None,
                    "requested_notional": str(risk_input.requested_notional),
                },
            )
        else:
            add("buying_power_available", True, "sell order does not require buying power")

        if risk_input.action == "SELL":
            available_quantity = self._available_long_quantity(positions, risk_input.symbol)
            position_ok = available_quantity >= risk_input.requested_quantity
            add(
                "sell_position_available",
                position_ok,
                "sell quantity is covered by current position"
                if position_ok
                else "sell quantity exceeds current position",
                {
                    "available_quantity": str(available_quantity),
                    "requested_quantity": str(risk_input.requested_quantity),
                },
            )
        else:
            add("sell_position_available", True, "buy order does not require existing position")

        if equity_available:
            equity = account.equity
            current_notional = sum(
                abs(position.market_value)
                for position in positions
                if position.symbol.upper() == risk_input.symbol.upper()
            )
            max_position_notional = equity * Decimal(str(self.settings.max_position_pct))
            proposed_position = (
                current_notional + risk_input.requested_notional
                if risk_input.action == "BUY"
                else max(Decimal("0"), current_notional - risk_input.requested_notional)
            )
            add(
                "position_limit",
                proposed_position <= max_position_notional,
                "position limit passed"
                if proposed_position <= max_position_notional
                else "position limit exceeded",
                {
                    "current_symbol_notional": str(current_notional),
                    "proposed_symbol_notional": str(proposed_position),
                    "max_position_notional": str(max_position_notional),
                },
            )

            stop_loss_pct = Decimal(str(risk_input.suggested_stop_loss_pct or 1))
            estimated_trade_risk = risk_input.requested_notional * stop_loss_pct
            max_trade_risk = equity * Decimal(str(self.settings.max_single_trade_risk_pct))
            add(
                "single_trade_risk",
                estimated_trade_risk <= max_trade_risk,
                "single trade risk passed"
                if estimated_trade_risk <= max_trade_risk
                else "single trade risk exceeded",
                {
                    "estimated_trade_risk": str(estimated_trade_risk),
                    "max_trade_risk": str(max_trade_risk),
                    "stop_loss_pct": str(stop_loss_pct),
                },
            )

            daily_loss = self._current_daily_loss()
            max_daily_loss = equity * Decimal(str(self.settings.max_daily_loss_pct))
            add(
                "daily_loss_limit",
                daily_loss <= max_daily_loss,
                "daily loss limit passed"
                if daily_loss <= max_daily_loss
                else "daily loss limit exceeded",
                {"daily_loss": str(daily_loss), "max_daily_loss": str(max_daily_loss)},
            )

            max_quantity = (max_position_notional / risk_input.price).quantize(
                Decimal("0.0001"), rounding=ROUND_DOWN
            )
            max_notional = max_position_notional
        else:
            max_quantity = None
            max_notional = None

        if db is not None:
            cooldown_passed = not self._has_recent_opening_trade(db, risk_input.symbol)
            add(
                "cooldown",
                cooldown_passed,
                "cooldown passed" if cooldown_passed else "symbol is inside cooldown window",
                {
                    "symbol": risk_input.symbol.upper(),
                    "cooldown_seconds": self.settings.trade_cooldown_seconds,
                },
            )
            duplicate_pending = self._has_pending_live_preview(
                db,
                risk_input.symbol,
                risk_input.action,
            )
            add(
                "duplicate_pending_live_preview",
                not duplicate_pending,
                "no duplicate pending order preview"
                if not duplicate_pending
                else "duplicate pending order preview exists",
                {"symbol": risk_input.symbol.upper(), "action": risk_input.action},
            )
            if risk_input.trading_mode == "live":
                daily_count, daily_notional = self._daily_live_usage(db)
                daily_count_ok = daily_count < self.settings.max_daily_live_order_count
                add(
                    "daily_live_order_count",
                    daily_count_ok,
                    "daily live order count passed"
                    if daily_count_ok
                    else "daily live order count exceeded",
                    {
                        "current_count": daily_count,
                        "max_daily_live_order_count": self.settings.max_daily_live_order_count,
                    },
                )
                projected_notional = daily_notional + risk_input.requested_notional
                daily_notional_ok = projected_notional <= self.settings.max_daily_live_notional
                add(
                    "daily_live_notional",
                    daily_notional_ok,
                    "daily live notional passed"
                    if daily_notional_ok
                    else "daily live notional exceeded",
                    {
                        "current_notional": str(daily_notional),
                        "requested_notional": str(risk_input.requested_notional),
                        "projected_notional": str(projected_notional),
                        "max_daily_live_notional": str(self.settings.max_daily_live_notional),
                    },
                )
        else:
            add("cooldown", True, "cooldown skipped because no database session was provided")
            add(
                "duplicate_pending_live_preview",
                True,
                "duplicate preview check skipped because no database session was provided",
            )

        approved = all(check.passed for check in checks)
        reason = "approved" if approved else next(check.reason for check in checks if not check.passed)
        return self._decision(approved, reason, checks, max_quantity=max_quantity, max_notional=max_notional)

    def _decision(
        self,
        approved: bool,
        reason: str,
        checks: list[RiskCheck],
        *,
        max_quantity: Decimal | None = None,
        max_notional: Decimal | None = None,
    ) -> RiskDecision:
        return RiskDecision(
            approved=approved,
            reason=reason,
            checks=checks,
            max_quantity=max_quantity,
            max_notional=max_notional,
        )

    def _current_daily_loss(self) -> Decimal:
        return Decimal("0")

    def _production_live_configuration(self) -> tuple[bool, str, dict]:
        missing: list[str] = []
        if self.settings.broker_provider != "webull":
            missing.append("broker_provider must be webull")
        if not self.settings.has_webull_credentials:
            missing.append("webull credentials")
        if not self.settings.webull_account_id:
            missing.append("webull account id")
        if not self.settings.api_auth_required or not self.settings.api_auth_token:
            missing.append("api authentication")
        passed = not missing
        return (
            passed,
            "production live configuration passed"
            if passed
            else "production live configuration is incomplete",
            {
                "broker_provider": self.settings.broker_provider,
                "has_webull_credentials": self.settings.has_webull_credentials,
                "has_webull_account_id": bool(self.settings.webull_account_id),
                "api_auth_required": self.settings.api_auth_required,
                "has_api_auth_token": bool(self.settings.api_auth_token),
                "missing": missing,
            },
        )

    def _regular_market_hours_open(self) -> tuple[bool, str, dict]:
        if not self.settings.regular_trading_hours_only:
            return True, "regular market hours check disabled", {"regular_trading_hours_only": False}
        now = datetime.now(ZoneInfo("America/New_York"))
        market_open = time(9, 30)
        market_close = time(16, 0)
        is_weekday = now.weekday() < 5
        is_inside_hours = market_open <= now.time() <= market_close
        passed = is_weekday and is_inside_hours
        return (
            passed,
            "regular market hours passed" if passed else "outside regular market hours",
            {
                "now_new_york": now.isoformat(),
                "market_open": "09:30",
                "market_close": "16:00",
                "note": "Weekends and clock hours are checked; exchange holidays must be verified during broker UAT.",
            },
        )

    @staticmethod
    def _available_funds(account: AccountSummary | None) -> Decimal | None:
        if account is None:
            return None
        if account.buying_power is not None:
            return account.buying_power
        return account.cash

    @staticmethod
    def _available_long_quantity(positions: list[Position], symbol: str) -> Decimal:
        total = Decimal("0")
        for position in positions:
            if position.symbol.upper() != symbol.upper():
                continue
            if position.quantity > 0 and position.side != "SHORT":
                total += position.quantity
        return total

    @staticmethod
    def _adverse_limit_deviation(action: str, snapshot_price: Decimal, limit_price: Decimal) -> Decimal:
        if snapshot_price <= 0:
            return Decimal("1")
        if action == "BUY":
            return max(Decimal("0"), (limit_price - snapshot_price) / snapshot_price)
        if action == "SELL":
            return max(Decimal("0"), (snapshot_price - limit_price) / snapshot_price)
        return Decimal("0")

    def _has_recent_opening_trade(self, db: Session, symbol: str) -> bool:
        if self.settings.trade_cooldown_seconds <= 0:
            return False
        cutoff = datetime.now(UTC) - timedelta(seconds=self.settings.trade_cooldown_seconds)
        paper_stmt = (
            select(PaperOrderTable)
            .where(PaperOrderTable.symbol == symbol.upper())
            .where(PaperOrderTable.side == "BUY")
            .where(PaperOrderTable.status.in_(["ACCEPTED", "FILLED"]))
            .order_by(desc(PaperOrderTable.created_at))
            .limit(1)
        )
        paper_order = db.scalar(paper_stmt)
        if paper_order and self._as_aware(paper_order.created_at) >= cutoff:
            return True

        live_stmt = (
            select(LiveOrderAttemptTable)
            .join(LiveOrderPreviewTable, LiveOrderPreviewTable.id == LiveOrderAttemptTable.preview_id)
            .where(LiveOrderPreviewTable.symbol == symbol.upper())
            .where(LiveOrderPreviewTable.side == "BUY")
            .where(LiveOrderAttemptTable.status.in_(["ACCEPTED", "FILLED"]))
            .order_by(desc(LiveOrderAttemptTable.created_at))
            .limit(1)
        )
        live_attempt = db.scalar(live_stmt)
        return bool(live_attempt and self._as_aware(live_attempt.created_at) >= cutoff)

    @staticmethod
    def _has_pending_live_preview(db: Session, symbol: str, action: str) -> bool:
        stmt = (
            select(LiveOrderPreviewTable)
            .where(LiveOrderPreviewTable.symbol == symbol.upper())
            .where(LiveOrderPreviewTable.side == action)
            .where(LiveOrderPreviewTable.status == "PENDING_CONFIRMATION")
            .limit(1)
        )
        return db.scalar(stmt) is not None

    @staticmethod
    def _daily_live_usage(db: Session) -> tuple[int, Decimal]:
        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(LiveOrderAttemptTable, LiveOrderPreviewTable)
            .join(LiveOrderPreviewTable, LiveOrderPreviewTable.id == LiveOrderAttemptTable.preview_id)
            .where(LiveOrderAttemptTable.created_at >= cutoff)
            .where(LiveOrderPreviewTable.environment != "paper")
            .where(LiveOrderAttemptTable.status.in_(["ACCEPTED", "FILLED", "CONFIRMED"]))
        )
        rows = list(db.execute(stmt))
        total = Decimal("0")
        for _, preview in rows:
            if preview.estimated_notional:
                total += Decimal(preview.estimated_notional)
        return len(rows), total

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
