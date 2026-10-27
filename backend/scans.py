"""Rutas de scans y findings: disparar un scan, ver el último y los findings de un control."""

import logging

import findings_repository
import scanner_client
from responses import build_response, error_response, user_sub
from validation import validate_control_id

logger = logging.getLogger(__name__)


def start_scan(event):
    requested_by = user_sub(event)
    scanner_client.start_scan(requested_by)
    logger.info("scan solicitado", extra={"user_sub": requested_by})
    # 202 Accepted: el pedido se aceptó, pero el resultado todavía no existe (D93)
    return build_response(202, {"message": "Scan iniciado. Consultá GET /scans/latest para ver el resultado."})


def latest_scan(event):
    return build_response(200, {"item": findings_repository.latest_scan()})


def list_findings(event):
    raw_id = (event.get("queryStringParameters") or {}).get("control_id")
    control_id, err = validate_control_id(raw_id)
    if err:
        return error_response(400, err)

    items = findings_repository.findings_for_control(control_id)
    return build_response(200, {"items": items, "count": len(items)})
