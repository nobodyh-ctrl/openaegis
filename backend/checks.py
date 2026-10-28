"""Checks de seguridad de SOLO LECTURA. No importa boto3: recibe los clientes ya creados.

Cada check recibe un ScanContext y devuelve una lista de resultados, uno por recurso:
    {"resource_id": ..., "status": "PASS" | "FAIL" | "ERROR", "evidence": ...}
No sabe de DynamoDB ni de HTTP: check → finding → reporte se mantienen separados.
"""

import json
from dataclasses import dataclass
from typing import Callable

# resource_id de los checks que evalúan la cuenta entera. No se guarda el ID real de la cuenta.
ACCOUNT_RESOURCE = "account"
# resource_id cuando el check no se pudo correr (por ejemplo, un check_id que no existe)
CHECK_RESOURCE = "check"
# resource_id del usuario root de la cuenta
ROOT_RESOURCE = "root"


@dataclass(frozen=True)
class ScanContext:
    client: Callable[[str], object]  # client("s3control") → cliente de boto3 (o uno falso en los tests)
    account_id: str


def _result(resource_id, status, evidence):
    return {"resource_id": resource_id, "status": status, "evidence": evidence}


def _error_code(err):
    """Código del error de AWS (AccessDenied, Throttling…). Nunca el mensaje: puede traer ARNs con el ID de la cuenta."""
    return err.response.get("Error", {}).get("Code", "desconocido")


# --- S3 Block Public Access (cuenta y buckets) --------------------------------

BPA_FLAGS = ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")


def _disabled_flags(config):
    """Opciones de BPA desactivadas. Una opción ausente cuenta como desactivada."""
    return [flag for flag in BPA_FLAGS if not config.get(flag, False)]


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

    disabled = _disabled_flags(response["PublicAccessBlockConfiguration"])
    if disabled:
        return [_result(ACCOUNT_RESOURCE, "FAIL", "Desactivadas: " + ", ".join(disabled) + ".")]
    return [_result(ACCOUNT_RESOURCE, "PASS", "Las 4 opciones de Block Public Access están activadas.")]


def _account_bpa_covers_all(ctx):
    """True solo si la cuenta tiene las 4 opciones activadas. Ante cualquier duda (no configurado, error), False."""
    s3control = ctx.client("s3control")
    try:
        response = s3control.get_public_access_block(AccountId=ctx.account_id)
    except s3control.exceptions.ClientError:
        return False
    return not _disabled_flags(response["PublicAccessBlockConfiguration"])


def _bucket_resource(name):
    return f"arn:aws:s3:::{name}"  # el ARN de un bucket no lleva la cuenta


def _list_buckets(s3):
    """Nombres de los buckets de uso general de la cuenta (ListBuckets es global)."""
    return [bucket["Name"] for bucket in s3.list_buckets().get("Buckets", [])]


def s3_bucket_public_access_block(ctx):
    """Cada bucket protegido por Block Public Access: el propio o, si no, el de la cuenta (D97)."""
    s3 = ctx.client("s3")
    try:
        names = _list_buckets(s3)
    except s3.exceptions.ClientError as err:
        return [_result(CHECK_RESOURCE, "ERROR", f"No se pudieron listar los buckets: {_error_code(err)}.")]

    account_covers = _account_bpa_covers_all(ctx)
    results = []
    for name in names:
        try:
            config = s3.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
            disabled = _disabled_flags(config)
        except s3.exceptions.ClientError as err:
            # En S3 este error no es una excepción modelada: se reconoce por el código
            if _error_code(err) != "NoSuchPublicAccessBlockConfiguration":
                results.append(_result(_bucket_resource(name), "ERROR", f"No se pudo leer: {_error_code(err)}."))
                continue
            disabled = list(BPA_FLAGS)

        if not disabled:
            results.append(_result(_bucket_resource(name), "PASS", "Las 4 opciones activadas en el bucket."))
        elif account_covers:
            results.append(_result(
                _bucket_resource(name), "PASS",
                "Cubierto por el Block Public Access de la cuenta (en el bucket: " + ", ".join(disabled) + " desactivadas).",
            ))
        else:
            results.append(_result(_bucket_resource(name), "FAIL", "Desactivadas: " + ", ".join(disabled) + "."))
    return results


# --- s3-bucket-tls-only --------------------------------------------------------

def _as_list(value):
    return value if isinstance(value, list) else [value]


