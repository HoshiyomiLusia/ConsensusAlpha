import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Boxes, Settings, SlidersHorizontal, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { HealthBadge, KillSwitchBadge, StatusBadge } from "./Badges";

const links = [
  { to: "/", label: "简单", icon: Sparkles },
  { to: "/advanced", label: "高级", icon: SlidersHorizontal },
  { to: "/settings", label: "设置", icon: Settings }
];

const advancedRoutePrefixes = ["/dashboard", "/proposals", "/run", "/orders", "/positions", "/audit", "/conference"];

function pageCopy(pathname: string): { title: string; description: string } {
  if (pathname.startsWith("/advanced")) {
    return { title: "高级功能", description: "按需查看详细流程、账户、订单和审计记录。" };
  }
  if (pathname.startsWith("/settings") || pathname.startsWith("/setup")) {
    return { title: "设置", description: "初始化配置、数据源、模型和风控参数。" };
  }
  if (pathname.startsWith("/orders")) {
    return { title: "订单", description: "确认订单预览或查看模拟订单。" };
  }
  if (pathname.startsWith("/positions")) {
    return { title: "持仓", description: "查看当前数据源返回的账户持仓。" };
  }
  if (pathname.startsWith("/proposals")) {
    return { title: "候选提案", description: "检查市场扫描和提案生成记录。" };
  }
  if (pathname.startsWith("/run")) {
    return { title: "手动会议", description: "指定单个标的运行会议。" };
  }
  if (pathname.startsWith("/audit")) {
    return { title: "审计", description: "复盘配置、会议和订单相关记录。" };
  }
  if (pathname.startsWith("/dashboard")) {
    return { title: "总览", description: "查看系统当前概况。" };
  }
  if (pathname.startsWith("/conference")) {
    return { title: "会议详情", description: "查看 Agent 意见、共识、风控和审计链路。" };
  }
  return { title: "简单决策", description: "默认只需要生成决策，然后按提示处理下一步。" };
}

function isAdvancedRoute(pathname: string): boolean {
  return advancedRoutePrefixes.some((prefix) => pathname.startsWith(prefix));
}

export default function Layout() {
  const location = useLocation();
  const copy = pageCopy(location.pathname);
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings, staleTime: 30_000 });
  const provider = useQuery({
    queryKey: ["provider-status"],
    queryFn: api.providerStatus,
    refetchInterval: 30_000
  });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Boxes size={24} />
          <div>
            <strong>ConsensusAlpha</strong>
            <span>运维控制台</span>
          </div>
        </div>
        <nav>
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  isActive ||
                  (link.to === "/advanced" && isAdvancedRoute(location.pathname)) ||
                  (link.to === "/settings" && location.pathname.startsWith("/setup"))
                    ? "active"
                    : ""
                }
              >
                <Icon size={18} />
                {link.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <h1>{copy.title}</h1>
            <p>{copy.description}</p>
          </div>
          <div className="topbar-badges">
            {provider.data && <HealthBadge healthy={provider.data.healthy} />}
            {settings.data && (
              <>
                <StatusBadge value={settings.data.broker_provider.toUpperCase()} />
                <StatusBadge
                  value={settings.data.webull_env.toUpperCase()}
                  tone={settings.data.webull_env === "production" ? "danger" : "warn"}
                />
                <StatusBadge
                  value={settings.data.trading_mode.toUpperCase()}
                  tone={settings.data.trading_mode === "live" ? "danger" : "ok"}
                />
                <KillSwitchBadge enabled={settings.data.enable_live_trading} />
              </>
            )}
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
