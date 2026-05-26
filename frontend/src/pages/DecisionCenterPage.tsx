import { FormEvent, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Loader2,
  RefreshCcw,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  WalletCards
} from "lucide-react";
import {
  ConferenceListItem,
  ConferenceDetail,
  DecisionRunResponse,
  RunConferenceResponse,
  Settings as AppSettings,
  api
} from "../api/client";
import { displayValue } from "../lib/format";

type DecisionStage = "idle" | "scan" | "select" | "conference" | "summary" | "done" | "error";

type DecisionResult = {
  decision: DecisionRunResponse;
  run: RunConferenceResponse;
  conference: ConferenceDetail | null;
};

type FallbackDecisionResult = {
  conference: ConferenceListItem | null;
  orderId: string | null;
  livePreviewId: string | null;
};

type DecisionBaseline = {
  conferenceIds: Set<string>;
  paperOrderIds: Set<string>;
  livePreviewIds: Set<string>;
};

const stages: Array<{ key: DecisionStage; label: string }> = [
  { key: "scan", label: "持仓与候选" },
  { key: "select", label: "一审计划" },
  { key: "conference", label: "组合会议" },
  { key: "summary", label: "风控" }
];

const MIN_STAGE_VISIBLE_MS = 500;
const DECISION_TIMEOUT_MS = 45_000;
const FALLBACK_POLL_START_MS = 3_000;
const FALLBACK_POLL_INTERVAL_MS = 1_000;
const FALLBACK_POLL_ATTEMPTS = 12;

