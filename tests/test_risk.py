from decimal import Decimal

from app.brokers.models import AccountSummary, Position
from app.core.config import Settings
from app.risk.models import RiskInput
from app.risk.service import RiskService


def _risk_input(**overrides):
    data = {
        "symbol": "AAPL",
        "action": "BUY",
        "trading_mode": "paper",
        "price": Decimal("100"),
        "requested_notional": Decimal("1000"),
        "requested_quantity": Decimal("10"),
        "suggested_stop_loss_pct": 0.05,
    }
    data.update(overrides)
    return RiskInput(**data)


def test_risk_rejects_when_live_disabled():
    settings = Settings(trading_mode="live", enable_live_trading=False)
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(trading_mode="live"),
        account=AccountSummary(account_id="acct", equity=Decimal("100000"), buying_power=Decimal("50000")),
        positions=[],
    )

    assert decision.approved is False
    assert any(check.name == "live_trading_enabled" and not check.passed for check in decision.checks)


def test_risk_rejects_position_limit():
    settings = Settings(max_position_pct=0.05)
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(requested_notional=Decimal("1000")),
        account=AccountSummary(account_id="acct", equity=Decimal("100000"), buying_power=Decimal("50000")),
        positions=[
            Position(
                symbol="AAPL",
                quantity=Decimal("45"),
                average_price=Decimal("100"),
                market_value=Decimal("4500"),
            )
        ],
    )

    assert decision.approved is False
    assert any(check.name == "position_limit" and not check.passed for check in decision.checks)


def test_risk_rejects_invalid_notional():
    settings = Settings()
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(requested_notional=Decimal("0"), requested_quantity=Decimal("0")),
        account=AccountSummary(account_id="acct", equity=Decimal("100000"), buying_power=Decimal("50000")),
        positions=[],
    )

    assert decision.approved is False
    assert any(
        check.name == "positive_price_quantity_notional" and not check.passed
        for check in decision.checks
    )


def test_risk_rejects_missing_account_equity():
    settings = Settings()
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(),
        account=None,
        positions=[],
    )

    assert decision.approved is False
    assert any(check.name == "account_equity_available" and not check.passed for check in decision.checks)


def test_risk_rejects_insufficient_buying_power():
    settings = Settings()
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(requested_notional=Decimal("1000")),
        account=AccountSummary(account_id="acct", equity=Decimal("100000"), buying_power=Decimal("500")),
        positions=[],
    )

    assert decision.approved is False
    assert any(check.name == "buying_power_available" and not check.passed for check in decision.checks)


def test_risk_rejects_sell_without_position():
    settings = Settings()
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(action="SELL", requested_quantity=Decimal("10")),
        account=AccountSummary(account_id="acct", equity=Decimal("100000"), buying_power=Decimal("50000")),
        positions=[
            Position(
                symbol="AAPL",
                quantity=Decimal("2"),
                average_price=Decimal("100"),
                market_value=Decimal("200"),
            )
        ],
    )

    assert decision.approved is False
    assert any(check.name == "sell_position_available" and not check.passed for check in decision.checks)


def test_risk_rejects_adverse_limit_price_deviation():
    settings = Settings(max_order_price_deviation_pct=0.05)
    decision = RiskService(settings).evaluate(
        db=None,
        risk_input=_risk_input(order_type="LIMIT", limit_price=Decimal("120")),
        account=AccountSummary(account_id="acct", equity=Decimal("100000"), buying_power=Decimal("50000")),
        positions=[],
    )

    assert decision.approved is False
    assert any(check.name == "limit_price_deviation" and not check.passed for check in decision.checks)
