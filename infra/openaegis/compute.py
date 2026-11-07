"""Las dos Lambdas, con sus roles y sus log groups (Etapa 12.3).

| Lambda            | Handler                | Memoria | Timeout | Rol                                  |
|-------------------|------------------------|---------|---------|--------------------------------------|
| openaegis-api     | handler.lambda_handler | 128 MB  | 3 s     | CRUD de controles + lanzar scans     |
| openaegis-scanner | scanner.lambda_handler | 256 MB  | 30 s    | checks read-only + escribir findings |

Las dos usan el MISMO zip (backend/*.py), igual que en la Etapa 11 (D89).

Permisos: statements escritos a mano, uno por necesidad del código, en vez de los `grant_*` de CDK,
que dan acciones de más. Replican las policies auditadas en las Etapas 7 y 11 (ARCHITECTURE.md §5).
Si el código empieza a usar una acción nueva, hay que agregarla acá; los tests de
tests/test_compute.py fijan la lista exacta.
"""

from pathlib import Path

from aws_cdk import Aws, Duration, RemovalPolicy
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from openaegis.data import Data

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"


def _allow(sid, actions, resources, conditions=None):
    return iam.PolicyStatement(sid=sid, actions=actions, resources=resources, conditions=conditions)


class _Function(Construct):
    """Una Lambda con su rol y su log group. El rol arranca SIN permisos (ni siquiera de logs)."""

    def __init__(self, scope, construct_id, *, name, handler, memory, timeout, code, environment):
        super().__init__(scope, construct_id)

        # Log group explícito: así es parte del stack (`cdk destroy` lo borra) y tiene retención.
        # Si no, Lambda lo crea sola al primer log, fuera del stack y con retención infinita.
        self.log_group = logs.LogGroup(
            self,
            "Logs",
            log_group_name=f"/aws/lambda/{name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Rol propio. Al pasárselo a la Lambda, CDK no le agrega AWSLambdaBasicExecutionRole
        # (que permite escribir en CUALQUIER log group).
        self.role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Execution role de {name}",
        )
        # Solo su propio log group. CreateLogGroup no hace falta: el log group ya existe.
        self.role.add_to_policy(
            _allow(
                "EscribirSusLogs",
                ["logs:CreateLogStream", "logs:PutLogEvents"],
                [self.log_group.log_group_arn],  # termina en ":*" = los streams de ESTE log group
            )
        )

        self.function = lambda_.Function(
            self,
            "Function",
            function_name=name,
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            handler=handler,
            code=code,
            memory_size=memory,
            timeout=Duration.seconds(timeout),
            role=self.role,
            environment=environment,
            log_group=self.log_group,
            logging_format=lambda_.LoggingFormat.JSON,
            application_log_level_v2=lambda_.ApplicationLogLevel.INFO,
            system_log_level_v2=lambda_.SystemLogLevel.INFO,
        )


class Compute(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, data: Data) -> None:
        super().__init__(scope, construct_id)

        # Solo los .py, en la raíz del zip (openapi.yaml y __pycache__ quedan afuera).
        # Un solo asset: se sube una vez y lo usan las dos Lambdas.
        code = lambda_.Code.from_asset(str(BACKEND_DIR), exclude=["*", "!*.py"])

        tables = {
            "TABLE_NAME": data.controls.table_name,
            "FINDINGS_TABLE": data.findings.table_name,
            "SCANS_TABLE": data.scans.table_name,
        }

        scanner = _Function(
            self,
            "Scanner",
            name="openaegis-scanner",
            handler="scanner.lambda_handler",
            memory=256,
            timeout=30,
            code=code,
            environment=tables,
        )
        # Lo invoca la API en forma asincrónica: un scan fallido no se repite solo (D93).
        # Lo avisa la alarma de errores (12.6).
        scanner.function.configure_async_invoke(retry_attempts=0)
        self._scanner_permissions(scanner.role, data)
        self.scanner = scanner.function

        api = _Function(
            self,
            "Api",
            name="openaegis-api",
            handler="handler.lambda_handler",
            memory=128,
            timeout=3,
            code=code,
            environment={**tables, "SCANNER_FUNCTION": scanner.function.function_name},
        )
        self._api_permissions(api.role, data, scanner.function)
        self.api = api.function

    @staticmethod
    def _api_permissions(role, data, scanner_function):
        # controls-table-crud (Etapas 6-7)
        role.add_to_policy(
            _allow(
                "CrudDeControles",
                ["dynamodb:Scan", "dynamodb:GetItem", "dynamodb:PutItem",
                 "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
                [data.controls.table_arn],
            )
        )
        # openaegis-api-scans (Etapa 11)
        role.add_to_policy(_allow("LanzarScans", ["lambda:InvokeFunction"], [scanner_function.function_arn]))
        # Query: el 409 del DELETE. BatchWriteItem: borrar los findings al pasar un control a manual.
        role.add_to_policy(
            _allow("LeerYBorrarFindings", ["dynamodb:Query", "dynamodb:BatchWriteItem"], [data.findings.table_arn])
        )
        role.add_to_policy(_allow("LeerScans", ["dynamodb:Query"], [data.scans.table_arn]))

    @staticmethod
    def _scanner_permissions(role, data):
        # openaegis-scanner-checks (Etapa 11, D90): los Sid son los mismos que en la policy manual.
        statements = [
            _allow("LeerControles", ["dynamodb:Scan"], [data.controls.table_arn]),
            # Puede escribir el resultado del check, pero no el título ni la severidad de un control.
            # `id` va en la lista porque dynamodb:Attributes incluye la clave. ReturnValues limitado:
            # con ALL_OLD, una escritura serviría para LEER el item entero.
            _allow(
                "EscribirSoloStatusDeControles",
                ["dynamodb:UpdateItem"],
                [data.controls.table_arn],
                conditions={
                    "ForAllValues:StringEquals": {"dynamodb:Attributes": ["id", "status", "updated_at"]},
                    "StringEquals": {"dynamodb:ReturnValues": ["NONE", "UPDATED_OLD", "UPDATED_NEW"]},
                },
            ),
            _allow("EscribirFindings", ["dynamodb:Query", "dynamodb:BatchWriteItem"], [data.findings.table_arn]),
            _allow("GuardarScans", ["dynamodb:PutItem"], [data.scans.table_arn]),
            # Los "*" que siguen son acciones de cuenta o de listado: no tienen un ARN al que apuntar.
            _allow("CheckS3AccountPublicAccessBlock", ["s3:GetAccountPublicAccessBlock"], ["*"]),
            _allow("CheckS3ListarBuckets", ["s3:ListAllMyBuckets"], ["*"]),
            _allow(
                "CheckS3ConfigDeBuckets",
                ["s3:GetBucketPublicAccessBlock", "s3:GetBucketPolicy"],
                [f"arn:{Aws.PARTITION}:s3:::*"],  # solo buckets: no incluye objetos (bucket/*)
            ),
            _allow("CheckCloudTrailListar", ["cloudtrail:DescribeTrails"], ["*"]),
            _allow(
                "CheckCloudTrailEstado",
                ["cloudtrail:GetTrailStatus"],
                [f"arn:{Aws.PARTITION}:cloudtrail:*:{Aws.ACCOUNT_ID}:trail/*"],  # trails de cualquier región
            ),
            _allow("CheckIamRootMfa", ["iam:GetAccountSummary"], ["*"]),
        ]
        for statement in statements:
            role.add_to_policy(statement)
