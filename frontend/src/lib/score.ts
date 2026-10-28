/**
 * Score de seguridad (paso 11.7): % de cumplimiento PONDERADO por severidad.
 * Un control crítico pesa 8 veces lo que uno bajo, así que arreglar lo grave sube mucho más el score.
 * REVIEW cuenta como "no cumple": sin evidencia de que cumple, no suma.
 * Se calcula en la SPA con GET /controls, así refleja también los cambios manuales sin esperar un scan.
 */
import type { Control, Severity } from "./api";

export const SEVERITY_WEIGHT: Record<Severity, number> = { CRITICAL: 8, HIGH: 4, MEDIUM: 2, LOW: 1 };

export interface Score {
  /** 0 a 100, redondeado. null si no hay controles (no es 0%: no hay nada que medir). */
  value: number | null;
  /** Controles automáticos: su estado sale de un check, no de lo que declaró una persona. */
  automatic: number;
  total: number;
}

export function computeScore(controls: Control[]): Score {
  let passed = 0;
  let total = 0;
  for (const c of controls) {
    total += SEVERITY_WEIGHT[c.severity];
    if (c.status === "PASS") passed += SEVERITY_WEIGHT[c.severity];
  }
  return {
    value: total ? Math.round((passed / total) * 100) : null,
    automatic: controls.filter((c) => c.check_id).length,
    total: controls.length,
  };
}
