# ConsensusAlpha 完善路线图

版本：0.2
日期：2026-05-25
适用对象：后续接手开发的人 / Coding Agent

## 设计原则(贯穿所有 Phase)

- **内部复杂、外部一键**。任何新增能力必须压在 LLM 调用之前的确定性管线里,不增加 frontend 操作步骤。
- **AI 只产生建议,不做硬决策**。新增逻辑不能让 LLM 绕过共识、风控、执行三层闸门。
- **mock 路径必须可跑通**。每个 Phase 都要保证在无 Webull / 无 LLM key 的环境下跑得通,真实接入是可选项。
- **审计可复盘**。新增数据全部记录到 `audit_events` / 各专属表,带原始 payload。

---

## 已完成

### Phase 1 — 特征工程 + 多时间框架上下文 ✅ (2026-05-25)

**做了什么**

- 新增 `app/market_data/features.py`:SMA / EMA / RSI / MACD / Bollinger / ATR / VWAP / Momentum / 实现波动率 / 趋势分类,纯 Python + Decimal,无 numpy 依赖
- 新增 `MarketContext` / `TimeframeFeatures` / `LiquidityProfile` 模型,支持 `from_snapshot` 降级
- `BrokerProvider` 协议加 `get_historical_bars(symbol, interval, lookback, asset_type)`
- `MockBrokerProvider` 实现确定性合成 bars(漂移 + 正弦 + 种子噪声)
- `WebullProvider` 通过 SDK `get_history_bar` 实现,interval 映射 `1d→d1` 等
- `LLMProvider.generate_opinion` 协议从 `snapshot=` 改为 `context=`
- Agent prompts 升级为角色专属指引 + 结构化 MarketContext 输入
- `ConferenceOrchestrator` 并行拉取多时间框架(1d×100 / 1h×60 / 5m×60)+ SPY 基准,任一失败优雅降级,MarketContext 入库供审计

**测试**:`tests/test_market_features.py` 新增 15 个,原有 30 个全部保留。

### Phase 4 — Replay / 回测框架 ✅ (2026-05-25)

**做了什么**

- 新增 `scripts/replay.py`:从 `market_snapshots` 按时间范围加载历史快照,用当前会议管线重放,输出 JSONL。
- 新增 `scripts/replay_diff.py`:对比两份 replay JSONL,报告最终动作、共识、风控和 Agent vote 差异。
- 新增 `app/agents/prompts.py`:集中管理角色 prompt 和 `2026-05-25-v1` 版本号。
- `AgentOpinion` / `ModelUsageEvent` / 数据表新增 `prompt_version`,会议详情页展示 prompt 版本。
- `ConferenceOrchestrator.run(...)` 支持 `snapshot_override` 和 `persist=False`,用于重放模式跳过 broker 行情调用且不污染数据库。
- `init_db()` 增加兼容性列迁移,已有 SQLite/Postgres volume 会自动补 `prompt_version` 列。

**测试**:`tests/test_replay.py` 覆盖 mock replay 确定性、diff 报告、prompt version 入库;全量 pytest 48 个通过。

**偏离说明**:初版 replay 使用已保存 `market_snapshots`;如果历史 payload 内没有完整 `market_context`,会降级为 snapshot-only 重放。后续 Phase 2/9 可继续把 regime/features payload 补得更完整。

---

## 待办路线图(按推荐执行顺序)

每个 Phase 都标注:
- **目标**:一句话定调
- **动机**:解决前一阶段没解决的什么问题
- **改动文件**:具体路径
- **数据模型**:如有
- **测试要点**
- **工作量估计**:0.5d / 1d / 2-3d / 1w
- **是否影响 UX**

---

### Phase 2 — 标的池 + 市场状态层

**目标**:让"一键"真正一键 — 用户不再需要输入 symbol 列表。

**动机**:目前 `/decision/run` 要求传 symbols,违背"用户操作最简"。同时所有决策都缺少市场整体状态的上下文(同样的"突破 + 放量"在 trending 和 choppy 市场含义不同)。

**改动文件**
- 新增 `app/universe/__init__.py`、`app/universe/service.py`
  - 默认 watchlist:SP100 / NASDAQ100 高流动性子集,按市值/ADV 过滤
  - 提供 `get_default_universe(settings) -> list[str]`
  - 支持配置文件覆盖(`UNIVERSE_FILE` env var)
