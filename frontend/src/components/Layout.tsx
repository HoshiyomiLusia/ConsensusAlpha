import { NavLink, Outlet } from "react-router-dom";
import { Activity, Boxes, ClipboardList, Gauge, Lightbulb, ScrollText, Settings, Sparkles, WalletCards } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { HealthBadge, KillSwitchBadge, StatusBadge } from "./Badges";

const links = [
  { to: "/", label: "决策中心", icon: Sparkles },
  { to: "/dashboard", label: "总览", icon: Gauge },
  { to: "/proposals", label: "候选提案", icon: Lightbulb },
  { to: "/run", label: "运行会议", icon: Activity },
  { to: "/orders", label: "订单", icon: ClipboardList },
  { to: "/positions", label: "持仓", icon: WalletCards },
  { to: "/audit", label: "审计", icon: ScrollText },
  { to: "/settings", label: "设置", icon: Settings }
];

export default function Layout() {
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
              <NavLink key={link.to} to={link.to} className={({ isActive }) => (isActive ? "active" : "")}>
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
            <h1>交易研究控制台</h1>
            <p>共识会议、确定性风控和受保护执行。</p>
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
