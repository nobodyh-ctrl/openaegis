/** Textos de los checks automáticos para la UI. Las claves son los check_id del backend (CHECKS en backend/checks.py). */
import type { CheckId } from "./api";

export const CHECK_INFO: Record<CheckId, { label: string; description: string }> = {
  "s3-account-public-access-block": {
    label: "S3 Block Public Access (cuenta)",
    description: "Las 4 opciones de Block Public Access activadas a nivel cuenta.",
  },
  "s3-bucket-public-access-block": {
    label: "S3 Block Public Access (cada bucket)",
    description: "Cada bucket protegido por su propio Block Public Access o por el de la cuenta.",
  },
  "s3-bucket-tls-only": {
    label: "S3 solo TLS (cada bucket)",
    description: "La bucket policy rechaza las conexiones sin HTTPS (aws:SecureTransport=false).",
  },
  "cloudtrail-multi-region-logging": {
    label: "CloudTrail multi-región",
    description: "Al menos un trail multi-región que esté registrando eventos.",
  },
  "iam-root-mfa": {
    label: "MFA del usuario root",
    description: "El usuario root de la cuenta tiene MFA activado.",
  },
};

/** Etiqueta de un check_id. Si el backend agrega un check que la SPA no conoce, se muestra el id tal cual. */
export function checkLabel(checkId: string): string {
  return CHECK_INFO[checkId as CheckId]?.label ?? checkId;
}
