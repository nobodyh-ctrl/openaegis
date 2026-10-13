"""Lógica de cada ruta de /controls: valida, aplica las reglas de negocio y arma la respuesta."""

import uuid
from datetime import datetime, timezone

import repository
from responses import build_response, error_response, parse_json_body
from validation import validate_control_id, validate_fields


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    if "code" in cleaned:
        existing = repository.find_control_by_code(cleaned["code"])
        if existing and existing["id"] != control_id:
            return error_response(409, f"Ya existe un control con el código '{cleaned['code']}'.")

    cleaned["updated_at"] = _now_utc()

    item = repository.update_control(control_id, cleaned)
    if item is None:
        return error_response(404, "Control no encontrado.")

    return build_response(200, {"item": item})


def delete_control(event):
    control_id, err = validate_control_id(event.get("pathParameters", {}).get("id"))
    if err:
        return error_response(400, err)

    item = repository.delete_control(control_id)
    if item is None:
        return error_response(404, "Control no encontrado.")

    print(f"[DELETE] code={item.get('code')} id={item['id']}")
    return build_response(200, {"item": item})
