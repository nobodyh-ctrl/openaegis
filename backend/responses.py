"""Entrada y salida HTTP en el formato de API Gateway (payload 2.0)."""

import json
from decimal import Decimal


def _json_default(value):
    """DynamoDB devuelve los números como Decimal, que json.dumps no sabe serializar."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Tipo no serializable: {type(value).__name__}")


def build_response(status_code, body_dict):
    """Arma la respuesta que API Gateway convierte en HTTP."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_dict, default=_json_default),
    }


def error_response(status_code, message):
    return build_response(status_code, {"error": message})


def parse_json_body(event):
    """Parsea y valida el body. Retorna (dict, None) o (None, response_error)."""
    raw_body = event.get("body")
    if not raw_body:
        return None, error_response(400, "El cuerpo de la solicitud está vacío.")
    try:
        body_data = json.loads(raw_body)
    except json.JSONDecodeError:
        return None, error_response(400, "JSON inválido.")
    if not isinstance(body_data, dict):
        return None, error_response(400, "El body debe ser un objeto JSON.")
    return body_data, None


def user_sub(event):
    """ID del usuario de Cognito (claim "sub") que el JWT authorizer validó, o None si no hay authorizer."""
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    return claims.get("sub")
