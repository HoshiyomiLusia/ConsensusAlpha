import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, RefreshCcw } from "lucide-react";
import { api } from "../api/client";
import MetricCard from "../components/MetricCard";
import { StatusBadge } from "../components/Badges";

export default function Dashboard() {
  const conferences = useQuery({
    queryKey: ["conferences"],
    queryFn: api.conferences,
    refetchInterval: 15_000
  });
  const paperOrders = useQuery({ queryKey: ["paper-orders"], queryFn: api.paperOrders });
  const livePreviews = useQuery({ queryKey: ["live-previews"], queryFn: api.livePreviews });
  const positions = useQuery({ queryKey: ["positions"], queryFn: api.positions });

  const latest = conferences.data?.[0];
  const pendingPreviews = livePreviews.data?.filter((preview) => preview.status === "PENDING_CONFIRMATION").length ?? 0;

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>总览</h2>
          <p>查看最新共识会议、执行状态和数据源状态。</p>
        </div>
        <button className="icon-button" onClick={() => conferences.refetch()} title="刷新总览">
          <RefreshCcw size={18} />
        </button>
      </section>

      <div className="metrics-grid">
        <MetricCard label="会议记录" value={String(conferences.data?.length ?? 0)} detail="最近保存的运行" />
        <MetricCard label="模拟订单" value={String(paperOrders.data?.length ?? 0)} detail="已成交模拟单" />
        <MetricCard label="订单预览" value={String(pendingPreviews)} detail="等待人工确认" />
        <MetricCard label="持仓" value={String(positions.data?.length ?? 0)} detail="当前数据源返回行数" />
      </div>

      {latest && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>最新会议</h3>
              <p>{latest.symbol}</p>
            </div>
            <StatusBadge
              value={latest.final_action}
              tone={latest.final_action === "HOLD" ? "warn" : "ok"}
            />
          </div>
          <div className="summary-row">
            <span>共识</span>
            <strong>{latest.consensus_reached ? "已达成" : "未达成"}</strong>
          </div>
          <Link className="text-link" to={`/conference/${latest.conference_id}`}>
            打开审计记录 <ArrowRight size={16} />
          </Link>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>最近运行</h3>
            <p>会议审计条目</p>
          </div>
          <Link className="primary-action" to="/run">
            运行会议
          </Link>
        </div>
        <div className="table">
          <div className="table-header table-run">
            <span>标的</span>
            <span>动作</span>
            <span>共识</span>
            <span>创建时间</span>
          </div>
          {(conferences.data ?? []).map((run) => (
            <Link className="table-row table-run" to={`/conference/${run.conference_id}`} key={run.conference_id}>
              <strong>{run.symbol}</strong>
              <StatusBadge value={run.final_action} tone={run.final_action === "HOLD" ? "warn" : "ok"} />
              <span>{run.consensus_reached ? "已达成" : "观望"}</span>
              <span>{new Date(run.created_at).toLocaleString()}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
