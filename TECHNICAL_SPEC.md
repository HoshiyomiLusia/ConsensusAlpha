# ConsensusAlpha 技术规格文档

版本：0.1
日期：2026-05-24
目标读者：编码 Agent / 后端工程师

## 1. 项目目标

ConsensusAlpha 是一个面向股票自动化研究和交易执行的系统。系统通过 Webull OpenAPI 接入市场数据、账户、持仓和订单能力，将市场数据交给多个 AI Agent 组成的“投资会议”进行独立分析、互相质询和最终共识判断。只有当所有必要 Agent 达成一致，并且确定性风控规则通过后，系统才允许进入 paper trading 或真实下单流程。

核心原则：

- AI 只能产生结构化建议，不能直接访问券商密钥，也不能直接下单。
- 下单必须经过共识协议、风控闸门、执行器三层控制。
- 默认优先 paper trading；真实交易必须显式开启。
- 所有行情输入、Agent 发言、共识结果、风控检查、订单请求和执行结果必须可审计、可复盘。

## 2. 第一阶段 MVP 范围

必须实现：

- Python 后端服务，提供 HTTP API。
- Webull Broker/MarketData 适配层接口，先支持 mock provider，保留真实 Webull provider 接口。
- 行情快照输入：symbol、price、volume、timestamp、OHLCV。
- AI 会议编排器：多个 Agent 独立产出结构化观点。
- 共识机制：所有必要 Agent 必须同意同一个 action 才能进入风控。
- 风控闸门：仓位、最大单笔风险、最大日亏损、冷却时间、禁交易开关。
- Paper trading 执行器：不真实下单，记录虚拟订单。
- REST API：触发一次分析、查看会议记录、查看 paper orders。
- 单元测试覆盖共识、风控、paper executor。
- `.env.example`，不得提交真实密钥。

暂不实现：

- 真实资金自动下单默认开启。
- 高频交易。
- 复杂期权策略。
- 多券商聚合。
- 前端复杂 UI。
- stock-sdk 集成。第一版只围绕 Webull 适配层设计。

## 3. 技术栈

推荐栈：

- Python 3.11
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL，开发环境可先用 SQLite 作为 fallback
- pytest
- httpx
- tenacity
- structlog 或标准 logging
- Docker Compose

可选：

- Redis：后续用于实时行情缓存、任务锁和异步队列。
- Celery/RQ/Arq：后续用于周期性扫描和异步会议任务。
- TimescaleDB：后续用于大规模 K 线存储。

Webull 接入：

- 优先使用 Webull 官方 SDK。
- 市场数据：HTTP 拉取历史/最新数据，实时数据后续通过 MQTT。
- 交易/账户：HTTP。
- 订单状态：后续通过 gRPC 订阅。
- 不要在业务代码里直接散落 Webull endpoint；必须封装在 provider 内。

## 4. 推荐目录结构

```text
ConsensusAlpha/
  README.md
  .env.example
  pyproject.toml
  docker-compose.yml
  docs/
    TECHNICAL_SPEC.md
  app/
    main.py
    core/
      config.py
      logging.py
      time.py
    brokers/
      base.py
      mock_provider.py
      webull_provider.py
      models.py
    market_data/
      models.py
      service.py
      indicators.py
    agents/
      base.py
      prompts.py
      mock_llm.py
      llm_provider.py
      roles.py
    conference/
      models.py
      orchestrator.py
      consensus.py
    risk/
      models.py
      rules.py
      service.py
    execution/
      models.py
      paper.py
      live.py
    storage/
      database.py
      tables.py
      repositories.py
    api/
      routes_health.py
      routes_conference.py
      routes_orders.py
  tests/
    test_consensus.py
    test_risk.py
    test_paper_execution.py
    test_api_conference.py
```

## 5. 配置要求

`.env.example` 必须包含：

```bash
APP_ENV=development
DATABASE_URL=sqlite:///./consensus_alpha.db

TRADING_MODE=paper
ENABLE_LIVE_TRADING=false

WEBULL_APP_KEY=
WEBULL_APP_SECRET=
WEBULL_REGION=us
WEBULL_ACCOUNT_ID=
WEBULL_API_BASE_URL=

LLM_PROVIDER=mock
LLM_MODEL=
LLM_API_KEY=

MAX_POSITION_PCT=0.05
MAX_SINGLE_TRADE_RISK_PCT=0.01
MAX_DAILY_LOSS_PCT=0.02
MIN_AGENT_CONFIDENCE=0.65
TRADE_COOLDOWN_SECONDS=300
```

规则：

- `TRADING_MODE=paper` 是默认值。
- `ENABLE_LIVE_TRADING=false` 是默认值。
- 当 `ENABLE_LIVE_TRADING=false` 时，live executor 必须拒绝所有真实下单请求。
- Webull 密钥只能从环境变量读取。
- 日志中不得打印完整密钥、access token、签名或账户敏感信息。

## 6. 核心领域模型

### 6.1 MarketSnapshot

```python
class MarketSnapshot(BaseModel):
    symbol: str
    asset_type: Literal["equity", "etf", "option", "crypto", "future"]
    price: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    previous_close: Decimal | None = None
    volume: int | None = None
    timestamp: datetime
    source: str
```