- 新增 `app/regime/__init__.py`、`app/regime/service.py`
  - 输入:SPY / VIX(如有)/ QQQ 的 1d 历史 bars
  - 输出:`RegimeSnapshot(label: "trend_up"|"trend_down"|"range"|"high_vol"|"low_vol", confidence: float, indicators: dict)`
  - 实现逻辑:SPY 50/200 SMA 交叉 + ATR/价格比阈值
- 修改 `app/api/routes_decision.py`:`symbols` 改为可选,缺省调用 universe service
- 修改 `app/conference/orchestrator.py`:`ConferenceContext` 注入 `regime`
- 修改 prompts:让 Agent 看到 regime 标签
- Frontend:`DecisionCenterPage.tsx` 头部加 regime 徽章,symbols 输入改为可选 + placeholder 提示"留空使用默认池"

**数据模型**
- 新表 `regime_snapshots`:id / label / confidence / indicators_payload / created_at
- `ConferenceRunTable.context_payload` 补 `regime_snapshot_id`

**测试要点**
- universe service 在缺省 + 自定义文件下均能产出 symbol list
- regime classifier 在合成 SPY 序列(单调上涨 / 单调下跌 / 横盘)下输出正确标签
- `/decision/run` 不传 symbols 时使用默认池

**工作量**:2-3 天

**影响 UX**:✅ 不影响,但让一键更"一键"

---

### Phase 3 — 持仓复评 + 退出建议

**目标**:同一个"一键"内,同步对所有已持仓做"是否继续持有"判断。

**动机**:当前只有入场逻辑,没有出场逻辑。Agent 已经会输出 `suggested_stop_loss_pct`,但风控里没强制成 OCO,持仓也没有定时复评。一个交易系统**入场 30%,管理 70%**。

**改动文件**
- 新增 `app/portfolio/exit_evaluator.py`
  - `evaluate_position(position, context) -> ExitRecommendation`
  - 评估维度:thesis 是否失效(原 BUY 理由的特征反向)、止损是否触及、时间止损(持仓 > N 天)、Agent 复评
- 修改 `app/conference/orchestrator.py`:`run_one_click_decision` 在一键流程末尾,对每个持仓跑一次**轻量级**会议(可只用 1-2 个 Agent,降低成本)
- 修改 `app/api/routes_decision.py`:`DecisionRunResponse` 加 `exit_recommendations: list[ExitRecommendation]`
- 修改 frontend `DecisionCenterPage.tsx`:同一卡片显示"建议平仓 N 项"

**数据模型**
- 新表 `position_reviews`:id / symbol / position_id / recommendation(HOLD/CLOSE/REDUCE)/ reason / triggered_features / created_at
- `ExitRecommendation` Pydantic:symbol / current_position / recommendation / urgency(low/medium/high)/ reason / suggested_quantity_to_close

**测试要点**
- 当 thesis 特征反向(原买入因 RSI > 70,现在 RSI < 30),应产出 CLOSE 建议
- 当持仓在合理区间且无新信号,产出 HOLD 建议
- 一键决策响应里同时包含新入场建议和持仓复评

**工作量**:3-4 天

**影响 UX**:✅ 不影响,只是在同一响应里多带回信息

**前置依赖**:Phase 1(需要特征对比)

---

### Phase 4 — Replay / 回测框架 ✅ 已完成

**目标**:能用历史 snapshot + 当前 prompt/参数,重放出会议决策序列,可 diff。

**动机**:**这是所有其他改进的乘数**。没有回测,任何参数调整都是赌博:调 `MIN_AGENT_CONFIDENCE` 从 0.65→0.70 谁也不知道好坏,换 prompt 无法对比新旧版本,改风控规则没有回归集。

**改动文件**
- 新增 `scripts/replay.py`:CLI 工具
  - 入参:`--from DATE --to DATE --config path/to/config.yaml --output out.jsonl`
  - 从 `market_snapshots` 表逐条加载,对每条重新跑 `ConferenceOrchestrator`(用 mock 或真实 LLM)
  - 输出每次会议的 `final_action / consensus_reached / risk_approved / opinions` 到 jsonl
- 新增 `scripts/replay_diff.py`:对比两份 replay 输出,产生 diff 报告
- 修改 `app/agents/llm_provider.py`:prompts 抽到 `app/agents/prompts.py`,加版本号
  - `PROMPT_VERSIONS = {"market_analyst": "2026-05-25-v1", ...}`
  - audit 里记 `prompt_version_id`
- 修改 `app/conference/orchestrator.py`:支持"重放模式"(给定 snapshot 直接跑,不再调 broker)

**数据模型**
- `agent_opinions` 表加 `prompt_version: str`
- `model_usage_events` 表加 `prompt_version: str`

