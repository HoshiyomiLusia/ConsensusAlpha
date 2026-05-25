#!/usr/bin/env sh
set -eu

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${API_AUTH_TOKEN:-}"

if [ -z "$TOKEN" ]; then
  echo "API_AUTH_TOKEN is required for production preflight." >&2
  exit 1
fi

echo "Checking health..."
curl -fsS "$API_BASE/health" >/dev/null

echo "Checking production readiness..."
READINESS_JSON="$(curl -fsS -H "Authorization: Bearer $TOKEN" "$API_BASE/production/readiness")"
READINESS_JSON="$READINESS_JSON" "${PYTHON:-python3}" - <<'PY'
import json
import os
import sys

data = json.loads(os.environ["READINESS_JSON"])
print(f"ready={data['ready']} live_trading_ready={data['live_trading_ready']}")
for check in data["checks"]:
    status = "PASS" if check["passed"] else check["severity"].upper()
    print(f"{status}: {check['name']} - {check['summary']}")
if not data["ready"]:
    sys.exit(2)
PY
