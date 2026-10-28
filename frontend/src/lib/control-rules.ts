/**
 * Espejo de FIELD_RULES de backend/validation.py (D73). Solo sirve para AVISAR antes de enviar:
 * la validación que protege los datos es la del backend. Si cambian las reglas allá, cambian acá
 * (y en backend/openapi.yaml).
 */
import { CHECK_IDS, SEVERITIES, STATUSES, type CheckId, type ControlInput, type Severity, type Status } from "./api";

export type FieldName = keyof ControlInput;

export const FIELD_RULES: Record<FieldName, { label: string; required: boolean; maxLength?: number }> = {
  code: { label: "Código", required: true, maxLength: 20 },
  title: { label: "Título", required: true, maxLength: 200 },
  service: { label: "Servicio", required: true, maxLength: 50 },
  category: { label: "Categoría", required: true, maxLength: 100 },
  severity: { label: "Severidad", required: true },
  status: { label: "Estado", required: false },
  description: { label: "Descripción", required: false, maxLength: 2000 },
  remediation: { label: "Remediación", required: false, maxLength: 2000 },
  check_id: { label: "Cómo se evalúa", required: false },
};

/** Valores del formulario: todo texto (los selects también). */
export type ControlFormValues = Record<FieldName, string>;

export const EMPTY_FORM: ControlFormValues = {
  code: "", title: "", service: "", category: "", severity: "", status: "REVIEW", description: "", remediation: "", check_id: "",
};

export type FormErrors = Partial<Record<FieldName, string>>;

export function validateControlForm(values: ControlFormValues): FormErrors {
  const errors: FormErrors = {};
  for (const [field, rule] of Object.entries(FIELD_RULES) as [FieldName, (typeof FIELD_RULES)[FieldName]][]) {
    const value = values[field].trim();
    if (rule.required && !value) errors[field] = `${rule.label} es obligatorio.`;
    else if (rule.maxLength && value.length > rule.maxLength) errors[field] = `Máximo ${rule.maxLength} caracteres.`;
  }
  if (values.severity && !SEVERITIES.includes(values.severity as Severity)) errors.severity = "Severidad inválida.";
  if (values.status && !STATUSES.includes(values.status as Status)) errors.status = "Estado inválido.";
  if (values.check_id && !CHECK_IDS.includes(values.check_id as CheckId)) errors.check_id = "Check inválido.";
  return errors;
}

/**
 * Arma el body para la API: textos sin espacios en los bordes y opcionales vacíos omitidos.
 * Un control automático va SIN status: lo pone el scanner, y la API rechaza los dos juntos (400).
 */
export function toControlInput(values: ControlFormValues): ControlInput {
  const input: ControlInput = {
    code: values.code.trim(),
    title: values.title.trim(),
    service: values.service.trim(),
    category: values.category.trim(),
    severity: values.severity as Severity,
  };
  if (values.check_id) input.check_id = values.check_id as CheckId;
  else input.status = values.status as Status;
  if (values.description.trim()) input.description = values.description.trim();
  if (values.remediation.trim()) input.remediation = values.remediation.trim();
  return input;
}
