"""Alarmas, topic de SNS y dashboard (Etapa 12.6). Replican la Etapa 10 tal cual (D86, D87, D121).

| Alarma                    | Métrica                          | Umbral |
|---------------------------|----------------------------------|--------|
| openaegis-lambda-errors   | AWS/Lambda Errors (API)          | >= 1   |
| openaegis-scanner-errors  | AWS/Lambda Errors (scanner)      | >= 1   |
| openaegis-api-5xx         | AWS/ApiGateway 5xx               | >= 1   |
| openaegis-api-4xx-pico    | AWS/ApiGateway 4xx               | >= 50  |

Todas: Sum en 5 minutos, 1 de 1, sin datos = no está fallando, y en ALARM → SNS → email.

Lección de D88: las métricas salen de los recursos del stack (`function.metric_errors()`,
`http_api.metric_server_error()`), así las dimensiones son referencias y no un nombre escrito a
mano que puede quedar mal.

La suscripción por email NO es parte del stack: se hace con `aws sns subscribe` (infra/README.md),
para que el email no quede en el repo ni en la plantilla.
"""

from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from constructs import Construct

PERIOD = Duration.minutes(5)


class Observability(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        api_function: lambda_.Function,
        scanner_function: lambda_.Function,
        http_api: apigwv2.HttpApi,
        access_logs: logs.LogGroup,
    ) -> None:
        super().__init__(scope, construct_id)

        # Standard y SIN cifrado: con la clave administrada alias/aws/sns, CloudWatch no puede
        # publicar y las alarmas fallan en silencio. Los avisos no llevan datos sensibles.
        self.topic = sns.Topic(self, "Alarms", topic_name="openaegis-alarmas", display_name="OpenAegis")

        def alarm(construct_id, name, metric, threshold, description):
            created = cloudwatch.Alarm(
                self,
                construct_id,
                alarm_name=name,
                alarm_description=description,
                metric=metric,
                threshold=threshold,
                evaluation_periods=1,
                datapoints_to_alarm=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                # Sin tráfico no hay datos: eso no es una falla.
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            created.add_alarm_action(cw_actions.SnsAction(self.topic))
            return created

        sum_5m = {"period": PERIOD, "statistic": cloudwatch.Stats.SUM}
        self.alarms = [
            alarm("LambdaErrors", "openaegis-lambda-errors", api_function.metric_errors(**sum_5m), 1,
                  "La Lambda de la API terminó con error (excepción no manejada o timeout)"),
            alarm("ScannerErrors", "openaegis-scanner-errors", scanner_function.metric_errors(**sum_5m), 1,
                  "Un scan terminó con error. No se reintenta solo (D93)"),
            alarm("Api5xx", "openaegis-api-5xx", http_api.metric_server_error(**sum_5m), 1,
                  "La API respondió 5xx"),
            alarm("Api4xxPico", "openaegis-api-4xx-pico", http_api.metric_client_error(**sum_5m), 50,
                  "Pico de 4xx: posible escaneo o tokens inválidos. Mirar el access log"),
        ]

        self._dashboard(api_function, http_api, access_logs)

    def _dashboard(self, api_function, http_api, access_logs):
        def graph(title, metrics, statistic):
            return cloudwatch.GraphWidget(
                title=title, width=12, height=6, period=PERIOD, statistic=statistic, left=metrics
            )

        def lambda_metric(name, statistic, label=None):
            return api_function.metric(name, period=PERIOD, statistic=statistic, label=label)

        def api_metric(name, statistic):
            return cloudwatch.Metric(
                namespace="AWS/ApiGateway",
                metric_name=name,
                dimensions_map={"ApiId": http_api.api_id},
                period=PERIOD,
                statistic=statistic,
            )

        def logs_table(title, log_group, query_lines):
            return cloudwatch.LogQueryWidget(
                title=title,
                width=12,
                height=6,
                log_group_names=[log_group.log_group_name],
                query_lines=query_lines,
                view=cloudwatch.LogQueryVisualizationType.TABLE,
            )

        cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name="OpenAegis",
            widgets=[
                [cloudwatch.AlarmStatusWidget(title="Alarmas", alarms=self.alarms, width=24, height=2)],
                [
                    graph("API: pedidos, 4xx y 5xx",
                          [api_metric(m, "Sum") for m in ("Count", "4xx", "5xx")], "Sum"),
                    graph("API: Latency vs IntegrationLatency (ms)",
                          [api_metric(m, "Average") for m in ("Latency", "IntegrationLatency")], "Average"),
                ],
                [
                    graph("Lambda: invocaciones, errores y throttles",
                          [lambda_metric(m, "Sum") for m in ("Invocations", "Errors", "Throttles")], "Sum"),
                    graph("Lambda: Duration (ms)",
                          [lambda_metric("Duration", "Average", "Promedio"),
                           lambda_metric("Duration", "Maximum", "Máximo")], "Average"),
                ],
                [
                    logs_table("Rechazos del authorizer por motivo", access_logs, [
                        'filter status = "401" or status = "403"',
                        "stats count(*) as intentos by status, authorizerError",
                        "sort intentos desc",
                    ]),
                    # Sin user_sub: las capturas del dashboard se comparten (D87).
                    logs_table("Auditoría: últimos cambios", api_function.log_group, [
                        "fields @timestamp, message, code",
                        'filter logger = "controls"',
                        "sort @timestamp desc",
                        "limit 20",
                    ]),
                ],
            ],
        )
