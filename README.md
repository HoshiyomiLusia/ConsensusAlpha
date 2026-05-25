# ConsensusAlpha

ConsensusAlpha is a full-stack AI-assisted trading research console for US stocks and ETFs. It scans market candidates, runs a multi-agent model conference, evaluates strict consensus, applies deterministic risk gates, and then routes approved decisions to paper execution or protected live-order preview.

Default mode is safe: mock broker, mock LLM, paper trading, and live trading disabled.

## Features

- FastAPI backend with SQLite/PostgreSQL storage
- React/Vite TypeScript operations console
- One-click decision flow: proposal scan -> agent conference -> consensus -> risk gate -> order result
- Mock broker and Webull provider integration
- Mock LLM by default, configurable multi-model agents
- Paper execution and guarded live-order preview
- Production readiness gate for real-money trading
- Audit trail and model token usage tracking

## Quick Start

Backend:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Open:

```text
http://127.0.0.1:5173
```

## Tests

```bash
.venv/bin/python -m pytest
cd frontend && pnpm build
```

## Production Notes

Real-money trading is blocked unless `GET /production/readiness` returns `ready=true`.

The readiness gate checks production auth, PostgreSQL, Webull production credentials, live-trading switches, conservative risk limits, daily live-order caps, regular-hours gating, broker connectivity, and real model configuration.

Live orders are never placed directly from model output. The system first creates a live preview, then requires explicit manual confirmation. Production confirmation must match symbol, side, quantity, order type, notional, account, environment, and the required confirmation text.

Production deployment template:

```bash
cp .env.production.example .env.production
docker compose -f docker-compose.prod.yml up --build -d
API_AUTH_TOKEN=... sh scripts/production_preflight.sh
```

UAT/test Docker environment:

```bash
cp .env.test.example .env.test
docker compose -f docker-compose.test.yml up --build
```

Test console: `http://127.0.0.1:5174`; test API: `http://127.0.0.1:8001`.

## Security

Never commit real `.env` files, broker credentials, LLM API keys, account IDs, or database dumps. The repo includes `.env.example` and `.env.production.example` templates only.

## Disclaimer

This project is research and execution tooling, not financial advice. Real trading requires broker UAT, credential configuration, operational monitoring, and user responsibility for every confirmed order.