function wait(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

function parseSymbols(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function currentStageIndex(stage: DecisionStage): number {
  return stages.findIndex((item) => item.key === stage);
}

function currentStageLabel(stage: DecisionStage): string {
  return stages.find((item) => item.key === stage)?.label ?? "准备";
}

function orderOutcome(result: DecisionResult): string {
  const plan = result.decision.decision_plan;
  if (plan.order_id) return `已生成模拟订单 ${plan.order_id}`;
  if (plan.live_preview_id) return "已生成实盘预览，等待人工确认";
  if (plan.final_action === "HOLD") return "结论为观望，未生成订单";
  if (!result.run.consensus_reached) return "未达成共识，未生成订单";
  if (!plan.risk_approved) return "风控阻断，未生成订单";
  return "未生成订单";
}

function orderActionLabel(result: DecisionResult): string {
  const plan = result.decision.decision_plan;
  if (plan.live_preview_id) return "确认订单预览";
  if (plan.order_id) return "查看模拟订单";
  return "查看订单页";
}

function fallbackOrderOutcome(result: FallbackDecisionResult): string {
  if (result.orderId) return `已生成模拟订单 ${result.orderId}`;
  if (result.livePreviewId) return "已生成实盘预览，等待人工确认";
  if (result.conference?.final_action === "HOLD") return "结论为观望，未生成订单";
  if (result.conference && !result.conference.consensus_reached) return "未达成共识，未生成订单";
  if (result.conference?.risk_approved === false) return "风控阻断，未生成订单";
  return "会议已完成";
}

function dataSourceLabel(settings?: AppSettings): string {
  if (!settings) return "读取中";
  return settings.broker_provider === "webull" ? "真实数据" : "模拟数据";
}

function tradingLabel(settings?: AppSettings): string {
  if (!settings) return "读取中";
  if (settings.trading_mode === "live" && settings.enable_live_trading) return "实盘待确认";
  return "模拟执行";
}

export default function DecisionCenterPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings, staleTime: 30_000 });
  const provider = useQuery({ queryKey: ["provider-status"], queryFn: api.providerStatus, refetchInterval: 30_000 });
  const livePreviews = useQuery({ queryKey: ["live-previews"], queryFn: api.livePreviews, refetchInterval: 20_000 });
  const paperOrders = useQuery({ queryKey: ["paper-orders"], queryFn: api.paperOrders, refetchInterval: 20_000 });
  const positions = useQuery({ queryKey: ["positions"], queryFn: api.positions, refetchInterval: 30_000 });

  const [customUniverse, setCustomUniverse] = useState("");
  const [maxNotional, setMaxNotional] = useState("1000");
  const [maxProposals, setMaxProposals] = useState("5");
  const [useLlm, setUseLlm] = useState(true);
  const [stage, setStage] = useState<DecisionStage>("idle");
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [fallbackResult, setFallbackResult] = useState<FallbackDecisionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resettingTestState, setResettingTestState] = useState(false);
  const [testResetMessage, setTestResetMessage] = useState<string | null>(null);
  const runningRef = useRef(false);

  const isRunning = stage !== "idle" && stage !== "done" && stage !== "error";
  const pendingPreviews = (livePreviews.data ?? []).filter((preview) => preview.status === "PENDING_CONFIRMATION");
  const canResetTestAccount = settings.data?.app_env !== "production";

  async function invalidateAfterDecision(proposalRunId: string) {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["proposals"] }),
      queryClient.invalidateQueries({ queryKey: ["proposal", proposalRunId] }),
      queryClient.invalidateQueries({ queryKey: ["conferences"] }),
      queryClient.invalidateQueries({ queryKey: ["orders", "paper"] }),
      queryClient.invalidateQueries({ queryKey: ["paper-orders"] }),
      queryClient.invalidateQueries({ queryKey: ["live-previews"] }),
      queryClient.invalidateQueries({ queryKey: ["positions"] }),
      queryClient.invalidateQueries({ queryKey: ["audit"] })
    ]);
  }

  function currentBaseline(): DecisionBaseline {
    return {
      conferenceIds: new Set<string>(),
      paperOrderIds: new Set((paperOrders.data ?? []).map((order) => order.order_id)),
      livePreviewIds: new Set((livePreviews.data ?? []).map((preview) => preview.preview_id))
    };
  }

  async function enrichBaseline(baseline: DecisionBaseline): Promise<DecisionBaseline> {
    const conferences = await api.conferences().catch(() => []);
    return {
      conferenceIds: new Set(conferences.map((conference) => conference.conference_id)),
      paperOrderIds: baseline.paperOrderIds,
      livePreviewIds: baseline.livePreviewIds
    };
  }

  async function pollDecisionCompletion(baseline: DecisionBaseline): Promise<FallbackDecisionResult | null> {
    for (let attempt = 0; attempt < FALLBACK_POLL_ATTEMPTS; attempt += 1) {
      await wait(FALLBACK_POLL_INTERVAL_MS);
      const [conferences, orders, previews] = await Promise.all([
        api.conferences().catch(() => []),
        api.paperOrders().catch(() => []),
        api.livePreviews().catch(() => [])
      ]);
      const conference = conferences.find((item) => !baseline.conferenceIds.has(item.conference_id)) ?? null;
      const order = orders.find((item) => !baseline.paperOrderIds.has(item.order_id)) ?? null;
      const preview = previews.find((item) => !baseline.livePreviewIds.has(item.preview_id)) ?? null;
      if (conference || order || preview) {
        return {
          conference,
          orderId: order?.order_id ?? conference?.order_id ?? null,
          livePreviewId: preview?.preview_id ?? conference?.live_preview_id ?? null
        };
      }
    }
    return null;
  }

  async function runDecision(event: FormEvent) {
    event.preventDefault();
    if (result || fallbackResult) return;
    if (runningRef.current) return;
    runningRef.current = true;
    setError(null);
    setResult(null);
    setFallbackResult(null);
    setStage("scan");
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), DECISION_TIMEOUT_MS);

    try {
      const baseline = await enrichBaseline(currentBaseline());
      const decisionRequest = api.runDecision({
        symbols: parseSymbols(customUniverse),
        max_proposals: Number(maxProposals),
        max_notional: maxNotional,
        use_llm: useLlm,
        order_type: "MARKET",
        limit_price: null
      }, { signal: controller.signal });
      void decisionRequest.catch(() => undefined);
      await wait(MIN_STAGE_VISIBLE_MS);
      const firstDecisionResult = await Promise.race([
        decisionRequest,
        wait(FALLBACK_POLL_START_MS).then(() => null)
      ]);
      if (!firstDecisionResult) {
        setStage("select");
        const fallback = await pollDecisionCompletion(baseline);
        if (fallback) {
          window.clearTimeout(timeoutId);
          controller.abort();
          setFallbackResult(fallback);
          setStage("done");
          void Promise.all([
            queryClient.invalidateQueries({ queryKey: ["conferences"] }),
            queryClient.invalidateQueries({ queryKey: ["paper-orders"] }),
            queryClient.invalidateQueries({ queryKey: ["live-previews"] }),
            queryClient.invalidateQueries({ queryKey: ["positions"] }),
            queryClient.invalidateQueries({ queryKey: ["audit"] })
          ]);
          return;
        }
      }
      const decision = firstDecisionResult ?? await decisionRequest;
      window.clearTimeout(timeoutId);

      if (decision.proposal_run.proposals.length === 0) {
        throw new Error("没有生成可提交会议的提案。");
      }

      setStage("select");
      await wait(MIN_STAGE_VISIBLE_MS);
      setStage("conference");
      await wait(MIN_STAGE_VISIBLE_MS);
      setStage("summary");
      await wait(MIN_STAGE_VISIBLE_MS);
      setResult({
        decision,
        run: decision.conference,
        conference: null
      });
      setStage("done");
      void invalidateAfterDecision(decision.proposal_run.proposal_run_id);
      void api.conference(decision.conference.conference_id)
        .then((conference) => {
          setResult((current) => {
            if (!current || current.run.conference_id !== decision.conference.conference_id) return current;
            return { ...current, conference };
          });
        })
        .catch(() => undefined);
    } catch (caught) {
      window.clearTimeout(timeoutId);
      setStage("error");
      if (caught instanceof DOMException && caught.name === "AbortError") {
        setError("自动决策请求超时。后端可能仍在处理，请刷新订单或稍后重试。");
      } else {
        setError(caught instanceof Error ? caught.message : "一键决策运行失败。");
      }
    } finally {
      runningRef.current = false;
    }
  }

  function reset() {
    setStage("idle");
    setResult(null);
    setFallbackResult(null);
    setError(null);
  }

  async function resetTestAccount() {
    if (resettingTestState || settings.data?.app_env === "production") return;
    setResettingTestState(true);
    setTestResetMessage(null);
    try {
      const response = await api.resetTestPaperState();
      setStage("idle");
      setResult(null);
      setFallbackResult(null);
      setError(null);
      setTestResetMessage(response.message);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["paper-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] }),
        queryClient.invalidateQueries({ queryKey: ["audit"] })
      ]);
    } catch (caught) {
      setTestResetMessage(caught instanceof Error ? caught.message : "测试账户重置失败。");
    } finally {
      setResettingTestState(false);
    }
  }

  const activeIndex = currentStageIndex(stage);
  const tokenUsage = result?.conference?.model_usage;
  const riskApproved = result?.decision.decision_plan.risk_approved ?? false;
  const hasDecisionResult = Boolean(result || fallbackResult);
  const shouldOpenOrders = Boolean(
    result?.decision.decision_plan.order_id ||
      result?.decision.decision_plan.live_preview_id ||
      fallbackResult?.orderId ||
      fallbackResult?.livePreviewId ||
      pendingPreviews.length > 0
  );

  return (
    <div className="simple-page">
      <section className="simple-hero">
        <div className="simple-copy">
          <span className="decision-eyebrow">
            <Sparkles size={15} />
            简单模式
          </span>
          <h2>从账户状态到组合决策</h2>
          <p>系统先复盘当前持仓，再扫描市场候选池，一审形成计划，最后由会议决定今天是否买入、卖出、减仓或观望。</p>
        </div>

        <form className="simple-run-box" onSubmit={runDecision}>
          <div className="simple-pipeline-card">
            <strong>自动流程</strong>
            <span>持仓复盘 / 候选池脚本 / 组合会议 / 风控与订单路由</span>
          </div>
          <button className="primary-action simple-main-action" type="submit" disabled={isRunning || hasDecisionResult}>
            {isRunning ? <Loader2 size={20} className="spin-icon" /> : <Sparkles size={20} />}
            {isRunning ? "正在处理" : hasDecisionResult ? "已生成结果" : "开始自动决策"}
          </button>
          {(isRunning || error) && (
            <div className={error ? "simple-inline-feedback danger" : "simple-inline-feedback"}>
              <strong>{error ? "运行失败" : `正在执行：${currentStageLabel(stage)}`}</strong>
              <span>
                {error
                  ? error
                  : "系统正在复盘持仓、扫描候选池、生成计划并提交会议。"}
              </span>
            </div>
          )}
        </form>
      </section>

      {(isRunning || stage === "error") && (
        <section className="simple-progress" aria-live="polite">
          <div className="simple-progress-head">
            <strong>{stage === "error" ? "运行失败" : "正在处理"}</strong>
          </div>
          <div className="simple-step-row">
            {stages.map((item, index) => {
              const completed = activeIndex > -1 && index < activeIndex;
              const active = item.key === stage;
              return (
                <span className={completed ? "completed" : active ? "active" : ""} key={item.key}>
                  {completed ? <CheckCircle2 size={15} /> : active ? <Loader2 size={15} className="spin-icon" /> : null}
                  {item.label}
                </span>
              );
            })}
          </div>
          {error && <div className="error-box">{error}</div>}
        </section>
      )}

      {result && (
        <section className="simple-result">
          <div className="simple-result-main">
            <span>最终结论</span>
            <h3>
              {result.decision.decision_plan.selected_symbol}：{result.decision.decision_plan.selected_intent}
            </h3>
            <p>{result.decision.decision_plan.summary}</p>
          </div>
          <div className="simple-result-facts">
            <div>
              <span>持仓复盘</span>
              <strong>{result.decision.decision_plan.portfolio_review_count} 项</strong>
            </div>
            <div>
              <span>新机会</span>
              <strong>{result.decision.decision_plan.opportunity_count} 个</strong>
            </div>
            <div>
              <span>会议共识</span>
              <strong>{result.run.consensus_reached ? "达成" : "未达成"}</strong>
            </div>
            <div>
              <span>风控</span>
              <strong>{riskApproved ? "通过" : "阻断或无需执行"}</strong>
            </div>
          </div>
          <div className="simple-proposal-strip">
            <span>计划候选</span>
            <div>
              {result.decision.decision_plan.items.slice(0, 6).map((item) => (
                <Link to="/advanced" key={`${item.source}-${item.symbol}`}>
                  <strong>{item.symbol}</strong>
                  <small>{item.intent} · {displayValue(item.proposed_action)}</small>
                </Link>
              ))}
            </div>
          </div>
          <div className="simple-order-outcome">
            <span>订单路由</span>
            <strong>{orderOutcome(result)}</strong>
            <small>
              {result.decision.decision_plan.next_step}
              {tokenUsage ? ` · 模型用量 ${tokenUsage.total_tokens.toLocaleString()} token` : ""}
            </small>
          </div>
          <div className="simple-result-actions">
            {shouldOpenOrders && (
              <Link className="primary-action" to="/orders">
                <ClipboardList size={16} />
                {orderActionLabel(result)}
              </Link>
            )}
            <Link className="secondary-action" to={`/conference/${result.run.conference_id}`}>
              查看详情 <ArrowRight size={16} />
            </Link>
            <button className="secondary-action" type="button" onClick={reset}>
              <RefreshCcw size={16} />
              再来一次
            </button>
          </div>
        </section>
      )}

      {fallbackResult && !result && (
        <section className="simple-result">
          <div className="simple-result-main">
            <span>最终结论</span>
            <h3>
              {fallbackResult.conference?.symbol ?? "决策完成"}：
              {fallbackResult.conference ? displayValue(fallbackResult.conference.final_action) : "已生成结果"}
            </h3>
            <p>后端已经完成本次决策。当前浏览器没有拿到完整响应，所以这里显示从会议和订单记录恢复出的结果。</p>
          </div>
          {fallbackResult.conference && (
            <div className="simple-result-facts">
              <div>
                <span>会议共识</span>
                <strong>{fallbackResult.conference.consensus_reached ? "达成" : "未达成"}</strong>
              </div>
              <div>
                <span>风控</span>
                <strong>{fallbackResult.conference.risk_approved ? "通过" : "阻断或无需执行"}</strong>
              </div>
            </div>
          )}
          <div className="simple-order-outcome">
            <span>订单路由</span>
            <strong>{fallbackOrderOutcome(fallbackResult)}</strong>
            <small>结果已从后端记录恢复。可以继续处理订单或查看会议详情。</small>
          </div>
          <div className="simple-result-actions">
            {shouldOpenOrders && (
              <Link className="primary-action" to="/orders">
                <ClipboardList size={16} />
                {fallbackResult.livePreviewId ? "确认订单预览" : "查看模拟订单"}
              </Link>
            )}
            {fallbackResult.conference && (
              <Link className="secondary-action" to={`/conference/${fallbackResult.conference.conference_id}`}>
                查看详情 <ArrowRight size={16} />
              </Link>
            )}
            <button className="secondary-action" type="button" onClick={reset}>
              <RefreshCcw size={16} />
              再来一次
            </button>
          </div>
        </section>
      )}

      <details className="simple-options">
        <summary>扫描与风控设置</summary>
        <div>
          <div className="simple-readonly-field">
            <span>候选池来源</span>
            <strong>后端候选池脚本</strong>
            <small>默认不需要输入股票代码。系统会先复盘当前持仓，再扫描基础市场池；真实数据模式下会用券商行情逐个扫描。</small>
          </div>
          <label>
            <span>一审提案数量</span>
            <select value={maxProposals} onChange={(event) => setMaxProposals(event.target.value)}>
              <option value="3">3 个</option>
              <option value="4">4 个</option>
              <option value="5">5 个</option>
            </select>
          </label>
          <label>
            <span>单次决策金额上限</span>
            <input value={maxNotional} onChange={(event) => setMaxNotional(event.target.value)} inputMode="decimal" />
            <small className="field-help">这不是“立刻投入这么多钱”，而是风控和订单数量计算使用的上限。真实下单仍需要订单页人工确认。</small>
          </label>
          <label>
            <span>自定义扫描列表</span>
            <textarea
              value={customUniverse}
              onChange={(event) => setCustomUniverse(event.target.value)}
              placeholder="留空则使用后端候选池脚本。需要覆盖时，用逗号或换行输入股票代码。"
              rows={3}
            />
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
            <span>一审阶段可用时使用模型筛选提案，否则回退到规则筛选。</span>
          </label>
        </div>
      </details>

      <section className="simple-status-grid" aria-label="当前状态">
        <Link to="/settings">
          <span>数据</span>
          <strong>{dataSourceLabel(settings.data)}</strong>
          <small>{provider.data?.healthy ? "连接正常" : "需要检查"}</small>
        </Link>
        <Link to="/settings">
          <span>执行</span>
          <strong>{tradingLabel(settings.data)}</strong>
          <small>{settings.data?.enable_live_trading ? "实盘仍需人工确认" : "不会真实下单"}</small>
        </Link>
        <Link to="/orders">
          <span>待处理</span>
          <strong>{pendingPreviews.length} 个</strong>
          <small>{pendingPreviews.length > 0 ? "有订单预览待确认" : "暂无待确认订单"}</small>
        </Link>
        <Link to="/positions">
          <span>账户</span>
          <strong>{positions.data?.length ?? 0} 项</strong>
          <small>当前持仓记录</small>
        </Link>
      </section>

      <section className="simple-action-strip">
        <Link to="/orders">
          <ClipboardList size={18} />
          <div>
            <strong>处理订单</strong>
            <span>{paperOrders.data?.length ?? 0} 笔模拟成交；实盘预览需确认</span>
          </div>
        </Link>
        <Link to="/positions">
          <WalletCards size={18} />
          <div>
            <strong>查看持仓</strong>
            <span>确认账户当前状态</span>
          </div>
        </Link>
        <Link to="/setup">
          <Settings size={18} />
          <div>
            <strong>初始化配置</strong>
            <span>首次使用或重新配置时进入</span>
          </div>
        </Link>
        <Link to="/advanced">
          <SlidersHorizontal size={18} />
          <div>
            <strong>高级页面</strong>
            <span>展开候选、会议、审计等细节</span>
          </div>
        </Link>
        {canResetTestAccount && (
          <button type="button" onClick={resetTestAccount} disabled={resettingTestState}>
            {resettingTestState ? <Loader2 size={18} className="spin-icon" /> : <Trash2 size={18} />}
            <div>
              <strong>重置测试账户</strong>
              <span>{testResetMessage ?? "清空模拟订单和持仓，方便反复测试"}</span>
            </div>
          </button>
        )}
      </section>

      <section className="simple-safety-note">
        <ShieldCheck size={19} />
        <p>简单模式只压缩操作步骤，不压缩保护流程。真实下单仍必须经过风控、订单预览和人工确认。</p>
      </section>
    </div>
  );
}
