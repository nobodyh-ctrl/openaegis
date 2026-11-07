"""HTTP API + JWT authorizer + permisos de invocación (Etapa 12.4).

Replica la API de las Etapas 5, 9 y 10 (D26-D29, D57, D82, D85):

    cliente ──► openaegis-http-api (stage $default: throttling 10/20 + access log JSON)
                  └─ JWT authorizer cognito-openaegis (scope openid) en las 8 rutas
                       └─ integración Lambda proxy (payload 2.0) ──► openaegis-api

CORS: un solo origen, el de la distribución de CloudFront, como referencia (D28, D114). Sin
localhost: en desarrollo la SPA usa el proxy de Vite (mismo origen).

PERMISOS DE INVOCACIÓN: la integración de CDK (`HttpLambdaIntegration`) agrega sus propios
permisos, con el método como comodín (`<api>/*/*/controls`) o, con `scopePermissionToRoute=False`,
uno solo para toda la API (`<api>/*/*/*`). Las dos opciones deshacen D57. Por eso la integración
de acá no agrega ninguno, y cada ruta suma el suyo con el método explícito.
"""

import json
import re

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from openaegis.auth import Auth

API_NAME = "openaegis-http-api"

# Las mismas claves que ROUTES en backend/handler.py. tests/test_api.py controla que coincidan.
ROUTE_KEYS = (
    "GET /controls",
    "GET /controls/{id}",
    "POST /controls",
    "PATCH /controls/{id}",
    "DELETE /controls/{id}",
    "POST /scans",
    "GET /scans/latest",
    "GET /findings",
)

# Formato del access log de la Etapa 10 (D85): una línea JSON por pedido, incluidos los 401/403
# del authorizer, que la Lambda nunca ve.
ACCESS_LOG_FORMAT = {
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


class _LambdaProxyWithoutPermissions(apigwv2.HttpRouteIntegration):
    """Integración Lambda proxy (payload 2.0) que NO toca la resource-based policy de la Lambda."""

    def __init__(self, construct_id: str, function: lambda_.IFunction) -> None:
        super().__init__(construct_id)
        self._function = function

    def bind(self, *_args, **_kwargs) -> apigwv2.HttpRouteIntegrationConfig:
        return apigwv2.HttpRouteIntegrationConfig(
            type=apigwv2.HttpIntegrationType.AWS_PROXY,
            uri=self._function.function_arn,
            payload_format_version=apigwv2.PayloadFormatVersion.VERSION_2_0,
        )


class Api(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, function: lambda_.IFunction, auth: Auth, spa_url: str
    ) -> None:
        super().__init__(scope, construct_id)

        self.http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=API_NAME,
            description="API de OpenAegis: CRUD de controles, scans y findings",
            create_default_stage=False,  # el stage se arma abajo, con throttling y access log
            # Lo responde API Gateway (D29), antes del authorizer: la preflight no lleva token.
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=[spa_url],
                allow_methods=[apigwv2.CorsHttpMethod[m] for m in ("GET", "POST", "PATCH", "DELETE")],
                allow_headers=["content-type", "authorization"],
                allow_credentials=False,
                max_age=Duration.seconds(0),  # paridad con lo manual; subirlo es una mejora aparte
            ),
        )

        # Mismo prefijo que el manual (/aws/vendedlogs/): el recomendado para logs que escribe un servicio.
        self.access_logs = logs.LogGroup(
            self,
            "AccessLogs",
            log_group_name=f"/aws/vendedlogs/apigateway/{API_NAME}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.stage = apigwv2.HttpStage(
            self,
            "Stage",
            http_api=self.http_api,
            stage_name="$default",
            auto_deploy=True,
            throttle=apigwv2.ThrottleSettings(rate_limit=10, burst_limit=20),  # D27
        )
        # El access log se configura sobre el recurso de CloudFormation (L1): en Python, la opción del
        # L2 pide implementar una interfaz de jsii, y así se ve exactamente lo que queda en la plantilla.
        self.stage.node.default_child.access_log_settings = apigwv2.CfnStage.AccessLogSettingsProperty(
            destination_arn=self.access_logs.log_group_arn,
            format=apigw.AccessLogFormat.custom(json.dumps(ACCESS_LOG_FORMAT, separators=(",", ":"))).to_string(),
        )

        # Valida el token ANTES de la Lambda: sin token o con uno inválido, 401 sin ejecutar nada.
        authorizer = authorizers.HttpUserPoolAuthorizer(
            "Cognito",
            auth.user_pool,
            user_pool_clients=[auth.client],
            authorizer_name="cognito-openaegis",
        )
        integration = _LambdaProxyWithoutPermissions("Api", function)

        for route_key in ROUTE_KEYS:
            method, path = route_key.split(" ")
            self.http_api.add_routes(
                path=path,
                methods=[apigwv2.HttpMethod[method]],
                integration=integration,
                authorizer=authorizer,
                authorization_scopes=["openid"],  # un ID token rebota con 403 (D82)
            )
            # Un statement por ruta, con el método (D57): una ruta nueva no puede invocar la Lambda
            # sin su propio permiso.
            function.add_permission(
                "Invoke" + re.sub(r"[^A-Za-z0-9]", "", route_key.title()),
                principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
                source_arn=self.http_api.arn_for_execute_api(method, path),
            )
