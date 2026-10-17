/** Colores semánticos (D71), siempre con texto e ícono: el color solo no alcanza. */
import { AlertOctagon, AlertTriangle, CheckCircle2, Info, SearchCheck, ShieldAlert, XCircle, type LucideIcon } from "lucide-react";
import type { Severity, Status } from "@/lib/api";
import { cn } from "@/lib/utils";

const BASE = "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap";

const SEVERITY: Record<Severity, { label: string; icon: LucideIcon; className: string }> = {
  CRITICAL: { label: "Crítica", icon: AlertOctagon, className: "border-red-500/30 bg-red-500/15 text-red-700 dark:text-red-300" },
  HIGH: { label: "Alta", icon: ShieldAlert, className: "border-orange-500/30 bg-orange-500/15 text-orange-700 dark:text-orange-300" },
  MEDIUM: { label: "Media", icon: AlertTriangle, className: "border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  LOW: { label: "Baja", icon: Info, className: "border-slate-500/30 bg-slate-500/15 text-slate-700 dark:text-slate-300" },
};

const STATUS: Record<Status, { label: string; icon: LucideIcon; className: string }> = {
  PASS: { label: "Cumple", icon: CheckCircle2, className: "border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  REVIEW: { label: "A revisar", icon: SearchCheck, className: "border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  FAIL: { label: "No cumple", icon: XCircle, className: "border-red-500/30 bg-red-500/15 text-red-700 dark:text-red-300" },
};

/** Orden para listar: lo más grave primero. */
export const SEVERITY_ORDER: Record<Severity, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export const severityLabel = (s: Severity) => SEVERITY[s].label;
export const statusLabel = (s: Status) => STATUS[s].label;

export function SeverityBadge({ severity }: { severity: Severity }) {
  const { label, icon: Icon, className } = SEVERITY[severity];
  return (
    <span className={cn(BASE, className)} title={severity}>
      <Icon className="size-3" aria-hidden="true" />
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const { label, icon: Icon, className } = STATUS[status];
  return (
    <span className={cn(BASE, className)} title={status}>
      <Icon className="size-3" aria-hidden="true" />
      {label}
    </span>
  );
}
