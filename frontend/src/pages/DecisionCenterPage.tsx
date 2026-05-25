import { FormEvent, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Loader2,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import {
  ConferenceDetail,
  MarketProposal,
  ProposalRunResponse,
  RunConferenceResponse,
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

const stages: Array<{ key: DecisionStage; label: string; description: string }> = [
  { key: "scan", label: "扫描候选", description: "读取候选池行情并排序" },
  { key: "select", label: "选择提案", description: "挑出最适合提交会议的标的" },
  { key: "conference", label: "运行会议", description: "多 Agent 投票并形成共识" },
  { key: "summary", label: "风控与结果", description: "执行确定性风控并汇总结论" }
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
  if (result.run.live_preview_id) return `已生成实盘预览 ${result.run.live_preview_id}`;
  if (result.run.final_action === "HOLD") return "结论为观望，未生成订单";
  if (!result.run.consensus_reached) return "未达成共识，未生成订单";
  if (!result.run.risk_approved) return "风控阻断，未生成订单";
  return "未生成订单";
}

export default function DecisionCenterPage() {
  const queryClient = useQueryClient();
  const [universe, setUniverse] = useState(defaultUniverse);
  const [maxNotional, setMaxNotional] = useState("1000");
  const [useLlm, setUseLlm] = useState(true);
  const [stage, setStage] = useState<DecisionStage>("idle");
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const symbols = useMemo(() => parseSymbols(universe), [universe]);
  const isRunning = stage !== "idle" && stage !== "done" && stage !== "error";

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
  const shouldOpenOrders = Boolean(result?.run.order_id || result?.run.live_preview_id);

  return (
    <div className="page-stack decision-page">
      <section className="decision-primary-panel">
        <div className="decision-copy">
          <span className="decision-eyebrow">
            <Sparkles size={15} />
            简单模式
          </span>
          <h2>一键生成交易决策</h2>
          <p>系统会自动扫描候选池、选择提案、运行会议、执行风控，然后只把最终结论和下一步动作展示出来。</p>
        </div>

        <form className="decision-action-box" onSubmit={runDecision}>
          <label>
            <span>本次最高金额</span>
            <input value={maxNotional} onChange={(event) => setMaxNotional(event.target.value)} inputMode="decimal" />
          </label>
          <button className="primary-action decision-main-action" type="submit" disabled={isRunning}>
            {isRunning ? <Loader2 size={18} className="spin-icon" /> : <Sparkles size={18} />}
            {isRunning ? "正在生成决策" : "一键生成决策"}
          </button>
          <details className="setup-help decision-advanced">
            <summary>高级输入</summary>
            <div className="setup-help-content">
              <section>
                <h4>候选池</h4>
                <p>默认只扫描常见美股和 ETF。需要扩大范围时，用逗号或换行分隔代码。</p>
                <textarea value={universe} onChange={(event) => setUniverse(event.target.value)} rows={4} />
              </section>
              <section>
                <h4>提案模型</h4>
                <label className="checkbox-row settings-checkbox">
                  <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
                  <span>已配置真实模型时优先使用模型提案，否则自动回退规则扫描。</span>
                </label>
              </section>
            </div>
          </details>
        </form>
      </section>

      {(isRunning || stage === "done" || stage === "error") && (
        <section className="panel decision-flow-panel" aria-live="polite">
          <div className="panel-heading">
            <div>
              <h3>运行进度</h3>
              <p>{stage === "done" ? "本次决策已经完成并写入记录。" : "系统正在按固定顺序处理，不需要额外操作。"}</p>
            </div>
            {stage === "done" && <StatusBadge value={result?.run.final_action ?? "HOLD"} tone={result?.run.final_action === "HOLD" ? "warn" : "ok"} />}
          </div>
          <div className="decision-flow">
            {stages.map((item, index) => {
              const completed = stage === "done" || (activeIndex > -1 && index < activeIndex);
              const active = item.key === stage;
              return (
                <div className={completed ? "decision-step completed" : active ? "decision-step active" : "decision-step"} key={item.key}>
                  <span>{completed ? <CheckCircle2 size={16} /> : active ? <Loader2 size={16} className="spin-icon" /> : index + 1}</span>
                  <div>
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </div>
                </div>
              );
            })}
          </div>
          {error && <div className="error-box decision-error">{error}</div>}
        </section>
      )}

      {result && (
        <section className="panel decision-result-panel">
          <div className="panel-heading">
            <div>
              <h3>最终结论</h3>
              <p>{result.selectedProposal.symbol} 已完成提案、会议、共识和风控记录。</p>
            </div>
            <div className="badge-row">
              <StatusBadge value={result.run.final_action} tone={result.run.final_action === "HOLD" ? "warn" : "ok"} />
              <StatusBadge value={riskApproved ? "approved" : "blocked"} tone={riskApproved ? "ok" : "danger"} />
            </div>
          </div>

          <div className="decision-result-grid">
            <div>
              <span>标的</span>
              <strong>{result.selectedProposal.symbol}</strong>
              <small>{displayValue(result.selectedProposal.asset_type)}</small>
            </div>
            <div>
              <span>会议动作</span>
              <strong>{displayValue(result.run.final_action)}</strong>
              <small>{result.run.consensus_reached ? "已达成共识" : "未达成共识"}</small>
            </div>
            <div>
              <span>风控结果</span>
              <strong>{riskApproved ? "通过" : "阻断或无需执行"}</strong>
              <small>{topRiskReason(result.conference)}</small>
            </div>
            <div>
              <span>订单状态</span>
              <strong>{orderOutcome(result)}</strong>
              <small>{result.run.live_preview_id ? "实盘仍需人工确认" : "模拟模式会直接记录结果"}</small>
            </div>
            <div>
              <span>模型用量</span>
              <strong>{tokenUsage ? `${tokenUsage.total_tokens.toLocaleString()} token` : "未记录"}</strong>
              <small>{tokenUsage?.estimated ? "含估算值" : tokenUsage ? "来自模型返回或统计" : "mock 或规则路径可能没有用量"}</small>
            </div>
            <div>
              <span>提案来源</span>
              <strong>{result.proposalRun.used_llm ? displayValue(result.proposalRun.llm_provider) : "规则扫描"}</strong>
              <small>候选 {result.proposalRun.candidate_count} 个，提案 {result.proposalRun.proposals.length} 个</small>
            </div>
          </div>

          <div className="decision-next-actions">
            <Link className="primary-action" to={`/conference/${result.run.conference_id}`}>
              查看详情 <ArrowRight size={16} />
            </Link>
            {shouldOpenOrders && (
              <Link className="secondary-action" to="/orders">
                <ClipboardList size={16} />
                查看订单
              </Link>
            )}
            <button className="secondary-action" type="button" onClick={reset}>
              <RefreshCcw size={16} />
              再生成一次
            </button>
          </div>
        </section>
      )}

      <section className="panel decision-safe-panel">
        <div>
          <ShieldCheck size={20} />
          <div>
            <h3>简单操作背后的保护</h3>
            <p>一键模式不会绕过会议、共识、风控和实盘确认。真实下单仍然必须到订单页人工确认。</p>
          </div>
        </div>
        <Link className="secondary-action" to="/settings">
          <Settings size={16} />
          设置
        </Link>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>需要手动控制时</h3>
            <p>高级入口仍然保留，用于检查提案、单独运行会议或复核订单。</p>
          </div>
        </div>
        <div className="decision-shortcuts">
          <Link to="/proposals">
            <Search size={18} />
            <strong>候选提案</strong>
            <span>查看和保留每次扫描结果</span>
          </Link>
          <Link to="/run">
            <Sparkles size={18} />
            <strong>运行会议</strong>
            <span>手动指定单个标的</span>
          </Link>
          <Link to="/orders">
            <ClipboardList size={18} />
            <strong>订单</strong>
            <span>确认实盘预览或查看模拟订单</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
