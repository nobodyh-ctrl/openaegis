"""Las tres tablas de DynamoDB (Etapa 12.3). Replican las creadas a mano en las Etapas 6 y 11.

Todas: on-demand, cifrado "Owned by DynamoDB" (sin costo), sin PITR y sin índices.

| Tabla               | Claves                         | Si se borra el stack                       |
|---------------------|--------------------------------|--------------------------------------------|
| openaegis-controls  | PK id                          | SE CONSERVA (RETAIN_ON_UPDATE_OR_DELETE)   |
| openaegis-findings  | PK control_id + SK resource_id | se borra: el próximo scan la vuelve a llenar |
| openaegis-scans     | PK pk + SK started_at          | se borra: se pierde el historial de scans  |

Por qué RETAIN_ON_UPDATE_OR_DELETE y no RETAIN: si el deploy que CREA la tabla falla, el rollback
la borra (está vacía). Con RETAIN quedaría huérfana, y con el nombre fijo el deploy siguiente
fallaría con "already exists".
"""

from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


def _table(scope, construct_id, name, partition_key, sort_key=None, *, keep):
    return dynamodb.Table(
        scope,
        construct_id,
        table_name=name,
        partition_key=dynamodb.Attribute(name=partition_key, type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name=sort_key, type=dynamodb.AttributeType.STRING) if sort_key else None,
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        encryption=dynamodb.TableEncryption.DEFAULT,
        # La protección contra borrado también frena un `delete-table` hecho a mano.
        deletion_protection=keep,
        removal_policy=RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE if keep else RemovalPolicy.DESTROY,
    )


class Data(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        # Los controles los carga el usuario: perderlos es perder trabajo.
        self.controls = _table(self, "Controls", "openaegis-controls", "id", keep=True)
        # Findings y scans los genera el scanner.
        self.findings = _table(self, "Findings", "openaegis-findings", "control_id", "resource_id", keep=False)
        self.scans = _table(self, "Scans", "openaegis-scans", "pk", "started_at", keep=False)
