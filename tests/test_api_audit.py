from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.main import app


def test_conference_run_creates_audit_event():
    symbol = f"A{uuid4().hex[:5]}".upper()
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
            conference_id = response.json()["conference_id"]

            audit = client.get("/audit")
            assert audit.status_code == 200
            events = audit.json()
            event = next(item for item in events if item["entity_id"] == conference_id)
            assert event["action"] == "conference.run"
            assert event["entity_type"] == "conference"
            assert event["payload"]["symbol"] == symbol
    finally:
        app.dependency_overrides.clear()


def test_proposal_run_creates_audit_event():
    with TestClient(app) as client:
        response = client.post(
            "/proposals/run",
            json={
                "symbols": ["AAPL", "MSFT"],
                "max_proposals": 1,
                "max_notional": "1000",
                "use_llm": False,
            },
        )
        assert response.status_code == 200, response.text
        proposal_run_id = response.json()["proposal_run_id"]

        audit = client.get("/audit")
        assert audit.status_code == 200
        events = audit.json()
        event = next(item for item in events if item["entity_id"] == proposal_run_id)
        assert event["action"] == "proposal.run"
        assert event["payload"]["proposal_count"] == 1
