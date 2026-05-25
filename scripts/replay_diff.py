#!/usr/bin/env python3
"""Diff two replay JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with Path(path).open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row.get("snapshot_id") or f"{row.get('symbol')}:{row.get('snapshot_timestamp')}")
            rows[key] = row
    return rows


def opinion_action_map(row: dict[str, Any]) -> dict[str, str]:
    return {
        str(opinion.get("role")): str(opinion.get("action"))
        for opinion in row.get("opinions", [])
    }


def diff_replays(base_rows: dict[str, dict[str, Any]], candidate_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    all_keys = sorted(set(base_rows) | set(candidate_rows))
    for key in all_keys:
        base = base_rows.get(key)
        candidate = candidate_rows.get(key)
        if base is None or candidate is None:
            diffs.append(
                {
                    "snapshot_id": key,
                    "change": "added" if base is None else "removed",
                    "base": base,
                    "candidate": candidate,
                }
            )
            continue

        fields = {}
        for field in ("final_action", "consensus_reached", "risk_approved", "risk_reason"):
            if base.get(field) != candidate.get(field):
                fields[field] = {"base": base.get(field), "candidate": candidate.get(field)}

        base_votes = opinion_action_map(base)
        candidate_votes = opinion_action_map(candidate)
        if base_votes != candidate_votes:
            fields["opinion_actions"] = {"base": base_votes, "candidate": candidate_votes}

        if fields:
            diffs.append(
                {
                    "snapshot_id": key,
                    "symbol": candidate.get("symbol") or base.get("symbol"),
                    "snapshot_timestamp": candidate.get("snapshot_timestamp") or base.get("snapshot_timestamp"),
                    "change": "changed",
                    "fields": fields,
                }
            )
    return diffs


def format_report(diffs: list[dict[str, Any]]) -> str:
    if not diffs:
        return "No replay differences.\n"
    lines = [f"Replay differences: {len(diffs)}"]
    for diff in diffs:
        lines.append(
            f"- {diff['snapshot_id']} {diff.get('symbol', '')} {diff.get('snapshot_timestamp', '')}: {diff['change']}"
        )
        for field, values in (diff.get("fields") or {}).items():
            lines.append(f"  - {field}: {values['base']} -> {values['candidate']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diff two replay JSONL outputs.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", help="Optional report path")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    diffs = diff_replays(load_jsonl(args.base), load_jsonl(args.candidate))
    report = format_report(diffs)
    if args.output:
        Path(args.output).write_text(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
