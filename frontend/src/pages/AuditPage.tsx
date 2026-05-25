import { useQuery } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { api } from "../api/client";
import { StatusBadge } from "../components/Badges";
import { formatAuditAction } from "../lib/format";

export default function AuditPage() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: api.auditEvents, refetchInterval: 30_000 });

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>审计</h2>
          <p>自动记录关键操作，用于复盘设置变更、会议、提案和实盘确认。</p>
        </div>
        <button className="icon-button" onClick={() => audit.refetch()} title="刷新审计记录">
          <RefreshCcw size={18} />
        </button>
      </section>

      <section className="panel">
        <h3>最近操作</h3>
        {audit.isLoading && <div className="empty-state">正在加载审计记录...</div>}
        {audit.error && <div className="error-box">{audit.error.message}</div>}
        {!audit.isLoading && !audit.error && (audit.data ?? []).length === 0 && (
          <div className="empty-state">还没有审计记录。运行会议、保存设置或处理订单后会自动出现在这里。</div>
        )}
        {(audit.data ?? []).length > 0 && (
          <div className="audit-list">
            {(audit.data ?? []).map((event) => (
              <article className="audit-card" key={event.event_id}>
                <div className="audit-card-heading">
                  <div>
                    <strong>{event.summary}</strong>
                    <span>{new Date(event.created_at).toLocaleString()}</span>
                  </div>
                  <StatusBadge value={formatAuditAction(event.action)} />
                </div>
                <div className="audit-meta">
                  <span>操作者：{event.actor}</span>
                  <span>对象：{event.entity_type}{event.entity_id ? ` / ${event.entity_id}` : ""}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
