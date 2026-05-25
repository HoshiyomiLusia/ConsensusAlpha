import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ClipboardList,
  Gauge,
  Lightbulb,
  ScrollText,
  Settings,
  ShieldCheck,
  WalletCards
} from "lucide-react";

const groups = [
  {
    title: "决策流程",
    description: "用于拆开查看默认首页自动完成的每一步。",
    tools: [
      { to: "/dashboard", label: "总览", detail: "查看会议、订单、持仓和审计概况", icon: Gauge },
      { to: "/proposals", label: "候选提案", detail: "单独扫描候选池并保留提案记录", icon: Lightbulb },
      { to: "/run", label: "手动会议", detail: "指定一个标的运行多 Agent 会议", icon: Activity }
    ]
  },
  {
    title: "执行与账户",
    description: "用于检查交易结果、实盘预览和账户状态。",
    tools: [
      { to: "/orders", label: "订单", detail: "确认实盘预览或查看模拟成交", icon: ClipboardList },
      { to: "/positions", label: "持仓", detail: "查看当前数据源返回的持仓", icon: WalletCards },
      { to: "/settings", label: "上线检查", detail: "检查真实交易开关和必要配置", icon: ShieldCheck }
    ]
  },
  {
    title: "系统记录",
    description: "用于排查、复盘和调整系统参数。",
    tools: [
      { to: "/audit", label: "审计", detail: "查看设置、会议和订单的时间线", icon: ScrollText },
      { to: "/setup", label: "初始化向导", detail: "重新走一遍必要配置", icon: Settings },
      { to: "/settings", label: "设置", detail: "调整数据源、模型、风控和访问保护", icon: Settings }
    ]
  }
];

export default function AdvancedPage() {
  return (
    <div className="page-stack advanced-page">
      <section className="advanced-intro">
        <div>
          <h2>高级页面</h2>
          <p>这些入口不是日常必需。默认首页已经会自动完成候选扫描、会议、风控和订单路由；这里只用于需要手动检查或调整时进入。</p>
        </div>
        <Link className="primary-action" to="/">
          回到简单模式 <ArrowRight size={16} />
        </Link>
      </section>

      {groups.map((group) => (
        <section className="advanced-section" key={group.title}>
          <div className="advanced-section-copy">
            <h3>{group.title}</h3>
            <p>{group.description}</p>
          </div>
          <div className="advanced-tool-grid">
            {group.tools.map((tool) => {
              const Icon = tool.icon;
              return (
                <Link className="advanced-tool" to={tool.to} key={`${group.title}-${tool.label}`}>
                  <Icon size={20} />
                  <div>
                    <strong>{tool.label}</strong>
                    <span>{tool.detail}</span>
                  </div>
                  <ArrowRight size={16} />
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
