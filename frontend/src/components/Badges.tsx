import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { displayValue } from "../lib/format";

export function StatusBadge({
  value,
  tone = "neutral"
}: {
  value: string;
  tone?: "neutral" | "ok" | "warn" | "danger";
}) {
  return <span className={`badge badge-${tone}`}>{displayValue(value)}</span>;
}

export function HealthBadge({ healthy }: { healthy: boolean }) {
  const Icon = healthy ? CheckCircle2 : XCircle;
  return (
    <span className={`badge ${healthy ? "badge-ok" : "badge-danger"}`}>
      <Icon size={14} />
      {healthy ? "正常" : "受阻"}
    </span>
  );
}

export function KillSwitchBadge({ enabled }: { enabled: boolean }) {
  return (
    <span className={`badge ${enabled ? "badge-danger" : "badge-ok"}`}>
      <ShieldAlert size={14} />
      {enabled ? "实盘已开启" : "实盘已关闭"}
    </span>
  );
}
