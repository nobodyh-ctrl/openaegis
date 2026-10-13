import controls
from responses import build_response

ROUTES = {
    "GET /controls": controls.list_controls,
    "GET /controls/{id}": controls.get_control,
    "POST /controls": controls.create_control,
    "PATCH /controls/{id}": controls.update_control,
    "DELETE /controls/{id}": controls.delete_control,
}


def lambda_handler(event, context):
    route_key = event.get("routeKey", "UNKNOWN")

    request_context = event.get("requestContext", {})
    apigw_request_id = request_context.get("requestId", "UNKNOWN")
    lambda_request_id = context.aws_request_id
    print(f"[{route_key}] | APIGW_ID: {apigw_request_id} | LAMBDA_ID: {lambda_request_id}")

    route_fn = ROUTES.get(route_key)
    if route_fn is None:
        return build_response(404, {"error": f"Ruta no encontrada: {route_key}"})

    return route_fn(event)
