from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.main import app


def test_run_decision_api_creates_proposal_conference_and_order():
    symbol = f"Q{uuid4().hex[:5]}".upper()
    app.dependency_overrides[get_app_settings] = lambda: Settings(trade_cooldown_seconds=0)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/decision/run",
                json={
                    "symbols": [symbol],
                    "max_proposals": 1,
                    "max_notional": "1000",
                    "use_llm": True,
                },
            )

            assert response.status_code == 200, response.text
            data = response.json()
            assert data["proposal_run"]["candidate_count"] == 1
            assert data["selected_proposal"]["symbol"] == symbol
            assert data["conference"]["symbol"] == symbol
            assert data["conference"]["final_action"] == "BUY"
            assert data["conference"]["risk_approved"] is True
            assert data["conference"]["order_id"] is not None

            proposal_detail = client.get(f"/proposals/{data['proposal_run']['proposal_run_id']}")
            assert proposal_detail.status_code == 200
            assert proposal_detail.json()["conferences"][0]["conference_id"] == data["conference"]["conference_id"]

            audit = client.get("/audit")
            assert audit.status_code == 200
            assert any(event["action"] == "decision.run" for event in audit.json())
    finally:
        app.dependency_overrides.clear()
