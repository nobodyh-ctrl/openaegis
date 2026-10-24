import logging

import controls
from responses import build_response, user_sub

# Con el log format JSON de Lambda, cada logger.info(...) sale como un JSON con
# timestamp, level, message y requestId; extra={...} agrega campos propios.
# El nivel (INFO) se configura en la Lambda, no acá.
logger = logging.getLogger()

ROUTES = {
    "GET /controls": controls.list_controls,
    "GET /controls/{id}": controls.get_control,
    "POST /controls": controls.create_control,
    "PATCH /controls/{id}": controls.update_control,
    "DELETE /controls/{id}": controls.delete_control,
}


def lambda_handler(event, context):
    route_key = event.get("routeKey", "UNKNOWN")
    log_fields = {
        "route": route_key,
        "apigw_request_id": event.get("requestContext", {}).get("requestId"),
        "user_sub": user_sub(event),
    }

    route_fn = ROUTES.get(route_key)
    if route_fn is None:
        logger.warning("ruta no encontrada", extra=log_fields)
        return build_response(404, {"error": f"Ruta no encontrada: {route_key}"})

    logger.info("request", extra=log_fields)
    # Sin try/except: si algo falla, la excepción llega al runtime, que la loguea con el
    # stackTrace y suma 1 a la métrica Errors (la que vigila la alarma del paso 10.5).
    return route_fn(event)
