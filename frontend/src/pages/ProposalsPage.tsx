import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Lightbulb, RefreshCcw, Search } from "lucide-react";
import { ProposalRunPayload, api } from "../api/client";
import { StatusBadge } from "../components/Badges";

const defaultUniverse = "SPY, QQQ, AAPL, MSFT, NVDA, TSLA, META, AMZN, GOOGL";

export default function ProposalsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [symbols, setSymbols] = useState(defaultUniverse);
  const [maxProposals, setMaxProposals] = useState("3");
  const [maxNotional, setMaxNotional] = useState("1000");
  const [useLlm, setUseLlm] = useState(true);
  const recent = useQuery({ queryKey: ["proposals"], queryFn: api.proposals });
  const selectedRunId = searchParams.get("run");
  const detail = useQuery({
    queryKey: ["proposal", selectedRunId],
    queryFn: () => api.proposal(selectedRunId || ""),
    enabled: Boolean(selectedRunId)
  });

  const mutation = useMutation({
    mutationFn: (payload: ProposalRunPayload) => api.runProposals(payload),
    onSuccess: (result) => {
      setSearchParams({ run: result.proposal_run_id });
      recent.refetch();
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate({
      symbols: symbols.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
      max_proposals: Number(maxProposals),
      max_notional: maxNotional,
      use_llm: useLlm
    });
  }

  const result = detail.data ?? mutation.data;

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>候选提案</h2>
          <p>先扫描候选池，再由提案模型挑选少量标的提交会议。</p>
        </div>
        <button className="icon-button" onClick={() => recent.refetch()} title="刷新提案记录">
          <RefreshCcw size={18} />
        </button>
      </section>

      <form className="form-grid proposal-form" onSubmit={submit}>
        <label>
          <span>候选池</span>
          <textarea value={symbols} onChange={(event) => setSymbols(event.target.value)} rows={4} />
        </label>
        <label>
          <span>最大提案数</span>
          <input value={maxProposals} onChange={(event) => setMaxProposals(event.target.value)} inputMode="numeric" />
        </label>
        <label>
          <span>建议会议金额</span>
          <input value={maxNotional} onChange={(event) => setMaxNotional(event.target.value)} inputMode="decimal" />
        </label>
        <label className="checkbox-row settings-checkbox">
          <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
          <span>启用提案模型</span>
        </label>
        <details className="setup-help form-help">
          <summary>提案流程说明</summary>
          <div className="setup-help-content">
            <section>
              <h4>候选池</h4>
              <p>用逗号或换行分隔股票/ETF 代码。系统会先拉取这些标的的行情快照，而不是扫描全市场。</p>
            </section>
            <section>
              <h4>规则扫描</h4>
              <p>后端先用涨跌幅、日内区间、成交量等摘要做排序，缩小要交给模型阅读的范围。</p>
            </section>
            <section>
              <h4>提案模型</h4>
              <p>如果已配置真实模型，会让模型基于扫描摘要生成候选提案；否则自动回退为规则提案。</p>
            </section>
            <section>
              <h4>提交会议</h4>
              <p>提案不会下单。点击提交会议后，仍会走现有多 Agent 共识、确定性风控和订单预览流程。</p>
            </section>
          </div>
        </details>
        <div className="form-actions">
          <button className="primary-action" type="submit" disabled={mutation.isPending}>
            <Search size={17} />
            {mutation.isPending ? "扫描中" : "扫描候选并生成提案"}
          </button>
          <span className="inline-note">
            <Lightbulb size={16} />
            提案只负责提名，不负责执行。
          </span>
        </div>
        {mutation.error && <div className="error-box">{mutation.error.message}</div>}
      </form>

      {result && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>提案批次</h3>
              <p>{result.message}</p>
              <p>{result.proposal_run_id}</p>
            </div>
            <div className="badge-row">
              <StatusBadge value={result.used_llm ? "LLM" : "RULES"} tone={result.used_llm ? "ok" : "warn"} />
              <StatusBadge value={result.llm_provider.toUpperCase()} />
            </div>
          </div>
          <div className="proposal-grid">
            {result.proposals.map((proposal) => (
              <article className="proposal-card" key={`${result.proposal_run_id}-${proposal.symbol}`}>
                <div className="proposal-card-heading">
                  <div>
                    <strong>{proposal.symbol}</strong>
                    <span>{proposal.asset_type === "etf" ? "ETF" : "美股"} · 分数 {proposal.scan_score.toFixed(2)}</span>
                  </div>
                  <StatusBadge value={proposal.proposed_action} tone={proposal.proposed_action === "HOLD" ? "warn" : "ok"} />
                </div>
                <p>{proposal.thesis}</p>
                {proposal.risks.length > 0 && (
                  <ul>
                    {proposal.risks.map((risk) => (
                      <li key={risk}>{risk}</li>
                    ))}
                  </ul>
                )}
                <Link
                  className="primary-action"
                  to={`/run?symbol=${proposal.symbol}&asset_type=${proposal.asset_type}&max_notional=${proposal.suggested_max_notional}&proposal_run_id=${result.proposal_run_id}&mock_agent_action=${proposal.proposed_action}`}
                >
                  提交会议 <ArrowRight size={16} />
                </Link>
              </article>
            ))}
          </div>
        </section>
      )}

      {result && (
        <section className="panel">
          <h3>该批次会议记录</h3>
          {detail.data?.conferences.length ? (
            <div className="table">
              <div className="table-header table-proposal-conferences">
                <span>标的</span>
                <span>动作</span>
                <span>共识</span>
                <span>风控</span>
                <span>创建时间</span>
              </div>
              {detail.data.conferences.map((conference) => (
                <Link className="table-row table-proposal-conferences" to={`/conference/${conference.conference_id}`} key={conference.conference_id}>
                  <strong>{conference.symbol}</strong>
                  <StatusBadge value={conference.final_action} tone={conference.final_action === "HOLD" ? "warn" : "ok"} />
                  <span>{conference.consensus_reached ? "已达成" : "未达成"}</span>
                  <span>{conference.risk_approved === null ? "未检查" : conference.risk_approved ? "通过" : "阻断"}</span>
                  <span>{new Date(conference.created_at).toLocaleString()}</span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-state">这个提案批次还没有关联会议。点击任一提案的“提交会议”后会在这里留存记录。</div>
          )}
        </section>
      )}

      {result && (
        <section className="panel">
          <h3>扫描摘要</h3>
          <div className="table">
            <div className="table-header table-proposals">
              <span>标的</span>
              <span>涨跌幅</span>
              <span>日内区间</span>
              <span>成交量</span>
              <span>分数</span>
            </div>
            {result.scanned.map((item) => (
              <div className="table-row table-proposals" key={item.symbol}>
                <strong>{item.symbol}</strong>
                <span>{(item.change_pct * 100).toFixed(2)}%</span>
                <span>{(item.intraday_range_pct * 100).toFixed(2)}%</span>
                <span>{item.volume?.toLocaleString() ?? "无"}</span>
                <span>{item.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <h3>最近提案记录</h3>
        <div className="table">
          <div className="table-header table-proposal-runs">
            <span>提案数</span>
            <span>候选数</span>
            <span>来源</span>
            <span>创建时间</span>
          </div>
          {(recent.data ?? []).map((item) => (
            <Link className="table-row table-proposal-runs" to={`/proposals?run=${item.proposal_run_id}`} key={item.proposal_run_id}>
              <strong>{item.proposal_count}</strong>
              <span>{item.candidate_count}</span>
              <span>{item.used_llm ? item.llm_provider : "规则"}</span>
              <span>{new Date(item.created_at).toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
