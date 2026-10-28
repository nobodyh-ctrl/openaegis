import { useMemo } from "react";
import BarChart from "@cloudscape-design/components/bar-chart";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Grid from "@cloudscape-design/components/grid";
import Header from "@cloudscape-design/components/header";
import Icon, { type IconProps } from "@cloudscape-design/components/icon";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import Link from "@cloudscape-design/components/link";
import PieChart from "@cloudscape-design/components/pie-chart";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import Table from "@cloudscape-design/components/table";
import { SEVERITY_ORDER, SeverityBadge, severityLabel, StatusBadge, statusLabel } from "@/components/controls/badges";
import { SEVERITIES, STATUSES, type Control, type Severity, type Status } from "@/lib/api";
import { useFollow } from "@/lib/navigation";
import { useNotifications } from "@/lib/notifications";
import { computeScore } from "@/lib/score";
import { useControls } from "@/lib/use-controls";
import { useLatestScan, useStartScan } from "@/lib/use-scans";

/** Colores semánticos de los gráficos (D71): verde cumple, ámbar a revisar, rojo no cumple. */
const STATUS_COLOR: Record<Status, string> = { PASS: "#16a34a", REVIEW: "#d97706", FAIL: "#dc2626" };
const relative = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

function timeAgo(iso: string) {
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}

function computeStats(items: Control[]) {
  const byStatus = Object.fromEntries(STATUSES.map((s) => [s, 0])) as Record<Status, number>;
  const matrix = Object.fromEntries(SEVERITIES.map((sev) => [sev, Object.fromEntries(STATUSES.map((s) => [s, 0]))])) as Record<Severity, Record<Status, number>>;
  for (const c of items) {
    byStatus[c.status] += 1;
    matrix[c.severity][c.status] += 1;
  }
  const failing = items
    .filter((c) => c.status === "FAIL")
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || a.code.localeCompare(b.code));
  const recent = [...items].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);
  const criticalOpen = items.filter((c) => c.status !== "PASS" && (c.severity === "CRITICAL" || c.severity === "HIGH")).length;
  return { total: items.length, byStatus, matrix, failing, recent, criticalOpen, score: computeScore(items) };
}

function Kpi({ label, value, hint, icon, variant, href, follow }: {
  label: string; value: string | number; hint: string; icon: IconProps.Name;
  variant: IconProps.Variant; href: string; follow: ReturnType<typeof useFollow>;
}) {
  return (
    <Container fitHeight>
      <SpaceBetween size="xxs">
        <Box variant="awsui-key-label"><Icon name={icon} variant={variant} /> {label}</Box>
        <Link variant="awsui-value-large" href={href} onFollow={follow} ariaLabel={`${label}: ${value}`}>{value}</Link>
        <Box variant="small" color="text-body-secondary">{hint}</Box>
      </SpaceBetween>
    </Container>
  );
}

/** Último scan + botón para correr uno nuevo. Los contadores son de FINDINGS (uno por recurso), no de controles. */
function LatestScan() {
  const { data: scan, isPending, error } = useLatestScan();
  const startScan = useStartScan();
  const { notify } = useNotifications();

  const run = () =>
    startScan.mutate(undefined, {
      onSuccess: (s) => notify("success", `Scan terminado: ${s.pass_count} findings cumplen, ${s.fail_count} no cumplen y ${s.error_count} no se pudieron evaluar.`),
      onError: (err) => notify("error", `Scan: ${err.message}`),
    });

  return (
    <Container
      header={
        <Header
          variant="h2"
          description="Los checks de solo lectura evalúan la cuenta y actualizan el estado de los controles automáticos."
          actions={<Button variant="primary" iconName="security" loading={startScan.isPending} onClick={run}>{startScan.isPending ? "Escaneando…" : "Escanear"}</Button>}
        >
          Último scan
        </Header>
      }
    >
      {isPending && <Spinner />}
      {error && <Box color="text-status-error">No se pudo cargar el último scan: {error.message}</Box>}
      {!isPending && !error && !scan && <Box color="text-body-secondary">Todavía no se corrió ningún scan.</Box>}
      {scan && (
        <KeyValuePairs
          columns={4}
          items={[
            { label: "Cuándo", value: timeAgo(scan.finished_at) },
            { label: "Controles evaluados", value: scan.controls_evaluated },
            {
              label: "Findings",
              info: <Box variant="small" color="text-body-secondary">uno por recurso</Box>,
              value: (
                <SpaceBetween direction="horizontal" size="s">
                  <span><Icon name="status-positive" variant="success" /> {scan.pass_count}</span>
                  <span><Icon name="status-negative" variant="error" /> {scan.fail_count}</span>
                  <span><Icon name="status-warning" variant="warning" /> {scan.error_count}</span>
                </SpaceBetween>
              ),
            },
            { label: "Duración", value: `${Math.max(0, Math.round((Date.parse(scan.finished_at) - Date.parse(scan.started_at)) / 1000))} s` },
          ]}
        />
      )}
    </Container>
  );
}

