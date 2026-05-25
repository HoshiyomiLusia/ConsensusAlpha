import { FormEvent, useState } from "react";
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
import { displayValue, formatReason } from "../lib/format";

type DecisionStage = "idle" | "scan" | "select" | "conference" | "summary" | "done" | "error";

type DecisionResult = {
  proposalRun: ProposalRunResponse;
  selectedProposal: MarketProposal;
  run: RunConferenceResponse;
  conference: ConferenceDetail;
};

const stages: Array<{ key: DecisionStage; label: string }> = [
  { key: "scan", label: "脚本扫描" },
  { key: "select", label: "一审筛选" },
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

function currentStageLabel(stage: DecisionStage): string {
  return stages.find((item) => item.key === stage)?.label ?? "准备";
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

  const [customUniverse, setCustomUniverse] = useState("");
  const [maxNotional, setMaxNotional] = useState("1000");
  const [maxProposals, setMaxProposals] = useState("5");
  const [useLlm, setUseLlm] = useState(true);
  const [stage, setStage] = useState<DecisionStage>("idle");
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

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

    try {
      setStage("scan");
      const decision = await api.runDecision({
        symbols: parseSymbols(customUniverse),
        max_proposals: Number(maxProposals),
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
          <h2>从市场候选池到会议决策</h2>
          <p>系统先用候选池脚本扫描市场，一审筛出 3 到 5 个可提交会议的股票，再把优先级最高的一项送入会议决定行为。</p>
        </div>

        <form className="simple-run-box" onSubmit={runDecision}>
          <div className="simple-pipeline-card">
            <strong>自动流程</strong>
            <span>候选池脚本 / 一审提案 / Agent 会议 / 风控与订单路由</span>
          </div>
          <details className="simple-options">
            <summary>扫描与风控设置</summary>
            <div>
              <div className="simple-readonly-field">
                <span>候选池来源</span>
                <strong>后端候选池脚本</strong>
                <small>默认不需要输入股票代码。脚本会提供基础市场池，当前包含主要 ETF 和高流动性美股；真实数据模式下会用券商行情逐个扫描。</small>
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
          <button className="primary-action simple-main-action" type="submit" disabled={isRunning}>
            {isRunning ? <Loader2 size={20} className="spin-icon" /> : <Sparkles size={20} />}
            {isRunning ? "正在处理" : "开始自动决策"}
          </button>
          {(isRunning || error) && (
            <div className={error ? "simple-inline-feedback danger" : "simple-inline-feedback"}>
              <strong>{error ? "运行失败" : `正在执行：${currentStageLabel(stage)}`}</strong>
              <span>
                {error
                  ? error
                  : "系统正在扫描候选池、运行一审并提交会议。"}
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
              {result.selectedProposal.symbol}：{displayValue(result.run.final_action)}
            </h3>
            <p>{topRiskReason(result.conference)}</p>
          </div>
          <div className="simple-result-facts">
            <div>
              <span>扫描池</span>
              <strong>{result.proposalRun.candidate_count} 个</strong>
            </div>
            <div>
              <span>一审提案</span>
              <strong>{result.proposalRun.proposals.length} 个</strong>
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
            <span>一审入围</span>
            <div>
              {result.proposalRun.proposals.map((proposal) => (
                <Link to="/advanced" key={proposal.symbol}>
                  <strong>{proposal.symbol}</strong>
                  <small>{displayValue(proposal.proposed_action)} · {Math.round(proposal.confidence * 100)}%</small>
                </Link>
              ))}
            </div>
          </div>
          <div className="simple-order-outcome">
            <span>订单路由</span>
            <strong>{orderOutcome(result)}</strong>
            <small>{tokenUsage ? `模型用量 ${tokenUsage.total_tokens.toLocaleString()} token` : "模型用量未记录"}</small>
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
      </section>

      <section className="simple-safety-note">
        <ShieldCheck size={19} />
        <p>简单模式只压缩操作步骤，不压缩保护流程。真实下单仍必须经过风控、订单预览和人工确认。</p>
      </section>
    </div>
  );
}
