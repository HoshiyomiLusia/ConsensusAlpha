import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, Check, ClipboardCheck, RefreshCcw, ShieldCheck, WalletCards, X } from "lucide-react";
import { api, LivePreview, PaperOrder, Settings } from "../api/client";
import { StatusBadge } from "../components/Badges";
import { displayValue, formatSettingKey } from "../lib/format";

export default function OrdersPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings, staleTime: 30_000 });
  const paperOrders = useQuery({ queryKey: ["paper-orders"], queryFn: api.paperOrders, refetchInterval: 20_000 });
  const livePreviews = useQuery({ queryKey: ["live-previews"], queryFn: api.livePreviews, refetchInterval: 20_000 });
  const readiness = useQuery({ queryKey: ["production-readiness"], queryFn: api.productionReadiness, refetchInterval: 30_000 });
  const [confirming, setConfirming] = useState<LivePreview | null>(null);

  const reject = useMutation({
    mutationFn: api.rejectLivePreview,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["live-previews"] })
  });
  const previewList = livePreviews.data ?? [];
  const pendingPreviews = previewList.filter((preview) => preview.status === "PENDING_CONFIRMATION");
  const paperOrderList = paperOrders.data ?? [];

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>订单</h2>
          <p>先确认订单预览，再查看已经成交的模拟订单。</p>
        </div>
        <button className="icon-button" onClick={() => readiness.refetch()} title="刷新上线检查">
          <RefreshCcw size={18} />
        </button>
      </section>

      <OrderGuidePanel pendingPreviews={pendingPreviews} paperOrders={paperOrderList} onConfirm={setConfirming} />
      <OrderModePanel settings={settings.data} readiness={readiness.data} />

      <section className="panel" id="order-previews">
        <h3>待确认预览</h3>
        <div className="table">
          <div className="table-header table-orders">
            <span>标的</span>
            <span>方向</span>
            <span>数量</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {previewList.length === 0 && <div className="empty-state">没有订单预览。回到简单模式运行一次自动决策即可生成。</div>}
          {previewList.map((preview) => (
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
          {paperOrderList.length === 0 && <div className="empty-state">还没有模拟成交订单。回到简单模式运行一次自动决策即可生成。</div>}
          {paperOrderList.map((order) => (
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

function OrderGuidePanel({
  pendingPreviews,
  paperOrders,
  onConfirm
}: {
  pendingPreviews: LivePreview[];
  paperOrders: PaperOrder[];
  onConfirm: (preview: LivePreview) => void;
}) {
  const firstPreview = pendingPreviews[0];
  const latestPaperOrder = paperOrders[0];

  if (firstPreview) {
    const modeLabel = firstPreview.mode === "paper" ? "模拟" : "实盘";
    return (
      <section className="panel order-guide order-guide-pending">
        <div className="order-guide-main">
          <span>下一步</span>
          <h3>核对订单预览，然后确认或拒绝</h3>
          <p>
            当前有 {pendingPreviews.length} 个预览等待处理。先看标的、方向、数量、金额和模式；认可就确认，不认可就拒绝。
          </p>
        </div>
        <div className="order-guide-focus">
          <strong>{firstPreview.symbol}</strong>
          <span>{modeLabel} · {displayValue(firstPreview.side)} · {firstPreview.quantity} 股 · {firstPreview.estimated_notional ?? "金额待估算"}</span>
        </div>
        <div className="order-guide-actions">
          <button className="primary-action" type="button" onClick={() => onConfirm(firstPreview)}>
            <ClipboardCheck size={16} />
            确认这笔订单
          </button>
          <a className="secondary-action" href="#order-previews">查看全部预览</a>
        </div>
      </section>
    );
  }

  if (latestPaperOrder) {
    return (
      <section className="panel order-guide order-guide-done">
        <div className="order-guide-main">
          <span>下一步</span>
          <h3>模拟订单已成交</h3>
          <p>
            最近一笔是 {latestPaperOrder.symbol} {displayValue(latestPaperOrder.side)}，这是你确认后的纸面成交。接下来主要看持仓变化，或者回到简单模式生成下一轮决策。
          </p>
        </div>
        <div className="order-guide-actions">
          <Link className="primary-action" to="/positions">
            <WalletCards size={16} />
            查看持仓
          </Link>
          <Link className="secondary-action" to="/">继续自动决策</Link>
        </div>
      </section>
    );
  }

  return (
    <section className="panel order-guide">
      <div className="order-guide-main">
        <span>下一步</span>
        <h3>现在没有订单要处理</h3>
        <p>如果刚才的会议结论是观望，或者风控没有通过，这里不会生成订单。需要新的决策时回到简单模式重新运行。</p>
      </div>
      <div className="order-guide-actions">
        <Link className="primary-action" to="/">回到自动决策</Link>
      </div>
    </section>
  );
}

function OrderModePanel({
  settings,
  readiness
}: {
  settings?: Settings;
  readiness?: Awaited<ReturnType<typeof api.productionReadiness>>;
}) {
  const isLiveMode = Boolean(settings?.trading_mode === "live" && settings.enable_live_trading);
  const isProductionCapital = Boolean(settings?.app_env?.toLowerCase() === "production" || settings?.webull_env === "production");
  const showProductionGate = isLiveMode || isProductionCapital;
  const failedChecks = readiness?.checks.filter((check) => !check.passed) ?? [];
  const blockerCount = failedChecks.filter((check) => check.severity === "blocker").length;
  const warningCount = failedChecks.filter((check) => check.severity === "warning").length;

  if (!showProductionGate) {
    return (
      <section className="panel readiness-panel readiness-test">
        <div className="panel-heading">
          <div>
            <h3>测试环境可用</h3>
            <p>当前用于模拟数据和纸面交易测试；真实资金上线检查不会阻断这个流程。</p>
          </div>
          <StatusBadge value="可测试" tone="ok" />
        </div>
        <div className="readiness-summary">
          <span>
            <ShieldCheck size={16} />
            数据：{settings?.broker_provider === "webull" ? "真实数据通道" : "模拟数据"}
          </span>
          <span>
            <ShieldCheck size={16} />
            执行：纸面交易
          </span>
        </div>
        {readiness && (
          <details className="setup-help readiness-details">
            <summary>真实交易上线检查</summary>
            <p className="readiness-note">这些项目只用于判断能不能接入真实资金交易。测试 mock、UAT 和纸面订单时不用处理。</p>
            <ReadinessList failedChecks={failedChecks} />
          </details>
        )}
      </section>
    );
  }

  return (
    <section className={readiness?.ready ? "panel readiness-panel readiness-ok" : "panel readiness-panel readiness-blocked"}>
      <div className="panel-heading">
        <div>
          <h3>真实交易上线状态</h3>
          <p>只有真实资金订单需要通过这些门禁；模拟订单不受影响。</p>
        </div>
        <StatusBadge value={readiness?.ready ? "已通过" : "未通过"} tone={readiness?.ready ? "ok" : "danger"} />
      </div>
      {readiness && (
        <div className="readiness-summary">
          <span>
            <ShieldCheck size={16} />
            阻断项 {blockerCount} 个
          </span>
          <span>
            <AlertTriangle size={16} />
            警告项 {warningCount} 个
          </span>
        </div>
      )}
      {readiness && !readiness.ready && (
        <details className="setup-help readiness-details">
          <summary>查看真实交易阻断项</summary>
          <ReadinessList failedChecks={failedChecks} />
        </details>
      )}
    </section>
  );
}

function ReadinessList({
  failedChecks
}: {
  failedChecks: Awaited<ReturnType<typeof api.productionReadiness>>["checks"];
}) {
  if (failedChecks.length === 0) {
    return <p className="readiness-note">没有未通过项目。</p>;
  }

  return (
    <div className="readiness-list">
      {failedChecks.map((check) => (
        <div className="check-row" key={check.name}>
          <StatusBadge value={check.severity === "warning" ? "警告" : "阻断"} tone={check.severity === "warning" ? "warn" : "danger"} />
          <div>
            <strong>{formatSettingKey(check.name)}</strong>
            <span>{check.summary}</span>
          </div>
        </div>
      ))}
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
  const modeLabel = preview.mode === "paper" ? "模拟" : "实盘";
  return (
    <div className="table-row table-orders">
      <strong>{preview.symbol}</strong>
      <span>{modeLabel} · {displayValue(preview.side)}</span>
      <span>{preview.quantity}</span>
      <StatusBadge value={preview.status} tone={preview.status === "PENDING_CONFIRMATION" ? "warn" : "ok"} />
      <div className="row-actions">
        <button
          className="secondary-action order-row-button"
          title={productionBlocked ? "真实交易上线检查未通过" : "确认订单预览"}
          disabled={disabled}
          onClick={() => onConfirm(preview)}
        >
          <Check size={16} />
          确认
        </button>
        <button
          className="secondary-action order-row-button danger"
          title="拒绝订单预览"
          disabled={preview.status !== "PENDING_CONFIRMATION"}
          onClick={() => onReject(preview.preview_id)}
        >
          <X size={16} />
          拒绝
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
      await queryClient.invalidateQueries({ queryKey: ["paper-orders"] });
      await queryClient.invalidateQueries({ queryKey: ["positions"] });
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
        <h3>{preview.mode === "paper" ? "确认模拟订单" : "确认实盘订单"}</h3>
        <div className="kv-grid">
          <span>标的</span><strong>{preview.symbol}</strong>
          <span>方向</span><strong>{displayValue(preview.side)}</strong>
          <span>数量</span><strong>{preview.quantity}</strong>
          <span>订单类型</span><strong>{displayValue(preview.order_type)}</strong>
          <span>名义金额</span><strong>{preview.estimated_notional ?? "无"}</strong>
          <span>模式</span><strong>{preview.mode === "paper" ? "模拟交易" : "实盘交易"}</strong>
          <span>环境</span><strong>{displayValue(preview.environment)}</strong>
          <span>账户</span><strong>{preview.account_id}</strong>
        </div>
        <label className="checkbox-row">
          <input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} />
          <span>{preview.mode === "paper" ? "我确认执行这笔模拟订单。" : "我确认这可能会向券商提交实盘订单。"}</span>
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
          <button type="submit" className={preview.mode === "paper" ? "primary-action" : "danger-action"} disabled={confirm.isPending}>确认下单</button>
        </div>
      </form>
    </div>
  );
}
