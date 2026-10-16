/**
 * Cliente de la API de controles. Es el ÚNICO archivo del frontend que hace fetch():
 * el resto de la app llama a estas funciones y recibe datos tipados o un ApiError.
 * Espejo del contrato del backend (backend/validation.py y backend/controls.py).
 */

export const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export const STATUSES = ["PASS", "REVIEW", "FAIL"] as const;

export type Severity = (typeof SEVERITIES)[number];
export type Status = (typeof STATUSES)[number];

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
  created_at: string;
  updated_at: string;
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

/** El backend responde {"error": "..."}; API Gateway, {"message": "..."} (404 de ruta, 429, 500). */
function errorMessage(data: unknown, status: number): string {
  if (data && typeof data === "object") {
    const body = data as Record<string, unknown>;
    if (typeof body.error === "string") return body.error;
    if (typeof body.message === "string") return body.message;
  }
  return `Error HTTP ${status}`;
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: init.method ?? "GET",
      // Content-Type solo si hay body: un GET sin headers extra es una "simple request" (sin preflight)
      headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    // fetch() solo lanza si no hubo respuesta: sin red, DNS, o un bloqueo de CORS del navegador
    throw new ApiError(0, "No se pudo conectar con la API.");
  }

  const data: unknown = await response.json().catch(() => null);
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
};
