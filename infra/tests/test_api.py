"""Tests de api.py: el HTTP API, el JWT authorizer y los permisos de invocación (Etapa 12.4).

Lo más importante está al final: los permisos que dejan a API Gateway invocar la Lambda. Tienen que
ser uno por ruta y CON el método (D57). La integración de CDK por defecto los arma con el método
como comodín (`<api>/*/*/controls`) y con `scopePermissionToRoute=False`, uno solo para toda la API
(`<api>/*/*/*`): estos tests fallan en los dos casos.
"""

import ast
import json
import unittest
from pathlib import Path

from test_stack import synth_template

HANDLER = Path(__file__).resolve().parents[2] / "backend" / "handler.py"

# Los 15 campos del access log de la Etapa 10 (D85, docs/10-cloudwatch.md §4.3).
ACCESS_LOG_FIELDS = {
    "requestId": "$context.requestId",
    "ip": "$context.identity.sourceIp",
    "userAgent": "$context.identity.userAgent",
    "requestTime": "$context.requestTime",
    "method": "$context.httpMethod",
    "routeKey": "$context.routeKey",
    "path": "$context.path",
    "status": "$context.status",
    "responseLength": "$context.responseLength",
    "responseLatency": "$context.responseLatency",
    "integrationLatency": "$context.integrationLatency",
    "integrationStatus": "$context.integrationStatus",
    "authorizerError": "$context.authorizer.error",
    "errorMessage": "$context.error.message",
    "sub": "$context.authorizer.claims.sub",
}


def backend_routes():
    """Las claves de ROUTES en backend/handler.py, leídas sin importarlo (importarlo pide boto3 y env)."""
    tree = ast.parse(HANDLER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "ROUTES" for t in node.targets):
            return {key.value for key in node.value.keys}
    raise AssertionError("no se encontró ROUTES en backend/handler.py")