**测试要点**
- 同一 snapshot + 同一 mock LLM 重放两次,结果完全一致(确定性)
- 改 prompt 版本后 replay 产生不同输出,diff 工具能展示差异

**工作量**:1 周

**影响 UX**:🟢 完全不影响(纯研发工具)

**建议**:这是后续所有 Phase 的"测量工具",**强烈建议早做**

---

### Phase 5 — 订单生命周期 + 与券商对账

**目标**:支持订单从提交到成交/拒绝的完整状态跟踪 + 与 broker 持仓的周期性 reconciliation。

**动机**:当前 `LiveExecutor.place_order` 是 fire-and-forget。真实交易需要:
- 跟踪 PENDING / PARTIAL / FILLED / REJECTED 状态变化
- 限价单未成交时的撤单/改价策略
- 部分成交处理
- 与 broker 报告的真实持仓比对

否则会出现"系统以为有仓位但 broker 没有"这种最危险的状态。

**改动文件**
- 新增 `app/execution/order_tracker.py`:后台任务,定期拉取 broker 订单状态,更新本地表
- 新增 `app/execution/reconciliation.py`:`reconcile_positions(db, provider) -> ReconciliationReport`
- 修改 `app/brokers/base.py`:协议加 `get_order_status(order_id)` 和 `cancel_order(order_id)`
- 修改 `MockBrokerProvider` 和 `WebullProvider`:实现新接口
- 修改 `app/execution/live.py`:place 之后启动追踪
- 新增 API:`GET /orders/live/{order_id}/status`、`POST /orders/live/{order_id}/cancel`
- 新增 health check:`GET /health/reconciliation` 返回最近一次对账结果

**数据模型**
- 新表 `order_status_events`:id / order_id / status / reported_at / payload
- 新表 `reconciliation_reports`:id / drift_count / drift_details / created_at

**测试要点**
- 模拟 broker 返回 PARTIAL → FILLED 状态变化,本地表正确更新
- 制造一笔本地有 broker 没有的持仓,reconciliation 能检测出来
- 撤单后状态变成 CANCELLED

**工作量**:1 周

**影响 UX**:✅ 不影响主路径,但新增了订单状态查询(可选展示)

**前置依赖**:这是真实接 live 之前的硬性前提

---

### Phase 6 — Paper 执行的滑点与成本建模

**目标**:让 paper executor 的成交结果尽可能贴近真实 live 表现。

**动机**:当前 `PaperExecutor` 按 `snapshot.price` 全量立即成交,这是糖水模拟。Paper 上跑出来的"赚钱策略"到 live 上**几乎肯定**会缩水 30-50%。

**改动文件**
- 新增 `app/execution/slippage.py`:
  - `estimate_slippage_bps(snapshot, liquidity, order_size, side) -> int`
  - 基础模型:`base_spread_bps + market_impact_coef * sqrt(notional / ADV)`
  - 流动性差的标的扣更多
- 新增 `app/execution/cost.py`:佣金 + 监管费(SEC fee + TAF)
- 修改 `app/execution/paper.py`:
  - 成交价 = `snapshot.price * (1 + slippage * side_sign)`
  - 净 notional 减去 cost
  - 大单可拆成部分成交(可选)
- 修改 `PaperFillTable`:加 `slippage_bps`、`commission`、`gross_price`、`net_price`

**数据模型**
- `paper_fills` 加列(见上)

**测试要点**
- 大单(notional/ADV > 0.1)的滑点显著大于小单
- BUY 成交价高于 mid,SELL 成交价低于 mid
- 净 P&L 等于 gross P&L 减去 cost

**工作量**:2-3 天

**影响 UX**:✅ 不影响

**前置依赖**:Phase 1(需要 `liquidity` 估计)

---

### Phase 7 — 组合层风控

**目标**:风控不只看单标的,还看整个组合的暴露和相关性。

**动机**:当前 `RiskService` 18 项检查全部是单标的层。**5 只半导体股各占 4% 仓位 ≠ 20% 风险分散**。需要补:
- 板块/相关性集中度
- 波动率调整的仓位上限
- 组合回撤闸(从峰值跌 X% 自动停盘新仓)
- β/净敞口估算

**改动文件**
- 新增 `app/risk/portfolio.py`:
  - `PortfolioRiskInput`:positions + new_order_intent
  - `PortfolioRiskDecision`:approved + checks(sector_concentration / correlation / drawdown / net_exposure)
