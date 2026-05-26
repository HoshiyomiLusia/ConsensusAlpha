from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.main import app


def test_reset_paper_state_is_blocked_in_production():
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        app_env="production",
        api_auth_token="test-token",
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/test/paper/reset",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_reset_paper_state_clears_mock_orders_and_positions():
    symbol = f"R{uuid4().hex[:5]}".upper()
    app.dependency_overrides[get_app_settings] = lambda: Settings(app_env="uat", trade_cooldown_seconds=0)
    try:
        with TestClient(app) as client:
            created = client.post(
                "/conference/run",
                json={
                    "symbol": symbol,
                    "asset_type": "equity",
                    "max_notional": "1000",
                    "mock_agent_action": "BUY",
                },
            )
            assert created.status_code == 200, created.text
            assert created.json()["live_preview_id"] is not None

            confirm = client.post(
                f"/orders/previews/{created.json()['live_preview_id']}/confirm",
                json={"acknowledge_live_risk": True},
            )
            assert confirm.status_code == 200, confirm.text

            reset = client.post("/test/paper/reset")
            assert reset.status_code == 200, reset.text
            body = reset.json()
            assert body["deleted"]["paper_orders"] >= 1
            assert body["deleted"]["paper_positions"] >= 1
            assert body["deleted"]["paper_previews"] >= 1

            orders = client.get("/orders/paper")
            positions = client.get("/portfolio/positions")
            previews = client.get("/orders/previews")
            assert orders.status_code == 200
            assert positions.status_code == 200
            assert previews.status_code == 200
            assert orders.json() == []
            assert positions.json() == []
            assert [preview for preview in previews.json() if preview["mode"] == "paper"] == []
    finally:
        app.dependency_overrides.clear()
