import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { api } from "../api/client";
import { StatusBadge } from "../components/Badges";
import { formatReason, formatRiskCheckName, formatRole } from "../lib/format";

export default function ConferenceDetailPage() {
  const { conferenceId } = useParams();
  const detail = useQuery({
    queryKey: ["conference", conferenceId],
    queryFn: () => api.conference(conferenceId ?? ""),
    enabled: Boolean(conferenceId)
  });

  if (detail.isLoading) return <div className="panel">正在加载会议...</div>;
  if (detail.error) return <div className="error-box">{detail.error.message}</div>;
  if (!detail.data) return null;

  const run = detail.data;
  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>{run.symbol} 会议</h2>
          <p>{run.conference_id}</p>
        </div>
        <StatusBadge
          value={run.consensus_result.final_action}
          tone={run.consensus_result.final_action === "HOLD" ? "warn" : "ok"}
        />
      </section>

      <section className="detail-grid">
        <div className="panel">
          <h3>行情快照</h3>
          {run.snapshot && (
            <div className="kv-grid">
              <span>价格</span>
              <strong>{run.snapshot.price}</strong>
              <span>来源</span>
              <strong>{run.snapshot.source}</strong>
              <span>成交量</span>
              <strong>{run.snapshot.volume ?? "无"}</strong>
              <span>时间戳</span>
              <strong>{new Date(run.snapshot.timestamp).toLocaleString()}</strong>
            </div>
          )}
        </div>
        <div className="panel">
          <h3>共识结果</h3>
          <div className="kv-grid">
            <span>是否达成</span>
            <strong>{run.consensus_result.consensus_reached ? "是" : "否"}</strong>
            <span>原因</span>
            <strong>{formatReason(run.consensus_result.consensus_reason)}</strong>
            <span>完成时间</span>
            <strong>{new Date(run.consensus_result.completed_at).toLocaleString()}</strong>
          </div>
        </div>
        <div className="panel">
          <h3>模型用量</h3>
          {run.model_usage ? (
            <div className="kv-grid">
              <span>总 Token</span>
              <strong>{run.model_usage.total_tokens.toLocaleString()}</strong>
              <span>输入 Token</span>
              <strong>{run.model_usage.prompt_tokens.toLocaleString()}</strong>
              <span>输出 Token</span>
              <strong>{run.model_usage.completion_tokens.toLocaleString()}</strong>
              <span>统计方式</span>
              <strong>{run.model_usage.estimated ? "估算" : "模型返回"}</strong>
            </div>
          ) : (
            <div className="empty-state">没有模型用量记录。</div>
          )}
        </div>
      </section>

      <section className="panel">
        <h3>Agent 意见</h3>
        <div className="agent-grid">
          {run.opinions.map((opinion) => (
            <article className="agent-card" key={`${opinion.role}-${opinion.agent_id}`}>
              <div className="panel-heading">
                <div>
                  <h4>{formatRole(opinion.role)}</h4>
                  <p>
                    {opinion.agent_id}
                    {opinion.prompt_version ? ` / ${opinion.prompt_version}` : ""}
                  </p>
                </div>
                <StatusBadge value={opinion.action} tone={opinion.action === "HOLD" ? "warn" : "ok"} />
              </div>
              <p>{opinion.thesis}</p>
              <div className="confidence">
                <span style={{ width: `${opinion.confidence * 100}%` }} />
              </div>
              {opinion.concerns.length > 0 && <small>关注点：{opinion.concerns.join(", ")}</small>}
              {opinion.blocking_concerns.length > 0 && (
                <small className="danger-text">阻断项：{opinion.blocking_concerns.join(", ")}</small>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <h3>风控检查</h3>
        <div className="check-list">
          {(run.risk_decision?.checks ?? []).map((check) => {
            const Icon = check.passed ? CheckCircle2 : XCircle;
            return (
              <div className="check-row" key={check.name}>
                <Icon size={18} className={check.passed ? "ok-text" : "danger-text"} />
                <div>
                  <strong>{formatRiskCheckName(check.name)}</strong>
                  <span>{formatReason(check.reason)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {run.model_usage && run.model_usage.events.length > 0 && (
        <section className="panel">
          <h3>模型调用明细</h3>
          <div className="table">
            <div className="table-header table-model-usage">
              <span>角色</span>
              <span>操作</span>
              <span>模型</span>
              <span>Prompt</span>
              <span>输入</span>
              <span>输出</span>
              <span>总计</span>
            </div>
            {run.model_usage.events.map((event, index) => (
              <div className="table-row table-model-usage" key={`${event.role}-${event.operation}-${index}`}>
                <strong>{formatRole(event.role)}</strong>
                <span>{event.operation === "summary" ? "总结" : "意见"}</span>
                <span>{event.provider}{event.model ? ` / ${event.model}` : ""}</span>
                <span>{event.prompt_version || "未记录"}</span>
                <span>{event.prompt_tokens.toLocaleString()}</span>
                <span>{event.completion_tokens.toLocaleString()}</span>
                <span>{event.total_tokens.toLocaleString()}{event.estimated ? " 估算" : ""}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <h3>审计时间线</h3>
        <div className="timeline">
          <div><Clock size={16} /> 行情快照已记录</div>
          <div><Clock size={16} /> Agent 意见已保存</div>
          <div><Clock size={16} /> 共识已评估</div>
          <div><Clock size={16} /> 风控决策已保存</div>
          <div><Clock size={16} /> {run.order_result ? "模拟订单已成交" : run.live_preview ? "实盘预览待确认" : "未生成订单"}</div>
        </div>
      </section>
    </div>
  );
}