- 新增 `app/risk/sector_map.py`:symbol → sector 映射(初版用 SPDR sector ETFs 划分)
- 新增 `app/risk/volatility_sizing.py`:基于 ATR 或 realized vol 计算"等风险"仓位上限
- 修改 `app/risk/service.py`:在原 18 项之后,串行追加组合层检查
- 配置:
  - `MAX_SECTOR_CONCENTRATION_PCT` (默认 0.30)
  - `MAX_PORTFOLIO_DRAWDOWN_PCT` (默认 0.10,触发后停盘)
  - `VOL_TARGET_ANNUALIZED` (默认 0.15,用于反推仓位)

**数据模型**
- 新表 `portfolio_snapshots`:id / total_equity / peak_equity / drawdown_pct / sector_exposures / created_at(每次决策前快照)

**测试要点**
- 当板块集中度超阈值,新增同板块仓位被拒
- 当组合回撤超阈值,所有新建仓被拒
- 高波动标的的仓位上限低于低波动标的(等风险)

**工作量**:1 周

**影响 UX**:✅ 不影响主流程,但拒绝原因可能在风控页面展示

---

### Phase 8 — P&L 归因 + 置信度校准

**目标**:把成交平仓后的 P&L,归因到具体 Agent / 共识形式 / 市场状态;并用历史数据校准 Agent confidence。

**动机**:目前系统不知道哪个 Agent 在什么市场状态下更可靠。Agent 自报的 confidence 也没有任何统计依据(0.65 不代表 65% 准确率)。

**改动文件**
- 新增 `app/analytics/attribution.py`:
  - `attribute_pnl(closed_position) -> AttributionRecord`
  - 关联到原 conference_id → opinions → regime → features
- 新增 `app/analytics/calibration.py`:
  - 对每个 Agent role,统计"confidence ≥ X 的决策实际胜率"
  - 输出 reliability diagram 数据
  - 提供"重映射函数":raw_confidence → calibrated_confidence
- 新增 API:
  - `GET /analytics/agent_performance?role=...&period=...` 返回胜率 / Sharpe
  - `GET /analytics/calibration?role=...` 返回校准曲线
- 修改 `app/agents/llm_provider.py`:可选启用 calibration(读取最近的校准数据,在 raw confidence 上做映射)

**数据模型**
- 新表 `attribution_records`:id / position_id / pnl_usd / pnl_pct / conference_id / regime_label / agent_opinions_snapshot / created_at
- 新表 `agent_calibrations`:id / role / period_start / period_end / reliability_curve_payload / created_at

**测试要点**
- 模拟一组已平仓的盈利和亏损,attribution 能正确关联回 conference 和 Agent
- 校准函数能把 confidence=0.9 的"实际胜率 0.6"重新映射为 ~0.6
- 校准后的低胜率 Agent 在共识中影响力下降(可选:加权投票)

**工作量**:1-2 周

**影响 UX**:✅ 不影响主流程,新增分析页面

**前置依赖**:Phase 4(回测可以加速校准数据积累)+ Phase 5(订单生命周期完整才能算 P&L)

---

### Phase 9 — Proposal 评分函数改进

**目标**:把"涨跌幅×100 + 日内幅×40 + log(volume)"这种朴素打分换成有方向性的多因子打分。

**动机**:当前打分会稳定筛出"今天最闹腾的票",大涨和大跌、突破和闪崩拿到的分数差不多。再交给 Agent 判方向相当于"先找最难判断的样本"。

**改动文件**
- 修改 `app/proposals/service.py:scan_snapshot`:改为基于 `MarketContext`(需要拉历史 bars)
- 新增评分维度:
  - 趋势一致性(多时间框架 trend 是否对齐)
  - 相对强弱(vs SPY 的 20 日 momentum 差)
  - 突破信号(收盘 > 20 日高点)
  - 量价配合(放量上涨 vs 放量下跌)
- 输出 `direction_score: float` (正→偏多,负→偏空,绝对值大→信号强)

**改动文件**
- `app/proposals/service.py`
- `app/proposals/models.py`:`CandidateScanItem` 加 `direction_score`、`trend_alignment`、`relative_strength`

**测试要点**
- 单调上涨的合成数据 direction_score > 0
- 单调下跌的合成数据 direction_score < 0
- 横盘 direction_score 接近 0

**工作量**:2-3 天

**影响 UX**:✅ 不影响,但提案质量上升

**前置依赖**:Phase 1

---

### Phase 10 — Prompt 版本化 + 决策质量指标看板

**目标**:让 prompt 改动可对比,让操作员能从一个仪表盘看决策质量趋势。

**动机**:目前 prompts 散在 `llm_provider.py` 里,改了就改了,没有版本。决策质量(命中率、盈亏比、Sharpe)也没有可视化。

