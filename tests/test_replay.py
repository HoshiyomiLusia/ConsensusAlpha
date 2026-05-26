import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import Settings
from app.main import app
from app.market_data.models import MarketSnapshot
from app.storage.database import SessionLocal, init_db
from scripts.replay import replay_snapshot
from scripts.replay_diff import diff_replays, format_report


def test_prompt_version_is_persisted_in_conference_detail():
    symbol = f"P{uuid4().hex[:5]}".upper()
    app.dependency_overrides[get_app_settings] = lambda: Settings(trade_cooldown_seconds=0)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/conference/run",
                json={"symbol": symbol, "asset_type": "equity", "max_notional": "1000"},
            )
            assert response.status_code == 200, response.text
            detail = client.get(f"/conference/{response.json()['conference_id']}")
            assert detail.status_code == 200
            body = detail.json()
            assert {opinion["prompt_version"] for opinion in body["opinions"]} == {"2026-05-25-v1"}
            assert {event["prompt_version"] for event in body["model_usage"]["events"]} == {
                "2026-05-25-v1"
            }
    finally:
        app.dependency_overrides.clear()


def test_replay_snapshot_is_deterministic_with_mock_llm():
    init_db()
    snapshot = MarketSnapshot(
        symbol=f"R{uuid4().hex[:5]}".upper(),
        asset_type="equity",
        price=Decimal("101.25"),
        open=Decimal("100.00"),
        high=Decimal("102.00"),
        low=Decimal("99.50"),
        previous_close=Decimal("100.50"),
        volume=1_200_000,
        timestamp=datetime.now(UTC),
        source="test",
    )
    config = {"replay": {"mock_agent_action": "BUY", "max_notional": "1000"}}
    settings = Settings(trade_cooldown_seconds=0)

    with SessionLocal() as db:
        first = asyncio.run(
            replay_snapshot(
                db=db,
                settings=settings,
                snapshot_id="snap_replay_1",
                snapshot=snapshot,
                config=config,
            )
        )
        db.rollback()
        second = asyncio.run(
            replay_snapshot(
                db=db,
                settings=settings,
                snapshot_id="snap_replay_1",
                snapshot=snapshot,
                config=config,
            )
        )
        db.rollback()

    for row in (first, second):
        row.pop("conference_id", None)
        row.pop("order_id", None)
        row.pop("live_preview_id", None)
        for opinion in row["opinions"]:
            opinion.pop("raw_payload", None)
    assert first == second


def test_replay_diff_reports_changed_decision():
    base = {
        "snap_1": {
            "snapshot_id": "snap_1",
            "symbol": "AAPL",
            "snapshot_timestamp": "2026-05-25T00:00:00+00:00",
            "final_action": "BUY",
            "consensus_reached": True,
            "risk_approved": True,
            "risk_reason": "approved",
            "opinions": [{"role": "market_analyst", "action": "BUY"}],
        }
    }
    candidate = {
        "snap_1": {
            **base["snap_1"],
            "final_action": "HOLD",
            "consensus_reached": False,
            "opinions": [{"role": "market_analyst", "action": "HOLD"}],
        }
    }
    diffs = diff_replays(base, candidate)
    assert len(diffs) == 1
    report = format_report(diffs)
    assert "final_action" in report
    assert "BUY -> HOLD" in report