### 6.2 AgentOpinion

```python
class AgentOpinion(BaseModel):
    agent_id: str
    role: str
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0, le=1)
    thesis: str
    concerns: list[str] = []
    blocking_concerns: list[str] = []
    suggested_max_position_pct: float | None = None
    suggested_stop_loss_pct: float | None = None
```

### 6.3 ConferenceResult

```python
class ConferenceResult(BaseModel):
    conference_id: str
    symbol: str
    started_at: datetime
    completed_at: datetime
    opinions: list[AgentOpinion]
    final_action: Literal["BUY", "SELL", "HOLD"]
    consensus_reached: bool
    consensus_reason: str
```

### 6.4 RiskDecision

```python
class RiskDecision(BaseModel):
    approved: bool
    reason: str
    checks: list[dict]
    max_quantity: Decimal | None = None
    max_notional: Decimal | None = None
```

### 6.5 ExecutionOrder

```python
class ExecutionOrder(BaseModel):
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: Decimal | None = None
    status: Literal["PENDING", "ACCEPTED", "FILLED", "REJECTED", "CANCELLED"]
    mode: Literal["paper", "live"]
    created_at: datetime
```

## 7. Agent 会议设计

第一版固定 5 个角色：

- `market_analyst`：价格走势、成交量、K 线和技术指标。
- `risk_manager`：仓位、波动、最大亏损、止损建议。此角色拥有 veto 权。
- `contrarian_critic`：专门反驳交易理由，寻找盲点。
- `execution_specialist`：流动性、滑点、订单类型、交易时间。
- `chairperson`：汇总讨论结果，但不能绕过其他 Agent 的投票。

第一版可以使用 `MockLLMProvider` 返回可预测结果，确保系统逻辑先跑通。真实 LLM provider 后续接入。

### 7.1 会议流程

```text
1. 获取 MarketSnapshot
2. 构建 ConferenceContext
3. 并行调用必要 Agent，获得第一轮 AgentOpinion
4. 校验每个 AgentOpinion 是否符合 schema
5. 将全部意见交给 chairperson 生成摘要
6. 调用 consensus engine
7. 如果 consensus_reached=false，最终动作必须是 HOLD
8. 如果 final_action=BUY/SELL，进入 risk gate
9. risk gate 通过后，进入 paper executor
10. 保存完整审计记录
```

### 7.2 共识规则

第一版使用严格一致规则：

- 必要 Agent：`market_analyst`、`risk_manager`、`contrarian_critic`、`execution_specialist`。
- `chairperson` 不计入投票，只负责摘要。
- 所有必要 Agent 的 `action` 必须完全一致。
- 所有必要 Agent 的 `confidence` 必须大于等于 `MIN_AGENT_CONFIDENCE`。
- 任意 Agent 出现 `blocking_concerns`，最终动作必须是 `HOLD`。
- `risk_manager` 只要输出 `HOLD` 或 blocking concern，最终动作必须是 `HOLD`。
- 如果意见不一致，最终动作必须是 `HOLD`。

伪代码：

```python
def evaluate_consensus(opinions: list[AgentOpinion], min_confidence: float) -> ConferenceResult:
    required_roles = {
        "market_analyst",
        "risk_manager",
        "contrarian_critic",
        "execution_specialist",
    }

    required = [o for o in opinions if o.role in required_roles]
    if {o.role for o in required} != required_roles:
        return hold("missing required agent opinion")

    if any(o.blocking_concerns for o in required):
        return hold("blocking concern raised")

    if any(o.confidence < min_confidence for o in required):
        return hold("confidence below threshold")

    actions = {o.action for o in required}
    if len(actions) != 1:
        return hold("agents disagree")

    action = actions.pop()
    if action == "HOLD":
        return hold("unanimous hold")

    return approve(action)
```

## 8. 风控闸门

风控必须是确定性代码，不允许由 LLM 决定。

第一版规则：

- live trading 未开启时，拒绝 live 下单。
- final action 为 `HOLD` 时，不生成订单。
- 单个 symbol 仓位不得超过 `MAX_POSITION_PCT`。
- 单笔交易最大风险不得超过 `MAX_SINGLE_TRADE_RISK_PCT`。
- 当日累计亏损超过 `MAX_DAILY_LOSS_PCT` 时，拒绝新开仓。
- 同一 symbol 在 `TRADE_COOLDOWN_SECONDS` 内不得重复开仓。
- 价格、数量、notional 必须为正数。
- 如果无法获取账户权益或价格，拒绝交易。

输出必须是 `RiskDecision`，并保存每条 check 的通过/失败结果。

## 9. 执行层

### 9.1 PaperExecutor

第一版只实现 paper executor：

- 接收通过风控的交易意图。
- 按当前 snapshot price 模拟成交。
- 记录 order、fill、position。
- 支持查询 paper orders。
- 不调用 Webull 下单接口。

### 9.2 LiveExecutor

第一版只实现保护壳：