**改动文件**
- 新增 `app/agents/prompts.py`:集中管理所有 role 的 prompt + 版本号
  - `PROMPTS = {"market_analyst": {"v1": "...", "v2": "..."}, ...}`
  - `get_active_prompts(settings) -> dict[str, str]`
  - audit 里记 `{role: version}` 映射
- 新增 API:`GET /analytics/decisions/summary?period=...` 返回:
  - 总会议数 / 入场数 / consensus 达成率 / 风控通过率
  - 命中率(已平仓盈利占比)
  - 平均盈亏比
  - 决策 Sharpe(可选)
- 修改 frontend:`Dashboard.tsx` 加这些指标卡片

**数据模型**
- `agent_opinions` 已在 Phase 4 加了 `prompt_version`,这里复用

**测试要点**
- 切换 prompt version 后 audit 里能查到使用的版本
- summary endpoint 在空数据下返回合理的零值响应

**工作量**:3-4 天

**影响 UX**:🟡 Dashboard 新增指标卡片(增量,不破坏)

**前置依赖**:Phase 8(需要 P&L 归因数据)

---

## 选做项(优先级低 / 可酌情)

### A — 新闻 / 催化剂集成
- 接 Benzinga / Polygon / Finnhub 等新闻 API
- 把当日相关新闻摘要塞给 `contrarian_critic`
- 影响:Agent 决策对消息面有感
- 工作量:3-4 天 + API 费用

### B — Canary(小额实盘)模式
- `TRADING_MODE=canary`:最多 N 笔/天,每笔 ≤ $X
- 介于 paper 和 full live 之间
- 用来验证执行差异、券商 API 行为、滑点真实分布
- 工作量:2-3 天

### C — Kill Switch + 操作员告警
- Settings 加 `HALT_ALL_TRADING: bool`,所有 executor 启动前检查
- 异常告警:连续 N 笔亏损 / 单标的亏损超 X% / 对账失败
- 通过 Slack/邮件/前端推送
- 工作量:2-3 天

### D — 时间感知决策
- 开盘前 30 min / 收盘前 30 min / 财报日 / FOMC 日:走单独的 prompt 或避开
- 需要先有 earnings calendar 接入
- 工作量:1 周

### E — 多源异质信号 Agent(深度版多代理共识)
- 让不同 Agent 看不同的信息切面:
  - market_analyst → 技术指标
  - risk_manager → 波动率、相关性、组合敞口
  - contrarian_critic → 新闻 + 情绪 + 异常资金流
  - execution_specialist → 盘口、价差、深度
- 这是把"多模型 ≠ 多信号"的根本缺陷彻底解决
- 工作量:2-3 周(取决于数据源接入难度)

---

## 推荐执行顺序

按"边际价值最高 / 风险最低 / 前置依赖少"排序:

```
Phase 1 (✅ 已完成)
   ↓
Phase 2: Universe + Regime          ────┐
Phase 3: 持仓复评 + 退出             ────┤  并行,都依赖 Phase 1
Phase 9: Proposal 评分改进           ────┘
   ↓
Phase 4: Replay/回测框架             ◄── 关键节点:之后所有改动可量化
   ↓
Phase 6: 滑点/成本建模              ────┐
Phase 7: 组合层风控                  ────┤  并行,改 paper / risk 两条路径
   ↓
Phase 5: 订单生命周期 + 对账        ◄── 准备走 live 之前必须做完
   ↓
Phase 8: P&L 归因 + 置信度校准     ◄── 需要前面 5/6/7 都有数据
   ↓
Phase 10: Prompt 版本化 + 看板
   ↓
选做项 A-E
```

---

## 真正走实盘前的硬性检查清单

完成下面所有项之前,**不应该**把 `ENABLE_LIVE_TRADING=true` 在生产环境打开:

- [ ] Phase 5 完成(订单生命周期 + 对账)
- [ ] Phase 6 完成(滑点建模,paper 结果可信)
- [ ] Phase 7 完成(组合层风控,有回撤闸)
- [ ] Phase 4 的 replay 跑过至少 30 天历史数据,无异常
- [ ] Canary 模式(选做项 B)跑过至少 2 周,无对账 drift
- [ ] Kill switch(选做项 C)联调过一次
- [ ] `/production/readiness` 全绿
- [ ] `scripts/production_preflight.sh` 全绿

---

## 文档维护

每完成一个 Phase,把"已完成"部分追加一节,标上完成日期 + 实际工作量 + 任何与本路线图偏离的地方。
