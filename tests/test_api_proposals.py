from fastapi.testclient import TestClient

from app.main import app


def test_run_proposals_with_mock_provider_returns_candidates():
    with TestClient(app) as client:
        response = client.post(
            "/proposals/run",
            json={
                "symbols": ["AAPL", "MSFT", "SPY"],
                "max_proposals": 2,
                "max_notional": "1000",
                "use_llm": True,
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["candidate_count"] == 3
        assert len(data["proposals"]) == 2
        assert data["used_llm"] is False
        assert data["proposals"][0]["symbol"] in {"AAPL", "MSFT", "SPY"}

        detail = client.get(f"/proposals/{data['proposal_run_id']}")
        assert detail.status_code == 200
        assert len(detail.json()["proposals"]) == 2
        assert detail.json()["conferences"] == []

        conference = client.post(
            "/conference/run",
            json={
                "symbol": data["proposals"][0]["symbol"],
                "asset_type": data["proposals"][0]["asset_type"],
                "max_notional": "1000",
                "proposal_run_id": data["proposal_run_id"],
            },
        )
        assert conference.status_code == 200, conference.text
        detail_after_conference = client.get(f"/proposals/{data['proposal_run_id']}")
        assert detail_after_conference.status_code == 200
        assert detail_after_conference.json()["conferences"][0]["conference_id"] == conference.json()["conference_id"]

        recent = client.get("/proposals")
        assert recent.status_code == 200
        current = next(item for item in recent.json() if item["proposal_run_id"] == data["proposal_run_id"])
        assert current["proposal_count"] == 2


def test_run_proposals_uses_default_candidate_pool_when_symbols_are_empty():
    with TestClient(app) as client:
        response = client.post(
            "/proposals/run",
            json={
                "symbols": [],
                "max_proposals": 5,
                "max_notional": "1000",
                "use_llm": False,
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["candidate_count"] >= 10
        assert len(data["proposals"]) == 5
        assert data["scanned"][0]["symbol"]
