#!/usr/bin/env python
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.proposals.universe import DEFAULT_MARKET_UNIVERSE, infer_asset_type  # noqa: E402


def main() -> None:
    rows = [{"symbol": symbol, "asset_type": infer_asset_type(symbol)} for symbol in DEFAULT_MARKET_UNIVERSE]
    print(json.dumps({"source": "default_market_universe", "count": len(rows), "symbols": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
