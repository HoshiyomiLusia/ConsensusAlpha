import { useQuery } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { api } from "../api/client";
import { displayValue } from "../lib/format";

export default function PositionsPage() {
  const positions = useQuery({ queryKey: ["positions"], queryFn: api.positions });

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>持仓</h2>
          <p>当前数据源返回并映射后的券商持仓。</p>
        </div>
        <button className="icon-button" title="刷新持仓" onClick={() => positions.refetch()}>
          <RefreshCcw size={18} />
        </button>
      </section>
      <section className="panel">
        <div className="table">
          <div className="table-header table-positions">
            <span>标的</span>
            <span>资产</span>
            <span>数量</span>
            <span>均价</span>
            <span>市值</span>
          </div>
          {(positions.data ?? []).map((position) => (
            <div className="table-row table-positions" key={position.symbol}>
              <strong>{position.symbol}</strong>
              <span>{displayValue(position.asset_type)}</span>
              <span>{position.quantity}</span>
              <span>{position.average_price}</span>
              <span>{position.market_value}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