def _denies_insecure_transport(statement):
    """¿Es un Deny para todos (Principal *) de todas las acciones de S3 cuando la conexión no es HTTPS?"""
    if statement.get("Effect") != "Deny":
        return False
    principal = statement.get("Principal")
    if principal != "*" and principal != {"AWS": "*"}:
        return False
    if not {"s3:*", "*"} & set(_as_list(statement.get("Action", []))):
        return False
    # Las claves de condición de IAM no distinguen mayúsculas; el valor puede venir como texto o booleano
    for operator in ("Bool", "BoolIfExists"):
        conditions = {k.lower(): v for k, v in statement.get("Condition", {}).get(operator, {}).items()}
        value = conditions.get("aws:securetransport")
        if value is not None and str(_as_list(value)[0]).lower() == "false":
            return True
    return False


def s3_bucket_tls_only(ctx):
    """Cada bucket rechaza las conexiones sin TLS: su bucket policy tiene un Deny con aws:SecureTransport=false."""
    s3 = ctx.client("s3")
    try:
        names = _list_buckets(s3)
    except s3.exceptions.ClientError as err:
        return [_result(CHECK_RESOURCE, "ERROR", f"No se pudieron listar los buckets: {_error_code(err)}.")]

    results = []
    for name in names:
        try:
            policy = json.loads(s3.get_bucket_policy(Bucket=name)["Policy"])
        except s3.exceptions.ClientError as err:
            if _error_code(err) == "NoSuchBucketPolicy":
                results.append(_result(_bucket_resource(name), "FAIL", "Sin bucket policy: acepta conexiones sin TLS."))
            else:
                results.append(_result(_bucket_resource(name), "ERROR", f"No se pudo leer: {_error_code(err)}."))
            continue

        if any(_denies_insecure_transport(st) for st in _as_list(policy.get("Statement", []))):
            results.append(_result(_bucket_resource(name), "PASS", "La bucket policy rechaza las conexiones sin TLS."))
        else:
            results.append(_result(
                _bucket_resource(name), "FAIL",
                "La bucket policy no tiene un Deny con aws:SecureTransport=false.",
            ))
    return results


# --- cloudtrail-multi-region-logging -------------------------------------------

def cloudtrail_multi_region_logging(ctx):
    """Al menos un trail multi-región que esté LOGUEANDO (un trail detenido no registra nada)."""
    cloudtrail = ctx.client("cloudtrail")
    try:
        # includeShadowTrails: también los multi-región creados en otra región
        trails = cloudtrail.describe_trails(includeShadowTrails=True).get("trailList", [])
        multi_region = [t for t in trails if t.get("IsMultiRegionTrail")]
        if not multi_region:
            return [_result(ACCOUNT_RESOURCE, "FAIL", "No hay ningún trail multi-región.")]

        stopped = []
        for trail in multi_region:
            # Con el ARN funciona aunque el trail sea de otra región. En la evidencia va solo el nombre.
            if cloudtrail.get_trail_status(Name=trail["TrailARN"]).get("IsLogging"):
                return [_result(ACCOUNT_RESOURCE, "PASS", f"El trail multi-región '{trail['Name']}' está logueando.")]
            stopped.append(trail["Name"])
    except cloudtrail.exceptions.ClientError as err:
        return [_result(ACCOUNT_RESOURCE, "ERROR", f"No se pudo leer CloudTrail: {_error_code(err)}.")]

    return [_result(ACCOUNT_RESOURCE, "FAIL", "Hay trails multi-región, pero ninguno está logueando: " + ", ".join(stopped) + ".")]


# --- iam-root-mfa -------------------------------------------------------------

def iam_root_mfa(ctx):
    """El usuario root tiene MFA (AccountMFAEnabled = 1 en el resumen de IAM)."""
    iam = ctx.client("iam")
    try:
        summary = iam.get_account_summary()["SummaryMap"]
    except iam.exceptions.ClientError as err:
        return [_result(ROOT_RESOURCE, "ERROR", f"No se pudo leer IAM: {_error_code(err)}.")]

    if summary.get("AccountMFAEnabled") == 1:
        return [_result(ROOT_RESOURCE, "PASS", "El usuario root tiene MFA.")]
    return [_result(ROOT_RESOURCE, "FAIL", "El usuario root NO tiene MFA.")]


# --- Registro: check_id (el que guarda el control, D92) → función ------------

CHECKS = {
    "s3-account-public-access-block": s3_account_public_access_block,
    "s3-bucket-public-access-block": s3_bucket_public_access_block,
    "s3-bucket-tls-only": s3_bucket_tls_only,
    "cloudtrail-multi-region-logging": cloudtrail_multi_region_logging,
    "iam-root-mfa": iam_root_mfa,
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
