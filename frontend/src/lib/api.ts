/**
 * Cliente de la API (controles, scans y findings). Es el ÚNICO archivo del frontend que hace fetch():
 * el resto de la app llama a estas funciones y recibe datos tipados o un ApiError.
 * Espejo del contrato del backend (backend/validation.py y backend/controls.py).
 */

import { getAccessToken, reloginAfter401 } from "./auth";

export const SEVERITIES =["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export const STATUSES = ["PASS", "REVIEW", "FAIL"] as const;

/** Checks que existen en el backend (CHECKS de backend/checks.py). "" = control manual (D92). */
export const CHECK_IDS = [
  "s3-account-public-access-block",
  "s3-bucket-public-access-block",
  "s3-bucket-tls-only",
  "cloudtrail-multi-region-logging",
  "iam-root-mfa",
] as const;
/** ERROR = el check no pudo evaluar el recurso (por ejemplo, AccessDenied). */
export const FINDING_STATUSES = ["PASS", "FAIL", "ERROR"] as const;

export type Severity = (typeof SEVERITIES)[number];
export type Status = (typeof STATUSES)[number];
export type CheckId = (typeof CHECK_IDS)[number];
export type FindingStatus = (typeof FINDING_STATUSES)[number];

/** Un control tal como lo devuelve la API. */
export interface Control {
  id: string;
  code: string;
  title: string;
  service: string;
  category: string;
  severity: Severity;
  status: Status;
  description?: string;
  remediation?: string;
  /** Con un check, el status lo pone el scanner y no se edita a mano (D94). Vacío o ausente = manual. */
  check_id?: CheckId | "";
  created_at: string;
  updated_at: string;
}

/** Resultado de un check sobre UN recurso. Un control automático tiene uno por recurso evaluado. */
export interface Finding {
  control_id: string;
  check_id: string;
  /** ARN del recurso, o "account" / "root" en los checks de cuenta, o "check" si el check no corrió. */
  resource_id: string;
  status: FindingStatus;
  evidence: string;
  evaluated_at: string;
  scan_id: string;
}

/** Resumen de un scan. Los contadores cuentan FINDINGS, no controles. */
export interface Scan {
  started_at: string;
  finished_at: string;
  controls_evaluated: number;
  pass_count: number;
  fail_count: number;
  error_count: number;
  stale_deleted: number;
}

/** Body de POST /controls: lo que el usuario puede mandar (id y fechas los pone el servidor). */
export interface ControlInput {
  code: string;
  title: string;
  service: string;
  category: string;
  severity: Severity;
  status?: Status;
  description?: string;
  remediation?: string;
  check_id?: CheckId | "";
}

/** Body de PATCH /controls/{id}: cualquier subconjunto de los campos editables. */
export type ControlPatch = Partial<ControlInput>;

/** Error de la API con el status HTTP. status = 0 significa que la request ni siquiera llegó. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// En desarrollo: "/api" (mismo origen; el proxy de Vite reenvía a la API real).
// En producción: la URL real, inyectada al compilar con VITE_API_URL.
const BASE_URL = (import.meta.env.VITE_API_URL ?? "/api").replace(/\/$/, "");

/** El backend responde {"error": "..."}; API Gateway, {"message": "..."} (401, 403, 404 de ruta, 429, 500). */
function errorMessage(data: unknown, status: number): string {
  // 403 del authorizer: el token es válido pero no tiene el scope que exige la ruta.
  if (status === 403) return "No tenés permiso para esta acción.";
  if (data && typeof data === "object") {
    const body = data as Record<string, unknown>;
    if (typeof body.error === "string") return body.error;
    if (typeof body.message === "string") return body.message;
  }
  return `Error HTTP ${status}`;
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  // Etapa 9: el access token (no el ID token) identifica al usuario ante la API.
  // Con este header, hasta un GET dispara preflight de CORS (por eso la 9.2 agregó "authorization").
  const token = await getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    // fetch() solo lanza si no hubo respuesta: sin red, DNS, o un bloqueo de CORS del navegador
    throw new ApiError(0, "No se pudo conectar con la API.");
  }

  const data: unknown = await response.json().catch(() => null);
  // 401 = el authorizer no aceptó el token: login de nuevo. La página se va, así que no resolvemos.
  if (response.status === 401 && (await reloginAfter401())) return new Promise<never>(() => {});
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(data, response.status));
  }
  return data as T;
}

const controlPath = (id: string) => `/controls/${encodeURIComponent(id)}`;

export const api = {
  listControls: () => request<{ items: Control[]; count: number }>("/controls"),

  getControl: (id: string) => request<{ item: Control }>(controlPath(id)),

  createControl: (input: ControlInput) =>
    request<{ item: Control }>("/controls", { method: "POST", body: input }),

  updateControl: (id: string, patch: ControlPatch) =>
    request<{ item: Control }>(controlPath(id), { method: "PATCH", body: patch }),

  deleteControl: (id: string) => request<{ item: Control }>(controlPath(id), { method: "DELETE" }),

  /** 202: el scan corre en segundo plano (D93). El resultado se consulta con latestScan. */
  startScan: () => request<{ message: string }>("/scans", { method: "POST" }),

  /** item = null si nunca se corrió un scan. */
  latestScan: () => request<{ item: Scan | null }>("/scans/latest"),

  listFindings: (controlId: string) =>
    request<{ items: Finding[]; count: number }>(`/findings?control_id=${encodeURIComponent(controlId)}`),
};
