from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.core.time import utc_now
from app.main import app
from app.storage.database import SessionLocal
from app.storage.tables import LiveOrderPreviewTable


def test_run_conference_api_returns_hold_with_mock_agents():
    with TestClient(app) as client:
        response = client.post(
            "/conference/run",
            json={"symbol": "AAPL", "asset_type": "equity", "max_notional": "1000"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["final_action"] == "HOLD"
        assert data["consensus_reached"] is False
        assert data["risk_approved"] is False

        detail = client.get(f"/conference/{data['conference_id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["snapshot"]["symbol"] == "AAPL"
        assert body["model_usage"]["total_tokens"] > 0
        assert len(body["model_usage"]["events"]) == 6
        assert body["opinions"][0]["prompt_version"] == "2026-05-25-v1"


def test_run_conference_api_creates_paper_order_with_unanimous_mock_buy():
    symbol = f"T{uuid4().hex[:5]}".upper()
    app.dependency_overrides[get_app_settings] = lambda: Settings(trade_cooldown_seconds=0)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "BUY",
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["final_action"] == "BUY"
            assert data["risk_approved"] is True
            assert data["order_id"] is not None

            orders = client.get("/orders/paper")
            assert orders.status_code == 200
            assert any(order["order_id"] == data["order_id"] for order in orders.json())

            positions = client.get("/portfolio/positions")
            assert positions.status_code == 200
            assert any(position["symbol"] == symbol for position in positions.json())
    finally:
        app.dependency_overrides.clear()


def test_live_preview_created_and_confirmation_guardrails_block_when_disabled():
    symbol = f"L{uuid4().hex[:5]}".upper()
    live_enabled = Settings(
        trading_mode="live",
        enable_live_trading=True,
        trade_cooldown_seconds=0,
    )
    app.dependency_overrides[get_app_settings] = lambda: live_enabled
    try:
        with TestClient(app) as client:
            response = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "BUY",
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["live_preview_id"] is not None
            assert data["order_id"] is None

            previews = client.get("/orders/live/previews")
            assert previews.status_code == 200
            assert any(preview["preview_id"] == data["live_preview_id"] for preview in previews.json())

            app.dependency_overrides[get_app_settings] = lambda: Settings(
                trading_mode="live",
                enable_live_trading=False,
                trade_cooldown_seconds=0,
            )
            confirm = client.post(
                f"/orders/live/{data['live_preview_id']}/confirm",
                json={"acknowledge_live_risk": True},
            )
            assert confirm.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_sell_without_position_is_blocked_by_risk_gate():
    symbol = f"S{uuid4().hex[:5]}".upper()
    app.dependency_overrides[get_app_settings] = lambda: Settings(trade_cooldown_seconds=0)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "SELL",
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["final_action"] == "SELL"
            assert data["risk_approved"] is False
            assert data["order_id"] is None

            detail = client.get(f"/conference/{data['conference_id']}")
            checks = detail.json()["risk_decision"]["checks"]
            assert any(check["name"] == "sell_position_available" and not check["passed"] for check in checks)
    finally:
        app.dependency_overrides.clear()


def test_duplicate_pending_live_preview_is_blocked():
    symbol = f"D{uuid4().hex[:5]}".upper()
    live_enabled = Settings(
        trading_mode="live",
        enable_live_trading=True,
        trade_cooldown_seconds=0,
    )
    app.dependency_overrides[get_app_settings] = lambda: live_enabled
    try:
        with TestClient(app) as client:
            first = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "BUY",
                },
            )
            assert first.status_code == 200, first.text
            assert first.json()["live_preview_id"] is not None

            second = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "BUY",
                },
            )
            assert second.status_code == 200, second.text
            assert second.json()["risk_approved"] is False
            assert second.json()["live_preview_id"] is None

            detail = client.get(f"/conference/{second.json()['conference_id']}")
            checks = detail.json()["risk_decision"]["checks"]
            assert any(
                check["name"] == "duplicate_pending_live_preview" and not check["passed"]
                for check in checks
            )
    finally:
        app.dependency_overrides.clear()


def test_expired_live_preview_cannot_be_confirmed():
    symbol = f"E{uuid4().hex[:5]}".upper()
    live_enabled = Settings(
        trading_mode="live",
        enable_live_trading=True,
        trade_cooldown_seconds=0,
        live_preview_ttl_seconds=1,
    )
    app.dependency_overrides[get_app_settings] = lambda: live_enabled
    try:
        with TestClient(app) as client:
            response = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "BUY",
                },
            )
            assert response.status_code == 200, response.text
            preview_id = response.json()["live_preview_id"]
            assert preview_id is not None

            with SessionLocal() as db:
                row = db.get(LiveOrderPreviewTable, preview_id)
                assert row is not None
                row.created_at = utc_now() - timedelta(seconds=10)
                db.commit()

            confirm = client.post(
                f"/orders/live/{preview_id}/confirm",
                json={"acknowledge_live_risk": True},
            )
            assert confirm.status_code == 409
            assert confirm.json()["detail"] == "live preview expired"
    finally:
        app.dependency_overrides.clear()