export function DashboardPage() {
  const { data, isPending, error, refetch } = useControls();
  const follow = useFollow();
  const s = useMemo(() => computeStats(data?.items ?? []), [data]);
  const scoreText = s.score.value === null ? "–" : `${s.score.value}%`;

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Estado de tus controles de seguridad: los automáticos los evalúa el scanner; los manuales, vos."
          actions={<Button iconName="add-plus" href="/app/controles/nuevo" onFollow={follow}>Nuevo control</Button>}
        >
          Dashboard
        </Header>
      }
    >
      {isPending && <Box textAlign="center" padding="xxl"><Spinner size="large" /></Box>}

      {error && (
        <Container>
          <Box textAlign="center">
            <SpaceBetween size="xs">
              <b>No se pudo cargar el resumen</b>
              <Box variant="p">{error.message}</Box>
              <Button onClick={() => void refetch()}>Reintentar</Button>
            </SpaceBetween>
          </Box>
        </Container>
      )}

      {data && (
        <SpaceBetween size="l">
          <LatestScan />

          <ColumnLayout columns={4}>
            <Kpi label="Score de seguridad" value={scoreText} hint={`Ponderado por severidad (crítica ×8, alta ×4, media ×2, baja ×1). ${s.score.automatic} de ${s.total} controles verificados por checks.`} icon="status-positive" variant="success" href="/app/controles" follow={follow} />
            <Kpi label="No cumplen" value={s.byStatus.FAIL} hint="Requieren corrección" icon="status-negative" variant="error" href="/app/controles?estado=FAIL" follow={follow} />
            <Kpi label="A revisar" value={s.byStatus.REVIEW} hint="Pendientes de evaluar" icon="status-warning" variant="warning" href="/app/controles?estado=REVIEW" follow={follow} />
            <Kpi label="Críticos y altos abiertos" value={s.criticalOpen} hint="Severidad crítica o alta sin cumplir" icon="security" variant="link" href="/app/controles" follow={follow} />
          </ColumnLayout>

          <Grid gridDefinition={[{ colspan: { default: 12, s: 5 } }, { colspan: { default: 12, s: 7 } }]}>
            <Container fitHeight header={<Header variant="h2" description="Proporción de controles por estado.">Distribución por estado</Header>}>
              <PieChart
                variant="donut"
                size="medium"
                hideFilter
                hideTitles
                hideDescriptions
                data={STATUSES.map((st) => ({ title: statusLabel(st), value: s.byStatus[st], color: STATUS_COLOR[st] }))}
                innerMetricValue={`${s.byStatus.PASS}/${s.total}`}
                innerMetricDescription="cumplen"
                ariaLabel="Distribución de controles por estado"
                ariaDescription={STATUSES.map((st) => `${statusLabel(st)}: ${s.byStatus[st]}`).join(", ")}
                segmentDescription={(d, sum) => `${d.value} controles (${sum ? Math.round((d.value / sum) * 100) : 0}%)`}
                empty={<Box textAlign="center" color="inherit">Sin controles</Box>}
              />
            </Container>

            <Container fitHeight header={<Header variant="h2" description="Cuántos controles hay de cada severidad y en qué estado.">Por severidad</Header>}>
              <BarChart
                stackedBars
                hideFilter
                height={220}
                xScaleType="categorical"
                xDomain={SEVERITIES.slice().reverse().map(severityLabel)}
                series={STATUSES.map((st) => ({
                  title: statusLabel(st),
                  type: "bar" as const,
                  color: STATUS_COLOR[st],
                  data: SEVERITIES.slice().reverse().map((sev) => ({ x: severityLabel(sev), y: s.matrix[sev][st] })),
                }))}
                yTickFormatter={(v) => (Number.isInteger(v) ? String(v) : "")}
                xTitle="Severidad"
                yTitle="Controles"
                ariaLabel="Controles por severidad y estado"
                empty={<Box textAlign="center" color="inherit">Sin controles</Box>}
              />
            </Container>
          </Grid>

          <Grid gridDefinition={[{ colspan: { default: 12, s: 6 } }, { colspan: { default: 12, s: 6 } }]}>
            <Table
              variant="container"
              header={
                <Header
                  variant="h2"
                  counter={`(${s.failing.length})`}
                  description="Controles que no cumplen, por severidad."
                  actions={<Button href="/app/controles?estado=FAIL" onFollow={follow}>Ver todos</Button>}
                >
                  Para resolver primero
                </Header>
              }
              items={s.failing.slice(0, 5)}
              trackBy="id"
              columnDefinitions={[
                { id: "code", header: "Código", cell: (c) => <Link href={`/app/controles/${c.id}/editar`} onFollow={follow}>{c.code}</Link>, width: 110 },
                { id: "title", header: "Control", cell: (c) => c.title },
                { id: "severity", header: "Severidad", cell: (c) => <SeverityBadge severity={c.severity} />, width: 110 },
              ]}
              empty={<Box textAlign="center" color="inherit" padding="s"><Icon name="status-positive" variant="success" /> Ningún control marcado como "No cumple".</Box>}
            />

            <Table
              variant="container"
              header={<Header variant="h2" description="Últimos controles modificados.">Actividad reciente</Header>}
              items={s.recent}
              trackBy="id"
              columnDefinitions={[
                { id: "code", header: "Código", cell: (c) => <Link href={`/app/controles/${c.id}/editar`} onFollow={follow}>{c.code}</Link>, width: 110 },
                { id: "status", header: "Estado", cell: (c) => <StatusBadge status={c.status} /> },
                { id: "when", header: "Cuándo", cell: (c) => timeAgo(c.updated_at), width: 130 },
              ]}
              empty={<Box textAlign="center" color="inherit" padding="s">Sin actividad.</Box>}
            />
          </Grid>
        </SpaceBetween>
      )}
    </ContentLayout>
  );
}