def render(value):
    """Un Fn::Join de CloudFormation como texto, con cada referencia reemplazada por <ref>."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and "Fn::Join" in value:
        separator, parts = value["Fn::Join"]
        return separator.join(render(part) for part in parts)
    return "<ref>"


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()
        cls.resources = cls.template.to_json()["Resources"]

    def of_type(self, resource_type):
        return {lid: r for lid, r in self.resources.items() if r["Type"] == resource_type}

    def only(self, resource_type):
        found = self.of_type(resource_type)
        self.assertEqual(len(found), 1, f"se esperaba un solo {resource_type}")
        return next(iter(found.items()))

    def function_id(self, name):
        for lid, resource in self.of_type("AWS::Lambda::Function").items():
            if resource["Properties"]["FunctionName"] == name:
                return lid
        raise AssertionError(f"no está la Lambda {name}")

    # ---- La API ----

    def test_http_api_con_nombre_fijo_y_sin_cors(self):
        # Sin CORS en el 12.4: en desarrollo la SPA usa el proxy de Vite (mismo origen).
        # El origen de CloudFront se agrega en el 12.5, como referencia.
        _, api = self.only("AWS::ApiGatewayV2::Api")
        self.assertEqual(api["Properties"]["Name"], "openaegis-http-api")
        self.assertEqual(api["Properties"]["ProtocolType"], "HTTP")
        self.assertNotIn("CorsConfiguration", api["Properties"])

    def test_las_rutas_son_exactamente_las_del_backend(self):
        # Una ruta en la API sin handler da 404 del backend; un handler sin ruta es código muerto.
        routes = {r["Properties"]["RouteKey"] for r in self.of_type("AWS::ApiGatewayV2::Route").values()}
        self.assertEqual(routes, backend_routes())

    def test_todas_las_rutas_exigen_el_jwt_con_scope_openid(self):
        # El scope hace rebotar al ID token (403): a la API solo entra el access token (D82).
        authorizer_id, _ = self.only("AWS::ApiGatewayV2::Authorizer")
        for route in self.of_type("AWS::ApiGatewayV2::Route").values():
            props = route["Properties"]
            with self.subTest(route=props["RouteKey"]):
                self.assertEqual(props["AuthorizationType"], "JWT")
                self.assertEqual(props["AuthorizationScopes"], ["openid"])
                self.assertEqual(props["AuthorizerId"], {"Ref": authorizer_id})

    def test_jwt_authorizer_contra_el_user_pool_y_el_app_client(self):
        _, authorizer = self.only("AWS::ApiGatewayV2::Authorizer")
        props = authorizer["Properties"]
        client_id, _ = self.only("AWS::Cognito::UserPoolClient")
        pool_id, _ = self.only("AWS::Cognito::UserPool")
        self.assertEqual(props["AuthorizerType"], "JWT")
        self.assertEqual(props["Name"], "cognito-openaegis")
        self.assertEqual(props["IdentitySource"], ["$request.header.Authorization"])
        self.assertEqual(props["JwtConfiguration"]["Audience"], [{"Ref": client_id}])
        self.assertIn(pool_id, json.dumps(props["JwtConfiguration"]["Issuer"]))

    def test_una_sola_integracion_lambda_proxy_con_payload_2(self):
        _, integration = self.only("AWS::ApiGatewayV2::Integration")
        props = integration["Properties"]
        self.assertEqual(props["IntegrationType"], "AWS_PROXY")
        self.assertEqual(props["PayloadFormatVersion"], "2.0")
        self.assertEqual(props["IntegrationUri"], {"Fn::GetAtt": [self.function_id("openaegis-api"), "Arn"]})

    # ---- Stage: throttling y access logs ----

    def test_stage_default_con_throttling(self):
        _, stage = self.only("AWS::ApiGatewayV2::Stage")
        props = stage["Properties"]
        self.assertEqual(props["StageName"], "$default")
        self.assertTrue(props["AutoDeploy"])
        self.assertEqual(props["DefaultRouteSettings"]["ThrottlingRateLimit"], 10)  # D27
        self.assertEqual(props["DefaultRouteSettings"]["ThrottlingBurstLimit"], 20)

    def test_access_log_con_los_15_campos_de_la_etapa_10(self):
        _, stage = self.only("AWS::ApiGatewayV2::Stage")
        settings = stage["Properties"]["AccessLogSettings"]
        self.assertEqual(json.loads(settings["Format"]), ACCESS_LOG_FIELDS)
        log_group_id = settings["DestinationArn"]["Fn::GetAtt"][0]
        log_group = self.resources[log_group_id]
        self.assertEqual(log_group["Properties"]["LogGroupName"], "/aws/vendedlogs/apigateway/openaegis-http-api")
        self.assertEqual(log_group["Properties"]["RetentionInDays"], 7)
        self.assertEqual(log_group["DeletionPolicy"], "Delete")

    # ---- Permisos de invocación (resource-based policy de la Lambda) ----

    def test_un_permiso_por_ruta_con_el_metodo(self):
        permissions = self.of_type("AWS::Lambda::Permission").values()
        expected = set()
        for route_key in backend_routes():
            method, path = route_key.split(" ")
            expected.add(f"/*/{method}{path}")  # stage comodín, método explícito (D57)

        suffixes = set()
        for permission in permissions:
            props = permission["Properties"]
            self.assertEqual(props["Principal"], "apigateway.amazonaws.com")
            self.assertEqual(props["Action"], "lambda:InvokeFunction")
            self.assertEqual(props["FunctionName"], {"Fn::GetAtt": [self.function_id("openaegis-api"), "Arn"]})
            source = render(props["SourceArn"])
            self.assertTrue(source.startswith("arn:<ref>:execute-api:"), source)
            suffixes.add(source.split("<ref>")[-1])

        self.assertEqual(len(permissions), len(expected), "un permiso por ruta, ni más ni menos")
        self.assertEqual(suffixes, expected)

    def test_el_scanner_no_se_puede_invocar_desde_la_api(self):
        # Al scanner solo lo invoca la Lambda de la API, por IAM (LanzarScans). Sin resource-based policy.
        scanner_arn = {"Fn::GetAtt": [self.function_id("openaegis-scanner"), "Arn"]}
        for permission in self.of_type("AWS::Lambda::Permission").values():
            self.assertNotEqual(permission["Properties"]["FunctionName"], scanner_arn)

    # ---- Lo que la SPA necesita saber ----

    def test_outputs_para_configurar_la_spa(self):
        outputs = self.template.to_json().get("Outputs", {})
        for name in ("ApiUrl", "CognitoAuthority", "CognitoClientId", "CognitoDomain"):
            with self.subTest(output=name):
                self.assertIn(name, outputs)


if __name__ == "__main__":
    unittest.main()
