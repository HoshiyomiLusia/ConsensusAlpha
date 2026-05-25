import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, RefreshCcw, ShieldCheck, X } from "lucide-react";
import { api, LivePreview } from "../api/client";
import { StatusBadge } from "../components/Badges";
import { displayValue, formatSettingKey } from "../lib/format";

export default function OrdersPage() {
  const queryClient = useQueryClient();
  const paperOrders = useQuery({ queryKey: ["paper-orders"], queryFn: api.paperOrders, refetchInterval: 20_000 });
  const livePreviews = useQuery({ queryKey: ["live-previews"], queryFn: api.livePreviews, refetchInterval: 20_000 });
  const readiness = useQuery({ queryKey: ["production-readiness"], queryFn: api.productionReadiness, refetchInterval: 30_000 });
  const [confirming, setConfirming] = useState<LivePreview | null>(null);

  const reject = useMutation({
    mutationFn: api.rejectLivePreview,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["live-previews"] })
  });

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>订单</h2>
          <p>查看模拟成交和受保护的实盘订单预览。</p>
        </div>
        <button className="icon-button" onClick={() => readiness.refetch()} title="刷新上线检查">
          <RefreshCcw size={18} />
        </button>
      </section>

      <section className={readiness.data?.ready ? "panel readiness-panel readiness-ok" : "panel readiness-panel readiness-blocked"}>
        <div className="panel-heading">
          <div>
            <h3>真实交易上线状态</h3>
            <p>实盘确认前必须通过这些门禁；模拟订单不受影响。</p>
          </div>
          <StatusBadge value={readiness.data?.ready ? "已通过" : "未通过"} tone={readiness.data?.ready ? "ok" : "danger"} />
        </div>
        {readiness.data && (
          <div className="readiness-summary">
            <span>
              <ShieldCheck size={16} />
              阻断项 {readiness.data.checks.filter((check) => check.severity === "blocker" && !check.passed).length} 个
            </span>
            <span>
              <AlertTriangle size={16} />
              警告项 {readiness.data.checks.filter((check) => check.severity === "warning" && !check.passed).length} 个
            </span>
          </div>
        )}
        {readiness.data && !readiness.data.ready && (
          <details className="setup-help readiness-details">
            <summary>查看阻断项</summary>
            <div className="readiness-list">
              {readiness.data.checks
                .filter((check) => !check.passed)
                .map((check) => (
                  <div className="check-row" key={check.name}>
                    <StatusBadge value={check.severity === "warning" ? "警告" : "阻断"} tone={check.severity === "warning" ? "warn" : "danger"} />
                    <div>
                      <strong>{formatSettingKey(check.name)}</strong>
                      <span>{check.summary}</span>
                    </div>
                  </div>
                ))}
            </div>
          </details>
        )}
      </section>

      <section className="panel">
        <h3>实盘预览</h3>
        <div className="table">
          <div className="table-header table-orders">
            <span>标的</span>
            <span>方向</span>
            <span>数量</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {(livePreviews.data ?? []).map((preview) => (
            <LivePreviewRow
              key={preview.preview_id}
              preview={preview}
              productionReady={Boolean(readiness.data?.ready)}
              onConfirm={setConfirming}
              onReject={(previewId) => reject.mutate(previewId)}
            />
          ))}
        </div>
      </section>

      <section className="panel">
        <h3>模拟订单</h3>
        <div className="table">
          <div className="table-header table-paper">
            <span>标的</span>
            <span>方向</span>
            <span>数量</span>
            <span>成交价</span>
            <span>状态</span>
          </div>
          {(paperOrders.data ?? []).map((order) => (
            <div className="table-row table-paper" key={order.order_id}>
              <strong>{order.symbol}</strong>
              <span>{displayValue(order.side)}</span>
              <span>{order.quantity}</span>
              <span>{order.fill_price}</span>
              <StatusBadge value={order.status} tone="ok" />
            </div>
          ))}
        </div>
      </section>

      {confirming && <ConfirmModal preview={confirming} onClose={() => setConfirming(null)} />}
    </div>
  );
}

function LivePreviewRow({
  preview,
  productionReady,
  onConfirm,
  onReject
}: {
  preview: LivePreview;
  productionReady: boolean;
  onConfirm: (preview: LivePreview) => void;
  onReject: (previewId: string) => void;
}) {
  const productionBlocked = preview.environment === "production" && !productionReady;
  const disabled = preview.status !== "PENDING_CONFIRMATION" || productionBlocked;
  return (
    <div className="table-row table-orders">
      <strong>{preview.symbol}</strong>
      <span>{displayValue(preview.side)}</span>
      <span>{preview.quantity}</span>
      <StatusBadge value={preview.status} tone={preview.status === "PENDING_CONFIRMATION" ? "warn" : "ok"} />
      <div className="row-actions">
        <button
          className="icon-button"
          title={productionBlocked ? "真实交易上线检查未通过" : "确认实盘预览"}
          disabled={disabled}
          onClick={() => onConfirm(preview)}
        >
          <Check size={16} />
        </button>
        <button
          className="icon-button"
          title="拒绝实盘预览"
          disabled={preview.status !== "PENDING_CONFIRMATION"}
          onClick={() => onReject(preview.preview_id)}
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}

function ConfirmModal({ preview, onClose }: { preview: LivePreview; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [ack, setAck] = useState(false);
  const [productionText, setProductionText] = useState("");
  const confirm = useMutation({
    mutationFn: () =>
      api.confirmLivePreview(preview.preview_id, {
        acknowledge_live_risk: ack,
        production_confirmation_text: productionText || null,
        confirm_symbol: preview.symbol,
        confirm_side: preview.side,
        confirm_quantity: preview.quantity,
        confirm_order_type: preview.order_type,
        confirm_estimated_notional: preview.estimated_notional ?? "",
        confirm_account_id: preview.account_id,
        confirm_environment: preview.environment
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["live-previews"] });
      onClose();
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    confirm.mutate();
  }

  const expected = `CONFIRM ${preview.symbol} ${preview.side} ${preview.quantity} ${preview.order_type} ${preview.estimated_notional ?? "UNKNOWN"} ${preview.account_id} ${preview.environment}`;

  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={submit}>
        <h3>确认实盘订单</h3>
        <div className="kv-grid">
          <span>标的</span><strong>{preview.symbol}</strong>
          <span>方向</span><strong>{displayValue(preview.side)}</strong>
          <span>数量</span><strong>{preview.quantity}</strong>
          <span>订单类型</span><strong>{displayValue(preview.order_type)}</strong>
          <span>名义金额</span><strong>{preview.estimated_notional ?? "无"}</strong>
          <span>环境</span><strong>{displayValue(preview.environment)}</strong>
          <span>账户</span><strong>{preview.account_id}</strong>
        </div>
        <label className="checkbox-row">
          <input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} />
          <span>我确认这可能会向券商提交实盘订单。</span>
        </label>
        {preview.environment === "production" && (
          <>
            <div className="warning-box">这是真实资金环境。请逐项核对标的、方向、数量、订单类型、金额、账户和环境，再输入完整确认文本。</div>
            <label>
              <span>真实交易确认文本</span>
              <small className="field-help">{expected}</small>
              <input value={productionText} onChange={(event) => setProductionText(event.target.value)} placeholder={expected} />
            </label>
          </>
        )}
        {confirm.error && <div className="error-box">{confirm.error.message}</div>}
        <div className="modal-actions">
          <button type="button" className="secondary-action" onClick={onClose}>取消</button>
          <button type="submit" className="danger-action" disabled={confirm.isPending}>确认下单</button>
        </div>
      </form>
    </div>
  );
}
