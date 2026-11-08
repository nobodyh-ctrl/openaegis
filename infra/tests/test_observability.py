"""Tests de observability.py: alarmas, topic de SNS y dashboard (Etapa 12.6).

Lo más importante es D88: una alarma que mira una métrica con la dimensión equivocada queda muda
para siempre (sin datos + notBreaching = OK). Por eso cada alarma se verifica con su namespace, su
métrica y sus DIMENSIONES, y las dimensiones tienen que ser referencias (Ref) a los recursos del
stack, nunca nombres escritos como texto.
"""

import json
import re
import unittest

from test_stack import synth_template

ALARMS = {
    # nombre: (namespace, métrica, dimensión, recurso al que apunta, umbral)
    "openaegis-lambda-errors": ("AWS/Lambda", "Errors", "FunctionName", "openaegis-api", 1),
    "openaegis-scanner-errors": ("AWS/Lambda", "Errors", "FunctionName", "openaegis-scanner", 1),
    "openaegis-api-5xx": ("AWS/ApiGateway", "5xx", "ApiId", "openaegis-http-api", 1),
    "openaegis-api-4xx-pico": ("AWS/ApiGateway", "4xx", "ApiId", "openaegis-http-api", 50),
}

DASHBOARD_TITLES = [
    "Alarmas",
    "API: pedidos, 4xx y 5xx",
    "API: Latency vs IntegrationLatency (ms)",
    "Lambda: invocaciones, errores y throttles",
    "Lambda: Duration (ms)",
    "Rechazos del authorizer por motivo",
    "Auditoría: últimos cambios",
]


def _token(value):
    """Convierte una referencia de CloudFormation en un marcador legible: {"Ref": "X"} → "<X>"."""
    if "Ref" in value:
        return f"<{value['Ref']}>"
    if "Fn::GetAtt" in value:
        return f"<{value['Fn::GetAtt'][0]}.{value['Fn::GetAtt'][1]}>"
    raise AssertionError(f"referencia inesperada en el dashboard: {value}")


class ObservabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()
        cls.resources = cls.template.to_json()["Resources"]

    # ---- helpers ----

    def logical_id(self, resource_type, **props):
        found = self.template.find_resources(resource_type, {"Properties": props})
        self.assertEqual(len(found), 1, f"se esperaba un {resource_type} con {props}")
        return next(iter(found))

    def target_id(self, name):
        """Logical ID del recurso que una alarma tiene que mirar, buscado por su nombre."""
        if name.startswith("openaegis-http-api"):
            return self.logical_id("AWS::ApiGatewayV2::Api", Name=name)
        return self.logical_id("AWS::Lambda::Function", FunctionName=name)

    def alarm(self, name):
        return self.resources[self.logical_id("AWS::CloudWatch::Alarm", AlarmName=name)]["Properties"]

    def topic_id(self):
        return self.logical_id("AWS::SNS::Topic", TopicName="openaegis-alarmas")

    def dashboard_widgets(self):
        """El cuerpo del dashboard, con las referencias reemplazadas por marcadores, ya parseado."""
        body = self.resources[self.logical_id("AWS::CloudWatch::Dashboard", DashboardName="OpenAegis")]
        parts = body["Properties"]["DashboardBody"]["Fn::Join"][1]
        text = "".join(p if isinstance(p, str) else _token(p) for p in parts)
        return json.loads(text)["widgets"]

    # ---- SNS ----

    def test_un_topic_standard_sin_cifrado(self):
        # Sin cifrado a propósito: con la clave administrada alias/aws/sns, CloudWatch no puede
        # publicar y las alarmas fallan en silencio (docs/10-cloudwatch.md, "cosas que NO hacer").
        self.template.resource_count_is("AWS::SNS::Topic", 1)
        topic = self.resources[self.topic_id()]["Properties"]
        self.assertNotIn("KmsMasterKeyId", topic)
        self.assertNotIn("FifoTopic", topic)

    def test_el_email_no_esta_en_la_plantilla(self):
        # La suscripción se hace fuera del stack (aws sns subscribe con read -rs): el email no
        # tiene que quedar ni en el repo ni en la plantilla ni en cdk.out.
        self.template.resource_count_is("AWS::SNS::Subscription", 0)
        text = json.dumps(self.template.to_json())
        self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text), "hay algo con forma de email")

    # ---- alarmas ----

    def test_hay_cuatro_alarmas(self):
        self.template.resource_count_is("AWS::CloudWatch::Alarm", len(ALARMS))

    def test_metrica_y_dimensiones_de_cada_alarma(self):
        # D88: namespace, métrica y dimensión, con Ref al recurso del stack (no un nombre como texto).
        for name, (namespace, metric, dimension, target, _) in ALARMS.items():
            with self.subTest(alarm=name):
                props = self.alarm(name)
                self.assertEqual(props["Namespace"], namespace)
                self.assertEqual(props["MetricName"], metric)
                self.assertEqual(props["Dimensions"], [{"Name": dimension, "Value": {"Ref": self.target_id(target)}}])

    def test_regla_de_cada_alarma(self):
        # D86: Sum en 5 minutos, 1 de 1, >= umbral, sin datos = no está fallando.
        for name, (*_, threshold) in ALARMS.items():
            with self.subTest(alarm=name):
                props = self.alarm(name)
                self.assertEqual(props["Statistic"], "Sum")
                self.assertEqual(props["Period"], 300)
                self.assertEqual(props["EvaluationPeriods"], 1)
                self.assertEqual(props["DatapointsToAlarm"], 1)
                self.assertEqual(props["Threshold"], threshold)
                self.assertEqual(props["ComparisonOperator"], "GreaterThanOrEqualToThreshold")
                self.assertEqual(props["TreatMissingData"], "notBreaching")

    def test_cada_alarma_avisa_al_topic(self):
        for name in ALARMS:
            with self.subTest(alarm=name):
                self.assertEqual(self.alarm(name)["AlarmActions"], [{"Ref": self.topic_id()}])

    # ---- dashboard ----

    def test_el_dashboard_tiene_los_siete_paneles(self):
        self.assertEqual([w["properties"]["title"] for w in self.dashboard_widgets()], DASHBOARD_TITLES)

    def test_el_panel_de_alarmas_muestra_las_cuatro(self):
        widget = self.dashboard_widgets()[0]
        alarm_ids = [self.logical_id("AWS::CloudWatch::Alarm", AlarmName=n) for n in ALARMS]
        self.assertEqual(widget["type"], "alarm")
        self.assertEqual(sorted(widget["properties"]["alarms"]), sorted(f"<{i}.Arn>" for i in alarm_ids))

    def test_los_graficos_apuntan_a_la_api_y_a_la_lambda_del_stack(self):
        api = f"<{self.target_id('openaegis-http-api')}>"
        function = f"<{self.target_id('openaegis-api')}>"
        expected = {
            "API: pedidos, 4xx y 5xx": ("AWS/ApiGateway", {"Count", "4xx", "5xx"}, "ApiId", api),
            "API: Latency vs IntegrationLatency (ms)": (
                "AWS/ApiGateway", {"Latency", "IntegrationLatency"}, "ApiId", api),
            "Lambda: invocaciones, errores y throttles": (
                "AWS/Lambda", {"Invocations", "Errors", "Throttles"}, "FunctionName", function),
            "Lambda: Duration (ms)": ("AWS/Lambda", {"Duration"}, "FunctionName", function),
        }
        widgets = {w["properties"]["title"]: w for w in self.dashboard_widgets()}
        for title, (namespace, metrics, dimension, target) in expected.items():
            with self.subTest(widget=title):
                rows = widgets[title]["properties"]["metrics"]
                # Cada fila: [namespace, métrica, dimensión, valor, {opciones}]
                self.assertEqual({r[1] for r in rows}, metrics)
                for row in rows:
                    self.assertEqual(row[0], namespace)
                    self.assertEqual(row[2:4], [dimension, target])

    def test_las_consultas_de_logs_usan_los_log_groups_del_stack(self):
        widgets = {w["properties"]["title"]: w for w in self.dashboard_widgets()}
        access_logs = self.logical_id(
            "AWS::Logs::LogGroup", LogGroupName="/aws/vendedlogs/apigateway/openaegis-http-api")
        api_logs = self.logical_id("AWS::Logs::LogGroup", LogGroupName="/aws/lambda/openaegis-api")
        cases = {
            "Rechazos del authorizer por motivo": (access_logs, "authorizerError"),
            "Auditoría: últimos cambios": (api_logs, 'filter logger = "controls"'),
        }
        for title, (log_group, fragment) in cases.items():
            with self.subTest(widget=title):
                query = widgets[title]["properties"]["query"]
                self.assertTrue(query.startswith(f"SOURCE '<{log_group}>'"), query)
                self.assertIn(fragment, query)

    def test_la_auditoria_no_muestra_el_usuario(self):
        # Las capturas del dashboard se comparten: el panel no muestra user_sub (D87).
        query = self.dashboard_widgets()[6]["properties"]["query"]
        self.assertNotIn("user_sub", query)

    def test_ningun_nombre_de_los_recursos_manuales(self):
        # Los recursos viejos se llaman cloud-sec-checklist-*: si aparecen, algo quedó como texto.
        self.assertNotIn("cloud-sec-checklist", json.dumps(self.template.to_json()))


if __name__ == "__main__":
    unittest.main()
