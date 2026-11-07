"""Tests de compute.py: las Lambdas y, sobre todo, los permisos EXACTOS de cada rol.

Los permisos se comparan contra una lista fija (Sid → acciones). Si alguien agrega una acción,
el test falla y obliga a decidirlo a propósito, actualizando la lista y ARCHITECTURE.md §5.
"""

import unittest

from test_stack import synth_template

API_PERMISSIONS = {
    "EscribirSusLogs": ["logs:CreateLogStream", "logs:PutLogEvents"],
    "CrudDeControles": ["dynamodb:Scan", "dynamodb:GetItem", "dynamodb:PutItem",
                        "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
    "LanzarScans": ["lambda:InvokeFunction"],
    "LeerYBorrarFindings": ["dynamodb:Query", "dynamodb:BatchWriteItem"],
    "LeerScans": ["dynamodb:Query"],
}

SCANNER_PERMISSIONS = {
    "EscribirSusLogs": ["logs:CreateLogStream", "logs:PutLogEvents"],
    "LeerControles": ["dynamodb:Scan"],
    "EscribirSoloStatusDeControles": ["dynamodb:UpdateItem"],
    "EscribirFindings": ["dynamodb:Query", "dynamodb:BatchWriteItem"],
    "GuardarScans": ["dynamodb:PutItem"],
    "CheckS3AccountPublicAccessBlock": ["s3:GetAccountPublicAccessBlock"],
    "CheckS3ListarBuckets": ["s3:ListAllMyBuckets"],
    "CheckS3ConfigDeBuckets": ["s3:GetBucketPublicAccessBlock", "s3:GetBucketPolicy"],
    "CheckCloudTrailListar": ["cloudtrail:DescribeTrails"],
    "CheckCloudTrailEstado": ["cloudtrail:GetTrailStatus"],
    "CheckIamRootMfa": ["iam:GetAccountSummary"],
}


def as_list(value):
    return value if isinstance(value, list) else [value]


class ComputeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()
        cls.resources = cls.template.to_json()["Resources"]

    # ---- helpers ----

    def function(self, name):
        found = self.template.find_resources("AWS::Lambda::Function", {"Properties": {"FunctionName": name}})
        self.assertEqual(len(found), 1, f"se esperaba una Lambda {name}")
        return next(iter(found.items()))

    def role_id(self, function_name):
        _, function = self.function(function_name)
        return function["Properties"]["Role"]["Fn::GetAtt"][0]

    def statements(self, function_name):
        """Statements de todas las policies que CDK le asigna al rol de esa Lambda, por Sid."""
        role_ref = {"Ref": self.role_id(function_name)}
        by_sid = {}
        for resource in self.resources.values():
            if resource["Type"] == "AWS::IAM::Policy" and role_ref in resource["Properties"]["Roles"]:
                for statement in as_list(resource["Properties"]["PolicyDocument"]["Statement"]):
                    by_sid[statement["Sid"]] = statement
        return by_sid

    def log_group_id(self, function_name):
        _, function = self.function(function_name)
        return function["Properties"]["LoggingConfig"]["LogGroup"]["Ref"]

    # ---- configuración de las Lambdas ----

    def test_configuracion_de_cada_lambda(self):
        expected = {
            "openaegis-api": ("handler.lambda_handler", 128, 3),
            "openaegis-scanner": ("scanner.lambda_handler", 256, 30),
        }
        for name, (handler, memory, timeout) in expected.items():
            with self.subTest(function=name):
                props = self.function(name)[1]["Properties"]
                self.assertEqual(props["Handler"], handler)
                self.assertEqual(props["MemorySize"], memory)
                self.assertEqual(props["Timeout"], timeout)
                self.assertEqual(props["Runtime"], "python3.14")
                self.assertEqual(props["Architectures"], ["arm64"])
                self.assertEqual(props["LoggingConfig"]["LogFormat"], "JSON")

    def test_las_dos_lambdas_usan_el_mismo_zip(self):
        # Si quedaran con código distinto, la API validaría check_id contra otra versión de CHECKS.
        api = self.function("openaegis-api")[1]["Properties"]["Code"]
        scanner = self.function("openaegis-scanner")[1]["Properties"]["Code"]
        self.assertEqual(api, scanner)

    def test_variables_de_entorno(self):
        # El backend las lee al importar: si falta una, falla TODA la Lambda.
        tables = {"TABLE_NAME", "FINDINGS_TABLE", "SCANS_TABLE"}
        api = self.function("openaegis-api")[1]["Properties"]["Environment"]["Variables"]
        scanner = self.function("openaegis-scanner")[1]["Properties"]["Environment"]["Variables"]
        self.assertEqual(set(api), tables | {"SCANNER_FUNCTION"})
        self.assertEqual(set(scanner), tables)

    def test_el_scanner_no_se_reintenta(self):
        # D93: un scan fallido no se repite solo; lo avisa la alarma.
        self.template.has_resource_properties(
            "AWS::Lambda::EventInvokeConfig",
            {"FunctionName": {"Ref": self.function("openaegis-scanner")[0]}, "MaximumRetryAttempts": 0},
        )

    def test_log_groups_con_retencion_de_una_semana(self):
        for name in ("openaegis-api", "openaegis-scanner"):
            with self.subTest(function=name):
                log_group = self.resources[self.log_group_id(name)]
                self.assertEqual(log_group["Properties"]["LogGroupName"], f"/aws/lambda/{name}")
                self.assertEqual(log_group["Properties"]["RetentionInDays"], 7)
                self.assertEqual(log_group["DeletionPolicy"], "Delete")

    # ---- permisos ----

    def test_permisos_exactos_de_la_api(self):
        actual = {sid: as_list(s["Action"]) for sid, s in self.statements("openaegis-api").items()}
        self.assertEqual(actual, API_PERMISSIONS)

    def test_permisos_exactos_del_scanner(self):
        actual = {sid: as_list(s["Action"]) for sid, s in self.statements("openaegis-scanner").items()}
        self.assertEqual(actual, SCANNER_PERMISSIONS)

    def test_ningun_rol_tiene_managed_policies(self):
        # Sin AWSLambdaBasicExecutionRole, que permite escribir en CUALQUIER log group.
        for name in ("openaegis-api", "openaegis-scanner"):
            with self.subTest(function=name):
                role = self.resources[self.role_id(name)]
                self.assertNotIn("ManagedPolicyArns", role["Properties"])

    def test_solo_lambda_puede_asumir_los_roles(self):
        for name in ("openaegis-api", "openaegis-scanner"):
            with self.subTest(function=name):
                trust = self.resources[self.role_id(name)]["Properties"]["AssumeRolePolicyDocument"]
                principals = [s["Principal"] for s in as_list(trust["Statement"])]
                self.assertEqual(principals, [{"Service": "lambda.amazonaws.com"}])

    def test_cada_lambda_escribe_solo_en_su_log_group(self):
        for name in ("openaegis-api", "openaegis-scanner"):
            with self.subTest(function=name):
                statement = self.statements(name)["EscribirSusLogs"]
                self.assertEqual(statement["Resource"], {"Fn::GetAtt": [self.log_group_id(name), "Arn"]})

    def test_el_scanner_solo_escribe_el_status_de_los_controles(self):
        # La condición que impide que el scanner cambie el título o la severidad (D90).
        statement = self.statements("openaegis-scanner")["EscribirSoloStatusDeControles"]
        self.assertEqual(
            statement["Condition"],
            {
                "ForAllValues:StringEquals": {"dynamodb:Attributes": ["id", "status", "updated_at"]},
                "StringEquals": {"dynamodb:ReturnValues": ["NONE", "UPDATED_OLD", "UPDATED_NEW"]},
            },
        )

    def test_los_permisos_de_dynamodb_apuntan_a_las_tablas_del_stack(self):
        # Referencias (GetAtt), no ARNs escritos a mano: si una tabla cambia de nombre,
        # la policy la sigue.
        tables = set(self.template.find_resources("AWS::DynamoDB::Table"))
        for name in ("openaegis-api", "openaegis-scanner"):
            for sid, statement in self.statements(name).items():
                if not as_list(statement["Action"])[0].startswith("dynamodb:"):
                    continue
                with self.subTest(function=name, sid=sid):
                    self.assertIn(statement["Resource"]["Fn::GetAtt"][0], tables)

    def test_la_api_solo_puede_invocar_al_scanner(self):
        statement = self.statements("openaegis-api")["LanzarScans"]
        self.assertEqual(statement["Resource"], {"Fn::GetAtt": [self.function("openaegis-scanner")[0], "Arn"]})

    def test_el_scanner_no_lee_objetos_de_s3(self):
        # arn:aws:s3:::* son los buckets; los objetos serían arn:aws:s3:::*/*.
        statement = self.statements("openaegis-scanner")["CheckS3ConfigDeBuckets"]
        self.assertEqual(statement["Resource"], {"Fn::Join": ["", ["arn:", {"Ref": "AWS::Partition"}, ":s3:::*"]]})


if __name__ == "__main__":
    unittest.main()
