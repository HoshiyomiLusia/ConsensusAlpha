import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Loader2, Play, ShieldCheck } from "lucide-react";
import { Action, RunConferencePayload, api } from "../api/client";
import { StatusBadge } from "../components/Badges";

const symbolOptions = [
  { symbol: "AAPL", label: "Apple" },
  { symbol: "MSFT", label: "Microsoft" },
  { symbol: "NVDA", label: "NVIDIA" },
  { symbol: "TSLA", label: "Tesla" },
  { symbol: "SPY", label: "S&P 500 ETF" },
  { symbol: "QQQ", label: "Nasdaq 100 ETF" },
  { symbol: "IWM", label: "Russell 2000 ETF" },
  { symbol: "DIA", label: "Dow ETF" }
];

const runSteps = ["获取行情与账户", "Agent 会议分析", "共识判断", "风控检查", "生成订单结果"];

export default function RunConference() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState(searchParams.get("symbol") ?? "AAPL");
  const [assetType, setAssetType] = useState<"equity" | "etf">(
    searchParams.get("asset_type") === "etf" ? "etf" : "equity"
  );
  const [maxNotional, setMaxNotional] = useState(searchParams.get("max_notional") ?? "1000");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [limitPrice, setLimitPrice] = useState("");
  const initialMockAction = searchParams.get("mock_agent_action");
  const [mockAction, setMockAction] = useState<Action | "">(
    initialMockAction === "BUY" || initialMockAction === "SELL" || initialMockAction === "HOLD"
      ? initialMockAction
      : ""
  );
  const proposalRunId = searchParams.get("proposal_run_id");

  const mutation = useMutation({
    mutationFn: (payload: RunConferencePayload) => api.runConference(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["conferences"] }),
        queryClient.invalidateQueries({ queryKey: ["orders", "paper"] }),
        queryClient.invalidateQueries({ queryKey: ["live-previews"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] }),
        queryClient.invalidateQueries({ queryKey: ["proposals"] }),
        proposalRunId ? queryClient.invalidateQueries({ queryKey: ["proposal", proposalRunId] }) : Promise.resolve()
      ]);
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.reset();
    mutation.mutate({
      symbol: symbol.trim().toUpperCase(),
      asset_type: assetType,
      max_notional: maxNotional,
      order_type: orderType,
      limit_price: orderType === "LIMIT" ? limitPrice : null,
      mock_agent_action: mockAction || null,
      proposal_run_id: proposalRunId
    });
  }

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>运行会议</h2>
          <p>触发一次 Agent 分析、共识判断、风控检查和执行路由。</p>
          {proposalRunId && <p>来源：候选提案批次 {proposalRunId}</p>}
          {proposalRunId && mockAction && <p>已按提案方向预设 mock 投票：{mockAction}</p>}
        </div>
      </section>
      <form className="form-grid" onSubmit={submit}>
        <label>
          <span>标的代码</span>
          <input list="symbol-options" value={symbol} onChange={(event) => setSymbol(event.target.value)} required />
          <datalist id="symbol-options">
            {symbolOptions.map((option) => (
              <option key={option.symbol} value={option.symbol}>
                {option.label}
              </option>
            ))}
          </datalist>
          <div className="symbol-quick-list" aria-label="常用标的">
            {symbolOptions.map((option) => (
              <button
                key={option.symbol}
                type="button"
                className={symbol.toUpperCase() === option.symbol ? "symbol-chip active" : "symbol-chip"}
                onClick={() => {
                  setSymbol(option.symbol);
                  setAssetType(option.symbol in { SPY: true, QQQ: true, IWM: true, DIA: true } ? "etf" : "equity");
                }}
                title={option.label}
              >
                {option.symbol}
              </button>
            ))}
          </div>
        </label>
        <label>
          <span>资产类型</span>
          <select value={assetType} onChange={(event) => setAssetType(event.target.value as "equity" | "etf")}>
            <option value="equity">美股</option>
            <option value="etf">美股 ETF</option>
          </select>
        </label>
        <label>
          <span>最大名义金额</span>
          <input value={maxNotional} onChange={(event) => setMaxNotional(event.target.value)} inputMode="decimal" />
        </label>
        <label>
          <span>订单类型</span>
          <select value={orderType} onChange={(event) => setOrderType(event.target.value as "MARKET" | "LIMIT")}>
            <option value="MARKET">市价</option>
            <option value="LIMIT">限价</option>
          </select>
        </label>
        {orderType === "LIMIT" && (
          <label>
            <span>限价价格</span>
            <input value={limitPrice} onChange={(event) => setLimitPrice(event.target.value)} inputMode="decimal" />
          </label>
        )}
        <label>
          <span>模拟投票覆盖</span>
          <select value={mockAction} onChange={(event) => setMockAction(event.target.value as Action | "")}>
            <option value="">默认混合投票</option>
            <option value="BUY">强制买入</option>
            <option value="SELL">强制卖出</option>
            <option value="HOLD">强制观望</option>
          </select>
        </label>
        <details className="setup-help form-help">
          <summary>配置项说明</summary>
          <div className="setup-help-content">
            <section>
              <h4>标的代码</h4>
              <p>要分析和可能交易的股票或 ETF 代码，例如 AAPL、MSFT、SPY。可以手动输入，也可以点击常用标的快捷项；提交时会自动转成大写。</p>
            </section>
            <section>
              <h4>资产类型</h4>
              <p>当前项目实盘范围限定为美股和美股 ETF。这里会影响行情查询、订单意图和后续风控记录。</p>
            </section>
            <section>
              <h4>最大名义金额</h4>
              <p>本次会议允许使用的最高交易金额。系统会用它和行情价格计算数量，并在风控里检查仓位和单笔风险。</p>
            </section>
            <section>
              <h4>订单类型</h4>
              <p>市价表示按当前可成交价格执行；限价表示只接受你填写的限价价格。实盘模式下仍然只会先生成订单预览。</p>
            </section>
            <section>
              <h4>限价价格</h4>
              <p>只有选择限价时才需要填写。它会进入订单意图和实盘预览，不会绕过共识或风控。</p>
            </section>
            <section>
              <h4>模拟投票覆盖</h4>
              <p>只用于 mock Agent 测试。默认混合投票会制造分歧；强制买入、卖出或观望用于测试共识通过、风控阻断和订单流程。</p>
            </section>
          </div>
        </details>
        <div className="form-actions">
          <button className="primary-action" type="submit" disabled={mutation.isPending}>
            <Play size={17} />
            {mutation.isPending ? "运行中" : "运行会议"}
          </button>
          <span className="inline-note">
            <ShieldCheck size={16} />
            实盘订单需要单独预览并人工确认。
          </span>
        </div>
        {mutation.error && <div className="error-box">会议运行失败：{mutation.error.message}</div>}
      </form>

      {mutation.isPending && (
        <section className="panel run-feedback" aria-live="polite">
          <div className="panel-heading">
            <div>
              <h3>会议正在运行</h3>
              <p>系统正在按固定流程读取数据、生成 Agent 意见、判断共识并执行风控。</p>
            </div>
            <span className="badge badge-warn">
              <Loader2 size={14} className="spin-icon" />
              处理中
            </span>
          </div>
          <div className="run-step-grid">
            {runSteps.map((step) => (
              <div className="run-step" key={step}>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {mutation.data && !mutation.isPending && (
        <section className="panel run-feedback" aria-live="polite">
          <div className="panel-heading">
            <div>
              <h3>会议运行完成</h3>
              <p>结果已经写入会议记录；下一步可以进入详情页查看 Agent 意见、共识和风控检查。</p>
            </div>
            <StatusBadge value={mutation.data.final_action} tone={mutation.data.final_action === "HOLD" ? "warn" : "ok"} />
          </div>
          <div className="review-grid">
            <div>
              <span>会议编号</span>
              <strong>{mutation.data.conference_id}</strong>
            </div>
            <div>
              <span>标的</span>
              <strong>{mutation.data.symbol}</strong>
            </div>
            <div>
              <span>共识结果</span>
              <strong>{mutation.data.consensus_reached ? "已达成共识" : "未达成共识"}</strong>
            </div>
            <div>
              <span>风控结果</span>
              <strong>{mutation.data.risk_approved ? "通过" : "未通过或无需执行"}</strong>
            </div>
            <div>
              <span>订单结果</span>
              <strong>
                {mutation.data.order_id
                  ? `已生成模拟订单 ${mutation.data.order_id}`
                  : mutation.data.live_preview_id
                    ? `已生成订单预览 ${mutation.data.live_preview_id}`
                    : "未生成订单"}
              </strong>
            </div>
            <div>
              <span>后续动作</span>
              <strong>{mutation.data.live_preview_id ? "进入订单页人工确认" : "查看会议详情"}</strong>
            </div>
          </div>
          <div className="form-actions run-result-actions">
            <Link className="primary-action" to={`/conference/${mutation.data.conference_id}`}>
              查看会议详情 <ArrowRight size={16} />
            </Link>
            {proposalRunId && (
              <Link className="secondary-action" to={`/proposals?run=${proposalRunId}`}>
                返回提案批次
              </Link>
            )}
            <span className="inline-note">
              <CheckCircle2 size={16} />
              当前页面已保留结果摘要，不会自动跳转。
            </span>
          </div>
        </section>
      )}
    </div>
  );
}
