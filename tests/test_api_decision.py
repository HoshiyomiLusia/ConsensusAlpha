from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.main import app
from app.storage.database import SessionLocal
from app.storage.repositories import new_id
from app.storage.tables import PaperPositionTable


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
            assert data["decision_plan"]["selected_symbol"] == data["selected_proposal"]["symbol"]
            assert data["decision_plan"]["portfolio_review_count"] >= 0
            assert data["decision_plan"]["opportunity_count"] == 1
            assert data["conference"]["symbol"] == data["selected_proposal"]["symbol"]
            assert data["conference"]["final_action"] == data["selected_proposal"]["proposed_action"]
            assert data["decision_plan"]["final_action"] == data["conference"]["final_action"]
            assert data["decision_plan"]["next_step"]

            proposal_detail = client.get(f"/proposals/{data['proposal_run']['proposal_run_id']}")
            assert proposal_detail.status_code == 200
            assert proposal_detail.json()["conferences"][0]["conference_id"] == data["conference"]["conference_id"]

            audit = client.get("/audit")
            assert audit.status_code == 200
            assert any(event["action"] == "decision.run" for event in audit.json())
    finally:
        app.dependency_overrides.clear()


def test_run_decision_prioritizes_existing_position_stop_loss_review():
    held_symbol = f"Z{uuid4().hex[:5]}".upper()
    with SessionLocal() as db:
        db.add(
            PaperPositionTable(
                id=new_id("pos"),
                symbol=held_symbol,
                quantity="10",
                average_price="150",
                market_value="1500",
            )
        )
        db.commit()

    app.dependency_overrides[get_app_settings] = lambda: Settings(trade_cooldown_seconds=0)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/decision/run",
                json={
                    "symbols": [f"N{uuid4().hex[:5]}".upper()],
                    "max_proposals": 1,
                    "max_notional": "500",
                    "use_llm": False,
                },
            )

            assert response.status_code == 200, response.text
            data = response.json()
            assert data["decision_plan"]["selected_source"] == "portfolio_review"
            assert data["decision_plan"]["selected_symbol"] == held_symbol
            assert data["selected_proposal"]["proposed_action"] == "SELL"
            assert data["conference"]["final_action"] == "SELL"
            assert data["decision_plan"]["portfolio_review_count"] >= 1
    finally:
        app.dependency_overrides.clear()
