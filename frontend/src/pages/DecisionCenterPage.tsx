import { FormEvent, useMemo, useState } from "react";
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
  WalletCards
} from "lucide-react";
import {
  ConferenceDetail,
  MarketProposal,
  ProposalRunResponse,
  RunConferenceResponse,
  Settings as AppSettings,
  api
} from "../api/client";
import { StatusBadge } from "../components/Badges";
import { displayValue, formatReason } from "../lib/format";

const defaultUniverse = "SPY, QQQ, AAPL, MSFT, NVDA, TSLA, META, AMZN, GOOGL";

type DecisionStage = "idle" | "scan" | "select" | "conference" | "summary" | "done" | "error";

type DecisionResult = {
  proposalRun: ProposalRunResponse;
  selectedProposal: MarketProposal;
  run: RunConferenceResponse;
  conference: ConferenceDetail;
};

const stages: Array<{ key: DecisionStage; label: string }> = [
  { key: "scan", label: "扫描" },
  { key: "select", label: "提案" },
  { key: "conference", label: "会议" },
  { key: "summary", label: "风控" }
];

function parseSymbols(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function currentStageIndex(stage: DecisionStage): number {
  return stages.findIndex((item) => item.key === stage);
}

function topRiskReason(detail: ConferenceDetail): string {
  const failed = detail.risk_decision?.checks.find((check) => !check.passed);
  return formatReason(failed?.reason ?? detail.risk_decision?.reason ?? detail.consensus_result.consensus_reason);
}

function orderOutcome(result: DecisionResult): string {
  if (result.run.order_id) return `已生成模拟订单 ${result.run.order_id}`;
  if (result.run.live_preview_id) return "已生成实盘预览，等待人工确认";
  if (result.run.final_action === "HOLD") return "结论为观望，未生成订单";
  if (!result.run.consensus_reached) return "未达成共识，未生成订单";
  if (!result.run.risk_approved) return "风控阻断，未生成订单";
  return "未生成订单";
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

  const [universe, setUniverse] = useState(defaultUniverse);
  const [maxNotional, setMaxNotional] = useState("1000");
  const [useLlm, setUseLlm] = useState(true);
  const [stage, setStage] = useState<DecisionStage>("idle");
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const symbols = useMemo(() => parseSymbols(universe), [universe]);
  const isRunning = stage !== "idle" && stage !== "done" && stage !== "error";
  const pendingPreviews = (livePreviews.data ?? []).filter((preview) => preview.status === "PENDING_CONFIRMATION");

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

  async function runDecision(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (symbols.length === 0) {
      setStage("error");
      setError("候选池不能为空。至少需要一个股票或 ETF 代码。");
      return;
    }

    try {
      setStage("scan");
      const decision = await api.runDecision({
        symbols,
        max_proposals: 3,
        max_notional: maxNotional,
        use_llm: useLlm,
        order_type: "MARKET",
        limit_price: null
      });

      if (decision.proposal_run.proposals.length === 0) {
        throw new Error("没有生成可提交会议的提案。");
      }

      setStage("select");
      setStage("conference");
      setStage("summary");
      const conference = await api.conference(decision.conference.conference_id);
      await invalidateAfterDecision(decision.proposal_run.proposal_run_id);
      setResult({
        proposalRun: decision.proposal_run,
        selectedProposal: decision.selected_proposal,
        run: decision.conference,
        conference
      });
      setStage("done");
    } catch (caught) {
      setStage("error");
      setError(caught instanceof Error ? caught.message : "一键决策运行失败。");
    }
  }

  function reset() {
    setStage("idle");
    setResult(null);
    setError(null);
  }

  const activeIndex = currentStageIndex(stage);
  const tokenUsage = result?.conference.model_usage;
  const riskApproved = result?.conference.risk_decision?.approved ?? result?.run.risk_approved ?? false;
  const shouldOpenOrders = Boolean(result?.run.order_id || result?.run.live_preview_id || pendingPreviews.length > 0);

  return (
    <div className="simple-page">
      <section className="simple-hero">
        <div className="simple-copy">
          <span className="decision-eyebrow">
            <Sparkles size={15} />
            简单模式
          </span>
          <h2>先生成决策，再按提示执行</h2>
          <p>默认流程会自动完成候选扫描、会议投票、风控检查和订单路由。你通常只需要确认本次最高金额，然后点击一次。</p>
        </div>

        <form className="simple-run-box" onSubmit={runDecision}>
          <label className="simple-amount-field">
            <span>本次最高投入</span>
            <div>
              <span>$</span>
              <input value={maxNotional} onChange={(event) => setMaxNotional(event.target.value)} inputMode="decimal" />
            </div>
          </label>
          <button className="primary-action simple-main-action" type="submit" disabled={isRunning}>
            {isRunning ? <Loader2 size={20} className="spin-icon" /> : <Sparkles size={20} />}
            {isRunning ? "正在生成" : "一键生成决策"}
          </button>
          <details className="simple-options">
            <summary>调整输入</summary>
            <div>
              <label>
                <span>候选池</span>
                <textarea value={universe} onChange={(event) => setUniverse(event.target.value)} rows={3} />
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
                <span>可用时使用模型生成提案</span>
              </label>
            </div>
          </details>
        </form>
      </section>

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

      {(isRunning || stage === "done" || stage === "error") && (
        <section className="simple-progress" aria-live="polite">
          <div className="simple-progress-head">
            <strong>{stage === "done" ? "决策完成" : stage === "error" ? "运行失败" : "正在处理"}</strong>
            {stage === "done" && <StatusBadge value={result?.run.final_action ?? "HOLD"} tone={result?.run.final_action === "HOLD" ? "warn" : "ok"} />}
          </div>
          <div className="simple-step-row">
            {stages.map((item, index) => {
              const completed = stage === "done" || (activeIndex > -1 && index < activeIndex);
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
              {result.selectedProposal.symbol}：{displayValue(result.run.final_action)}
            </h3>
            <p>{topRiskReason(result.conference)}</p>
          </div>
          <div className="simple-result-facts">
            <div>
              <span>共识</span>
              <strong>{result.run.consensus_reached ? "达成" : "未达成"}</strong>
            </div>
            <div>
              <span>风控</span>
              <strong>{riskApproved ? "通过" : "阻断或无需执行"}</strong>
            </div>
            <div>
              <span>订单</span>
              <strong>{orderOutcome(result)}</strong>
            </div>
            <div>
              <span>用量</span>
              <strong>{tokenUsage ? `${tokenUsage.total_tokens.toLocaleString()} token` : "未记录"}</strong>
            </div>
          </div>
          <div className="simple-result-actions">
            {shouldOpenOrders && (
              <Link className="primary-action" to="/orders">
                <ClipboardList size={16} />
                处理订单
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
      </section>

      <section className="simple-safety-note">
        <ShieldCheck size={19} />
        <p>简单模式只压缩操作步骤，不压缩保护流程。真实下单仍必须经过风控、订单预览和人工确认。</p>
      </section>
    </div>
  );
}
