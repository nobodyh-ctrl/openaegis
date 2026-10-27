"""Lógica de cada ruta de /controls: valida, aplica las reglas de negocio y arma la respuesta."""

import logging
import uuid
from datetime import datetime, timezone

import findings_repository
import repository
from responses import build_response, error_response, parse_json_body, user_sub
from validation import validate_control_id, validate_fields

logger = logging.getLogger(__name__)

AUTOMATIC_STATUS_ERROR = (
    "El status de un control automático lo define el scanner. "
    "Para editarlo a mano, pasalo a manual (check_id vacío)."
)


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_change(action, event, item):
    """Auditoría: qué control cambió y quién lo hizo. Solo IDs, nunca el body completo."""
    logger.info(
        f"control {action}",
        extra={"control_id": item["id"], "code": item.get("code"), "user_sub": user_sub(event)},
    )


def list_controls(event):
    items = repository.list_controls()
    return build_response(200, {"items": items, "count": len(items)})


def get_control(event):
    control_id, err = validate_control_id(event.get("pathParameters", {}).get("id"))
    if err:
        return error_response(400, err)

    item = repository.get_control(control_id)
    if not item:
        return error_response(404, "Control no encontrado.")

    return build_response(200, {"item": item})


def create_control(event):
    body, err_response = parse_json_body(event)
    if err_response:
        return err_response

    cleaned, err = validate_fields(body)
    if err:
        return error_response(400, err)

    # En la creación, status siempre tiene valor (default REVIEW): se mira si vino en el body
    if cleaned.get("check_id") and "status" in body:
        return error_response(400, AUTOMATIC_STATUS_ERROR)

    if repository.find_control_by_code(cleaned["code"]):
        return error_response(409, f"Ya existe un control con el código '{cleaned['code']}'.")

    now = _now_utc()
    item = {
        "id": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
        **{k: v for k, v in cleaned.items() if v is not None},
    }

    repository.create_control(item)
    _log_change("creado", event, item)

    return build_response(201, {"item": item})


def update_control(event):
    control_id, err = validate_control_id(event.get("pathParameters", {}).get("id"))
    if err:
        return error_response(400, err)

    body, err_response = parse_json_body(event)
    if err_response:
        return err_response

    cleaned, err = validate_fields(body, partial=True)
    if err:
        return error_response(400, err)

    current = repository.get_control(control_id)
    if current is None:
        return error_response(404, "Control no encontrado.")

    # Se calcula ANTES del update: no depender de que el item leído siga intacto después
    was_automatic = bool(current.get("check_id"))
    check_id_after = cleaned.get("check_id", current.get("check_id"))
    if "status" in cleaned and check_id_after:
        return error_response(409, AUTOMATIC_STATUS_ERROR)

    if "code" in cleaned:
        existing = repository.find_control_by_code(cleaned["code"])
        if existing and existing["id"] != control_id:
            return error_response(409, f"Ya existe un control con el código '{cleaned['code']}'.")

    cleaned["updated_at"] = _now_utc()

    item = repository.update_control(control_id, cleaned)
    if item is None:
        return error_response(404, "Control no encontrado.")

    _log_change("actualizado", event, item)

    # Pasó de automático a manual: sus findings ya no se actualizarían nunca (D95)
    if was_automatic and not check_id_after:
        deleted = findings_repository.delete_all_findings(control_id)
        logger.info(
            "findings eliminados",
            extra={"control_id": control_id, "deleted": deleted, "user_sub": user_sub(event)},
        )

    return build_response(200, {"item": item})


def delete_control(event):
    control_id, err = validate_control_id(event.get("pathParameters", {}).get("id"))
    if err:
        return error_response(400, err)

    if findings_repository.has_findings(control_id):
        return error_response(
            409,
            "El control tiene findings. Pasalo a manual (check_id vacío) antes de eliminarlo: eso borra sus findings.",
        )

    item = repository.delete_control(control_id)
    if item is None:
        return error_response(404, "Control no encontrado.")

    _log_change("eliminado", event, item)
    return build_response(200, {"item": item})
