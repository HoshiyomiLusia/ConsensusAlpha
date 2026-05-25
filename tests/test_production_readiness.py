from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.main import app
from app.storage.database import SessionLocal
from app.storage.tables import LiveOrderPreviewTable


def test_production_readiness_reports_blockers_without_real_config():
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        app_env="production",
        api_auth_token="secret-token",
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                "/production/readiness",
                headers={"Authorization": "Bearer secret-token"},
            )

            assert response.status_code == 200, response.text
            data = response.json()
            assert data["ready"] is False
            failed = {check["name"] for check in data["checks"] if not check["passed"]}
            assert "database_is_postgres" in failed
            assert "broker_is_webull" in failed
            assert "webull_credentials" in failed
            assert "real_llm_quorum" in failed
    finally:
        app.dependency_overrides.clear()


def test_production_confirmation_requires_matching_visible_details():
    preview_id = f"preview_{uuid4().hex}"
    with SessionLocal() as db:
        db.add(
            LiveOrderPreviewTable(
                id=preview_id,
                client_order_id=f"client_{uuid4().hex}",
                conference_id=None,
                risk_decision_id=None,
                symbol="AAPL",
                side="BUY",
                quantity="1.0000",
                order_type="MARKET",
                limit_price=None,
                estimated_notional="100",
                status="PENDING_CONFIRMATION",
                account_id="acct-prod",
                environment="production",
                preview_payload={},
            )
        )
        db.commit()

    app.dependency_overrides[get_app_settings] = lambda: Settings(
        app_env="production",
        api_auth_token="secret-token",
        broker_provider="webull",
        trading_mode="live",
        enable_live_trading=True,
        webull_env="production",
        webull_app_key="app-key",
        webull_app_secret="app-secret",
        webull_account_id="acct-prod",
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/orders/live/{preview_id}/confirm",
                headers={"Authorization": "Bearer secret-token"},
                json={
                    "acknowledge_live_risk": True,
                    "production_confirmation_text": "CONFIRM AAPL BUY 1.0000 MARKET 100 acct-prod production",
                    "confirm_symbol": "AAPL",
                    "confirm_side": "BUY",
                    "confirm_quantity": "2.0000",
                    "confirm_order_type": "MARKET",
                    "confirm_estimated_notional": "100",
                    "confirm_account_id": "acct-prod",
                    "confirm_environment": "production",
                },
            )

            assert response.status_code == 400
            assert response.json()["detail"]["message"] == "production confirmation details mismatch"
            assert "confirm_quantity" in response.json()["detail"]["mismatches"]
    finally:
        app.dependency_overrides.clear()
