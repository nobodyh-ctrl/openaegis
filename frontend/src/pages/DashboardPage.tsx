import { useMemo } from "react";
import { ArrowRight, CheckCircle2, ListChecks, RotateCw, SearchCheck, XCircle, type LucideIcon } from "lucide-react";
import { Link } from "react-router";
import { SEVERITY_ORDER, SeverityBadge, severityLabel, statusLabel } from "@/components/controls/badges";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SEVERITIES, STATUSES, type Control, type Severity, type Status } from "@/lib/api";
import { useControls } from "@/lib/use-controls";
import { cn } from "@/lib/utils";

/** Totales calculados en el cliente a partir de GET /controls (mismos datos que la página de Controles). */
function computeStats(items: Control[]) {
  const byStatus = Object.fromEntries(STATUSES.map((s) => [s, 0])) as Record<Status, number>;
  const bySeverity = Object.fromEntries(SEVERITIES.map((s) => [s, { total: 0, fail: 0 }])) as Record<Severity, { total: number; fail: number }>;
  for (const c of items) {
    byStatus[c.status] += 1;
    bySeverity[c.severity].total += 1;
    if (c.status === "FAIL") bySeverity[c.severity].fail += 1;
  }
  const failing = items
    .filter((c) => c.status === "FAIL")
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || a.code.localeCompare(b.code));
  const compliance = items.length ? Math.round((byStatus.PASS / items.length) * 100) : 0;
  return { total: items.length, byStatus, bySeverity, failing, compliance };
}

const STATUS_CARD: Record<Status, { icon: LucideIcon; tone: string }> = {
  PASS: { icon: CheckCircle2, tone: "text-emerald-600 dark:text-emerald-400" },
  REVIEW: { icon: SearchCheck, tone: "text-amber-600 dark:text-amber-400" },
  FAIL: { icon: XCircle, tone: "text-red-600 dark:text-red-400" },
};

const SEVERITY_BAR: Record<Severity, string> = {
  CRITICAL: "bg-red-500", HIGH: "bg-orange-500", MEDIUM: "bg-amber-500", LOW: "bg-slate-500",
};

function StatCard({ label, value, icon: Icon, tone, to }: { label: string; value: number | string; icon: LucideIcon; tone: string; to: string }) {
  return (
    <Link to={to} className="group rounded-xl border bg-card p-4 transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        {label}
        <Icon className={cn("size-4", tone)} aria-hidden="true" />
      </div>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
    </Link>
  );
}

export function DashboardPage() {
  const { data, isPending, error, refetch, isFetching } = useControls();
  const stats = useMemo(() => computeStats(data?.items ?? []), [data]);

  return (
    <>
      <PageHeader title="Dashboard" description="Resumen del estado declarado de los controles (manual; los checks automáticos llegan en la Etapa 11)." />

      {isPending && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Cargando resumen">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}

      {error && (
        <div role="alert" className="flex flex-col items-center gap-3 rounded-xl border p-10 text-center">
          <p className="font-medium">No se pudo cargar el resumen</p>
          <p className="text-sm text-muted-foreground">{error.message}</p>
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching}><RotateCw /> Reintentar</Button>
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Controles" value={stats.total} icon={ListChecks} tone="text-primary" to="/app/controles" />
            {STATUSES.map((s) => (
              <StatCard key={s} label={statusLabel(s)} value={stats.byStatus[s]} icon={STATUS_CARD[s].icon} tone={STATUS_CARD[s].tone} to={`/app/controles?estado=${s}`} />
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="rounded-xl border bg-card p-5" aria-labelledby="cumplimiento">
              <h2 id="cumplimiento" className="font-medium">Cumplimiento declarado</h2>
              <p className="mt-1 text-sm text-muted-foreground">Controles marcados como "Cumple" sobre el total.</p>
              <p className="mt-4 text-4xl font-semibold tabular-nums">{stats.compliance}%</p>
              <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-muted" role="img"
                aria-label={STATUSES.map((s) => `${statusLabel(s)}: ${stats.byStatus[s]}`).join(", ")}>
                <div className="bg-emerald-500" style={{ width: `${stats.total ? (stats.byStatus.PASS / stats.total) * 100 : 0}%` }} />
                <div className="bg-amber-500" style={{ width: `${stats.total ? (stats.byStatus.REVIEW / stats.total) * 100 : 0}%` }} />
                <div className="bg-red-500" style={{ width: `${stats.total ? (stats.byStatus.FAIL / stats.total) * 100 : 0}%` }} />
              </div>
              {/* Leyenda: el color nunca va solo (D71) */}
              <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {STATUSES.map((s) => (
                  <li key={s} className="flex items-center gap-1.5">
                    <span className={cn("size-2 rounded-full", { PASS: "bg-emerald-500", REVIEW: "bg-amber-500", FAIL: "bg-red-500" }[s])} aria-hidden="true" />
                    {statusLabel(s)}: <span className="tabular-nums text-foreground">{stats.byStatus[s]}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-xl border bg-card p-5" aria-labelledby="por-severidad">
              <h2 id="por-severidad" className="font-medium">Por severidad</h2>
              <ul className="mt-4 space-y-3">
                {SEVERITIES.slice().reverse().map((sev) => {
                  const { total, fail } = stats.bySeverity[sev];
                  return (
                    <li key={sev}>
                      <div className="flex justify-between text-sm">
                        <Link to={`/app/controles?severidad=${sev}`} className="hover:underline">{severityLabel(sev)}</Link>
                        <span className="tabular-nums text-muted-foreground">{total} · {fail} no cumplen</span>
                      </div>
                      <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
                        <div className={cn("h-full", SEVERITY_BAR[sev])} style={{ width: `${stats.total ? (total / stats.total) * 100 : 0}%` }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>

          <section className="rounded-xl border bg-card p-5" aria-labelledby="prioridad">
            <div className="flex items-center justify-between">
              <h2 id="prioridad" className="font-medium">Para resolver primero</h2>
              <Link to="/app/controles?estado=FAIL" className="flex items-center gap-1 text-sm text-primary hover:underline">
                Ver todos <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
            {stats.failing.length === 0 ? (
              <p className="mt-4 text-sm text-muted-foreground">Ningún control marcado como "No cumple".</p>
            ) : (
              <ul className="mt-3 divide-y">
                {stats.failing.slice(0, 5).map((c) => (
                  <li key={c.id} className="flex items-center gap-3 py-2.5">
                    <span className="w-20 shrink-0 font-mono text-xs text-muted-foreground">{c.code}</span>
                    <span className="min-w-0 flex-1 truncate text-sm">{c.title}</span>
                    <SeverityBadge severity={c.severity} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}
