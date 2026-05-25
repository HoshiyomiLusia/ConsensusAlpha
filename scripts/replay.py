#!/usr/bin/env python3
"""Replay stored market snapshots through the current conference pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm_provider import build_llm_provider
from app.brokers.mock_provider import MockBrokerProvider
from app.conference.models import ConferenceRunRequest
from app.conference.orchestrator import ConferenceOrchestrator
from app.core.config import Settings
from app.market_data.models import MarketSnapshot
from app.storage.database import SessionLocal, init_db
from app.storage.tables import AgentOpinionTable, MarketSnapshotTable, RiskDecisionTable


def parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def load_replay_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(path)
    text = config_path.read_text()
    if config_path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is present through uvicorn[standard]
        raise RuntimeError("YAML config requires PyYAML") from exc
    return yaml.safe_load(text) or {}


def settings_from_config(config: dict[str, Any]) -> Settings:
    values = config.get("settings") or {}
    return Settings(**values)


def request_from_config(config: dict[str, Any], snapshot: MarketSnapshot) -> ConferenceRunRequest:
    replay = config.get("replay") or {}
    return ConferenceRunRequest(
        symbol=snapshot.symbol,
        asset_type=snapshot.asset_type,
        max_notional=Decimal(str(replay.get("max_notional", "1000"))),
        order_type=replay.get("order_type", "MARKET"),
        limit_price=Decimal(str(replay["limit_price"])) if replay.get("limit_price") else None,
        mock_agent_action=replay.get("mock_agent_action"),
    )


def snapshot_from_row(row: MarketSnapshotTable) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=row.symbol,
        asset_type=row.asset_type,  # type: ignore[arg-type]
        price=Decimal(row.price),
        open=Decimal(row.open) if row.open else None,
        high=Decimal(row.high) if row.high else None,
        low=Decimal(row.low) if row.low else None,
        previous_close=Decimal(row.previous_close) if row.previous_close else None,
        volume=row.volume,
        timestamp=row.timestamp,
        source=row.source,
        raw_payload=row.raw_payload or {},
    )


async def replay_snapshot(
    *,
    db: Session,
    settings: Settings,
    snapshot_id: str,
    snapshot: MarketSnapshot,
    config: dict[str, Any],
) -> dict[str, Any]:
    provider = MockBrokerProvider(settings.webull_account_id or "replay-account")
    llm_provider = build_llm_provider(settings)
    request = request_from_config(config, snapshot)
    result = await ConferenceOrchestrator(
        settings=settings,
        provider=provider,
        llm_provider=llm_provider,
    ).run(
        db=db,
        request=request,
        snapshot_override=snapshot,
        persist=False,
    )
    opinion_rows = list(
        db.scalars(
            select(AgentOpinionTable)
            .where(AgentOpinionTable.conference_id == result.conference_id)
            .order_by(AgentOpinionTable.role)
        )
    )
    risk_row = db.scalar(
        select(RiskDecisionTable).where(RiskDecisionTable.conference_id == result.conference_id)
    )
    opinions = [
        {
            "agent_id": row.agent_id,
            "role": row.role,
            "symbol": row.symbol,
            "action": row.action,
            "confidence": row.confidence,
            "thesis": row.thesis,
            "concerns": row.concerns or [],
            "blocking_concerns": row.blocking_concerns or [],
            "suggested_max_position_pct": row.suggested_max_position_pct,
            "suggested_stop_loss_pct": row.suggested_stop_loss_pct,
            "prompt_version": row.prompt_version or None,
        }
        for row in opinion_rows
    ]
    return {
        "snapshot_id": snapshot_id,
        "snapshot_timestamp": snapshot.timestamp.isoformat(),
        "symbol": snapshot.symbol,
        "conference_id": result.conference_id,
        "final_action": result.final_action,
        "consensus_reached": result.consensus_reached,
        "risk_approved": result.risk_approved,
        "risk_reason": risk_row.reason if risk_row else "",
        "order_id": result.order_id,
        "live_preview_id": result.live_preview_id,
        "opinions": opinions,
    }


async def replay_range(
    *,
    from_dt: datetime,
    to_dt: datetime,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    settings = settings_from_config(config)
    init_db()
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(MarketSnapshotTable)
                .where(MarketSnapshotTable.timestamp >= from_dt)
                .where(MarketSnapshotTable.timestamp <= to_dt)
                .order_by(MarketSnapshotTable.timestamp, MarketSnapshotTable.symbol)
            )
        )
        snapshots = [(row.id, snapshot_from_row(row)) for row in rows]

    outputs: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for snapshot_id, snapshot in snapshots:
            line = await replay_snapshot(
                db=db,
                settings=settings,
                snapshot_id=snapshot_id,
                snapshot=snapshot,
                config=config,
            )
            outputs.append(line)
            db.rollback()
    return outputs


def write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    with Path(path).open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay stored market snapshots.")
    parser.add_argument("--from", dest="from_date", required=True, help="Inclusive ISO datetime/date")
    parser.add_argument("--to", dest="to_date", required=True, help="Inclusive ISO datetime/date")
    parser.add_argument("--config", help="Optional YAML/JSON replay config")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    return parser


async def async_main() -> None:
    args = build_parser().parse_args()
    config = load_replay_config(args.config)
    rows = await replay_range(
        from_dt=parse_dt(args.from_date),
        to_dt=parse_dt(args.to_date),
        config=config,
    )
    write_jsonl(args.output, rows)
    print(f"wrote {len(rows)} replay rows to {args.output}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
