"""Checks de seguridad de SOLO LECTURA. No importa boto3: recibe los clientes ya creados.

Cada check recibe un ScanContext y devuelve una lista de resultados, uno por recurso:
    {"resource_id": ..., "status": "PASS" | "FAIL" | "ERROR", "evidence": ...}
No sabe de DynamoDB ni de HTTP: check → finding → reporte se mantienen separados.
"""

from dataclasses import dataclass
from typing import Callable

# resource_id de los checks que evalúan la cuenta entera. No se guarda el ID real de la cuenta.
ACCOUNT_RESOURCE = "account"
# resource_id cuando el check no se pudo correr (por ejemplo, un check_id que no existe)
CHECK_RESOURCE = "check"


@dataclass(frozen=True)
class ScanContext:
    client: Callable[[str], object]  # client("s3control") → cliente de boto3 (o uno falso en los tests)
    account_id: str


def _result(resource_id, status, evidence):
    return {"resource_id": resource_id, "status": status, "evidence": evidence}


def _error_code(err):
    """Código del error de AWS (AccessDenied, Throttling…). Nunca el mensaje: puede traer ARNs con el ID de la cuenta."""
    return err.response.get("Error", {}).get("Code", "desconocido")


# --- s3-account-public-access-block ------------------------------------------

BPA_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def s3_account_public_access_block(ctx):
    """Las 4 opciones de S3 Block Public Access activadas a nivel CUENTA (protegen a todos los buckets)."""
    s3control = ctx.client("s3control")
    try:
        response = s3control.get_public_access_block(AccountId=ctx.account_id)
    # El orden importa: NoSuchPublicAccessBlockConfiguration es una subclase de ClientError
    except s3control.exceptions.NoSuchPublicAccessBlockConfiguration:
        return [_result(ACCOUNT_RESOURCE, "FAIL", "Block Public Access no está configurado a nivel cuenta.")]
    except s3control.exceptions.ClientError as err:
        return [_result(ACCOUNT_RESOURCE, "ERROR", f"No se pudo leer la configuración: {_error_code(err)}.")]

    config = response["PublicAccessBlockConfiguration"]
    disabled = [flag for flag in BPA_FLAGS if not config.get(flag, False)]
    if disabled:
        return [_result(ACCOUNT_RESOURCE, "FAIL", "Desactivadas: " + ", ".join(disabled) + ".")]
    return [_result(ACCOUNT_RESOURCE, "PASS", "Las 4 opciones de Block Public Access están activadas.")]


# --- Registro: check_id (el que guarda el control, D92) → función ------------

CHECKS = {
    "s3-account-public-access-block": s3_account_public_access_block,
}


def run_checks(controls, ctx):
    """Corre el check de cada control automático (los que tienen check_id).
    Retorna los findings: el resultado de cada recurso + control_id + check_id."""
    findings = []
    for control in controls:
        check_id = control["check_id"]
        check = CHECKS.get(check_id)
        if check is None:
            results = [_result(CHECK_RESOURCE, "ERROR", f"No existe un check '{check_id}'.")]
        else:
            results = check(ctx)
        findings.extend({"control_id": control["id"], "check_id": check_id, **r} for r in results)
    return findings


def control_status(statuses):
    """Status de un control automático a partir de los de sus findings (D94).
    Un FAIL manda; un ERROR (o no tener findings) deja el control en REVIEW: no se pudo confirmar que cumple."""
    if "FAIL" in statuses:
        return "FAIL"
    if "ERROR" in statuses or not statuses:
        return "REVIEW"
    return "PASS"