- 当 `ENABLE_LIVE_TRADING=false` 时总是拒绝。
- 当 `ENABLE_LIVE_TRADING=true` 时仍要求 `TRADING_MODE=live`。
- 真实 Webull 下单接口留 TODO，并通过 `WebullProvider.place_order()` 统一调用。
- 不允许 Agent 或 orchestrator 直接调用 live executor。

## 10. Broker Provider 抽象

定义统一接口：

```python
class BrokerProvider(Protocol):
    async def get_market_snapshot(self, symbol: str) -> MarketSnapshot: ...
    async def get_account_summary(self) -> AccountSummary: ...
    async def get_positions(self) -> list[Position]: ...
    async def preview_order(self, order: OrderIntent) -> OrderPreview: ...
    async def place_order(self, order: OrderIntent) -> ExecutionOrder: ...
```

实现：

- `MockBrokerProvider`：第一版必须完整可用，用于测试和无密钥开发。
- `WebullProvider`：先实现类、配置校验和方法骨架；有 API 凭证后再补真实调用。

WebullProvider 要求：

- 使用官方 SDK 优先。
- 封装认证、签名、请求重试和异常映射。
- 对外只返回项目内部模型。
- 不让上层业务感知 Webull 原始响应结构。

## 11. API 设计

### 11.1 Health

```http
GET /health
```

返回：

```json
{
  "status": "ok",
  "trading_mode": "paper"
}
```

### 11.2 触发一次会议

```http
POST /conference/run
Content-Type: application/json
```

请求：

```json
{
  "symbol": "AAPL",
  "asset_type": "equity",
  "max_notional": "1000"
}
```

返回：

```json
{
  "conference_id": "uuid",
  "symbol": "AAPL",
  "final_action": "HOLD",
  "consensus_reached": false,
  "risk_approved": false,
  "order_id": null
}
```

### 11.3 查询会议记录

```http
GET /conference/{conference_id}
```

必须返回：

- snapshot
- all agent opinions
- chairperson summary
- consensus result
- risk decision
- order result if any

### 11.4 查询 paper orders

```http
GET /orders/paper
```

返回最近 paper orders。

## 12. 数据库表

最小表：

- `market_snapshots`
- `conference_runs`
- `agent_opinions`
- `consensus_results`
- `risk_decisions`
- `risk_checks`
- `paper_orders`
- `paper_fills`
- `paper_positions`

每张表必须有：

- `id`
- `created_at`
- `updated_at`，如适用

审计相关表必须保存原始 JSON payload：

- `agent_opinions.raw_payload`
- `conference_runs.context_payload`
- `risk_decisions.checks_payload`

## 13. 测试要求

必须写 pytest：

- `test_consensus_unanimous_buy_passes`
- `test_consensus_disagreement_holds`
- `test_consensus_blocking_concern_holds`
- `test_consensus_low_confidence_holds`
- `test_risk_rejects_when_live_disabled`
- `test_risk_rejects_position_limit`
- `test_paper_executor_creates_filled_order`
- `test_run_conference_api_returns_hold_with_mock_agents`

所有测试必须在无 Webull key、无 LLM key 的环境下通过。

## 14. 日志与审计

日志要求：

- 每次会议生成 `conference_id`。
- 每次订单生成 `client_order_id`。
- 日志中记录模块、symbol、action、risk result。
- 不记录完整密钥、签名、token。

审计要求：

- 任何 BUY/SELL 决策必须能追溯到 snapshot、Agent opinions、consensus result、risk checks、execution result。
- 如果拒绝交易，必须明确拒绝原因。

## 15. 开发顺序

建议编码 Agent 按以下顺序实现：

1. 创建项目骨架、`pyproject.toml`、`.env.example`。
2. 实现 Pydantic models。
3. 实现 `MockBrokerProvider`。
4. 实现 `MockLLMProvider` 和 5 个 Agent role。
5. 实现 consensus engine。
6. 实现 risk service。
7. 实现 paper executor。
8. 实现 FastAPI routes。
9. 实现 SQLite/Postgres storage。
10. 写 pytest。
11. 补 README：安装、运行、测试、环境变量。

## 16. 验收标准

本地运行：

```bash
uvicorn app.main:app --reload
```

或：

```bash
docker compose up --build
```

必须满足：

- `GET /health` 返回 ok。
- 无任何真实 API key 时，系统可以使用 mock provider 跑通。
- `POST /conference/run` 可以生成一条完整会议记录。
- 默认情况下不会真实下单。
- 当 Agent 不一致时，最终结果是 `HOLD`。
- 当 Agent 一致 BUY 且风控通过时，生成 paper order。
- pytest 全部通过。

## 17. 官方参考资料

- Webull OpenAPI Overview: https://developer.webull.com/apis/docs/about-open-api/
- Webull Market Data API Overview: https://developer.webull.com/apis/docs/market-data-api/overview/
- Webull Market Data Getting Started: https://developer.webull.com/apis/docs/market-data-api/getting-started/
- Webull Trading API Overview: https://developer.webull.com/apis/docs/trade-api/overview/
- Webull Orders API: https://developer.webull.com/apis/docs/trade-api/trade/
- Webull Accounts API: https://developer.webull.com/apis/docs/trade-api/account/
