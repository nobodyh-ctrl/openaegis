"""Lambda openaegis-scanner: corre los checks de los controles automáticos y guarda findings y resumen.

Handler: scanner.lambda_handler. Mismo zip que la API, pero otra Lambda con su propio rol (D89):
solo este rol puede leer la configuración de la cuenta.
"""

import logging
from datetime import datetime, timezone
from functools import cache

import boto3

import findings_repository
import repository
from checks import ScanContext, run_checks

logger = logging.getLogger()

STATUSES = ("PASS", "FAIL", "ERROR")


@cache
def _client(service_name):
    """Un cliente por servicio, reutilizado entre invocaciones del mismo entorno."""
    return boto3.client(service_name)


def _now_utc():
    # Formato fijo (con ceros a la izquierda): la SK started_at se ordena como texto
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lambda_handler(event, context):
    started_at = _now_utc()
    scan_id = started_at

    # El ID de la cuenta sale del ARN de esta Lambda (arn:aws:lambda:región:CUENTA:function:nombre),
    # sin llamar a STS. Se usa solo para la llamada a s3control: nunca se loguea ni se guarda.
    account_id = context.invoked_function_arn.split(":")[4]

    controls = [c for c in repository.list_controls() if c.get("check_id")]
    findings = run_checks(controls, ScanContext(client=_client, account_id=account_id))
    for finding in findings:
        finding["scan_id"] = scan_id
        finding["evaluated_at"] = started_at

    findings_repository.save_findings(findings)
    stale_deleted = sum(findings_repository.delete_stale_findings(c["id"], scan_id) for c in controls)

    for finding in findings:
        if finding["status"] == "ERROR":
            logger.warning(
                "check con error",
                extra={k: finding[k] for k in ("control_id", "check_id", "resource_id", "evidence")},
            )

    summary = {
        "started_at": started_at,
        "finished_at": _now_utc(),
        "controls_evaluated": len(controls),
        **{f"{s.lower()}_count": sum(1 for f in findings if f["status"] == s) for s in STATUSES},
        "stale_deleted": stale_deleted,
    }
    findings_repository.save_scan(summary)
    logger.info("scan terminado", extra=summary)
    return summary
