/** Severidad y estado con los componentes de la consola: color + texto (nunca solo color). */
import Badge from "@cloudscape-design/components/badge";
import StatusIndicator, { type StatusIndicatorProps } from "@cloudscape-design/components/status-indicator";
import Box from "@cloudscape-design/components/box";
import type { FindingStatus, Severity, Status } from "@/lib/api";

const SEVERITY: Record<Severity, { label: string; color: "severity-critical" | "severity-high" | "severity-medium" | "severity-low" }> = {
  CRITICAL: { label: "Crítica", color: "severity-critical" },
  HIGH: { label: "Alta", color: "severity-high" },
  MEDIUM: { label: "Media", color: "severity-medium" },
  LOW: { label: "Baja", color: "severity-low" },
};

const STATUS: Record<Status, { label: string; type: StatusIndicatorProps.Type }> = {
  PASS: { label: "Cumple", type: "success" },
  REVIEW: { label: "A revisar", type: "warning" },
  FAIL: { label: "No cumple", type: "error" },
};

/** Orden para listar: lo más grave primero. */
export const SEVERITY_ORDER: Record<Severity, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export const severityLabel = (s: Severity) => SEVERITY[s].label;
export const statusLabel = (s: Status) => STATUS[s].label;

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge color={SEVERITY[severity].color}>{SEVERITY[severity].label}</Badge>;
}

export function StatusBadge({ status }: { status: Status }) {
  return <StatusIndicator type={STATUS[status].type}>{STATUS[status].label}</StatusIndicator>;
}

const FINDING: Record<FindingStatus, { label: string; type: StatusIndicatorProps.Type }> = {
  PASS: { label: "Cumple", type: "success" },
  FAIL: { label: "No cumple", type: "error" },
  // ámbar, como REVIEW: un ERROR es justamente lo que deja al control "A revisar"
  ERROR: { label: "No se pudo evaluar", type: "warning" },
};

export function FindingBadge({ status }: { status: FindingStatus }) {
  return <StatusIndicator type={FINDING[status].type}>{FINDING[status].label}</StatusIndicator>;
}

/** Automático (lo evalúa un check en cada scan) o manual (el estado lo pone una persona). */
export function EvaluationBadge({ checkId }: { checkId?: string }) {
  return checkId ? <Badge color="blue">Automático</Badge> : <Box color="text-body-secondary">Manual</Box>;
}
