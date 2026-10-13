# ADR-004: DynamoDB on-demand como base de datos de controles

- **Estado:** aceptada
- **Fecha:** 2026-10-08 (Etapa 6)
- **Decisiones relacionadas:** D32–D45, D50, D53, D54 ([DECISIONS.md](../DECISIONS.md)) · detalle en [06-dynamodb.md](../06-dynamodb.md)

## Contexto

La Lambda es stateless: los controles necesitan persistencia. Las operaciones de la app son pocas y conocidas: listar todos los controles y obtener, crear, editar o borrar **uno** por su id. El volumen es de decenas de items. Más adelante (Etapa 11) se van a guardar **findings**, con relación 1:N con los controles. La base tiene que encajar en una arquitectura serverless y no requerir secretos.

## Decisión

Una tabla **DynamoDB** `cloud-sec-checklist-controls`, **on-demand**, con partition key **`id` (UUID v4 generado por el backend)** y **sin sort key**. Un atributo `code` legible (`S3-001`) es único, y esa unicidad se valida en el código. Cifrado *Owned by Amazon DynamoDB*, sin PITR, sin índices. La Lambda accede con una **inline policy** de 5 acciones (`Scan`, `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`) sobre esa sola tabla. Todas las escrituras son **condicionales**.

## Por qué

- **Serverless de verdad:** sin servidor, pago por request, escala sola.
- **Acceso por IAM:** no hay usuario ni contraseña de base de datos que guardar o filtrar.
- Los access patterns son simples: 4 de las 5 operaciones van a **un** item por su PK (`GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`), y solo el listado usa `Scan`.
- **UUID como PK:** la PK es inmutable en DynamoDB; los findings van a referenciar un id que nunca cambia, aunque se renombre el `code`.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| RDS / Aurora (PostgreSQL, MySQL) | Cobra por hora encendido y requiere credenciales (Secrets Manager, con costo); los joins y las consultas ad-hoc no se necesitan |
| Provisioned 5 WCU / 5 RCU (Free Tier) | Si se supera la capacidad, DynamoDB rechaza requests y el usuario ve 500; el throttling de API Gateway ya pone el techo |
| `code` como partition key | No se podría renombrar sin borrar y recrear; las referencias desde los findings se romperían |
| PK `id` + SK `created_at` | Obliga a enviar la fecha en cada operación, sin beneficio (un item por `id`) |
| Unicidad de `code` con una transacción que reserva el `code` | Correcto a escala, pero complejo para la V1 |
| Single-table design (controles y findings juntos) | Más eficiente a gran escala, más difícil de entender |

## Ventajas

- Costo de fracciones de centavo y almacenamiento dentro de los 25 GB del Free Tier.
- Sin credenciales de base de datos ni puertos expuestos.
- Least privilege granular: acciones concretas sobre un ARN concreto.
- Latencia constante en las operaciones por clave.

## Desventajas

- **Sin joins ni foreign keys:** la relación control–finding la mantiene el código.
- Una consulta nueva puede requerir un índice nuevo o rediseñar las claves.
- Los reportes tipo `GROUP BY` se resuelven en el código (con decenas de items no importa; con millones, sí).
- **Trampas que hay que conocer:** `Limit` en un Scan con filtro (causó dos `S3-002` duplicados), `UpdateItem` es un upsert, `DeleteItem` no avisa si el item no existe, palabras reservadas.
- La unicidad de `code` tiene una *race condition* teórica.
- Los números vuelven como `Decimal` en Python.
- On-demand **no tiene techo propio**.

## Consideraciones de seguridad

- Rol sin `DeleteTable` ni acceso a otras tablas: *blast radius* acotado.
- Escrituras condicionales: sin sobrescrituras, sin upserts, sin borrados silenciosos.
- Allowlist de campos (`FIELD_RULES`) contra mass assignment; `id`, `created_at` y `updated_at` los pone el servidor.
- Sin SQL injection clásica; igual, los valores siempre van como marcadores en las expresiones.
- **Riesgo aceptado temporalmente:** deletion protection está desactivado para poder recrear la tabla con CDK, y no hay PITR.

## Consideraciones de costo

On-demand: USD 0,625 por millón de escrituras y USD 0,125 por millón de lecturas en `us-east-1` (verificado el 2026-10-08, [06-dynamodb.md](../06-dynamodb.md#7-costos)); 25 GB de almacenamiento gratis. PITR, KMS propio y auto scaling quedaron fuera por su costo. El techo de gasto lo pone el throttling de API Gateway.

## Consecuencias

- La validación del esquema vive en el código (`validation.py`): DynamoDB no la hace.
- `repository.py` es el único módulo que conoce boto3 y traduce las excepciones de DynamoDB (`None` = no existe).
- La tabla de findings (Etapa 11) se diseña a partir de un requisito ya conocido: consultar por `control_id` de forma eficiente, para responder **409** al borrar un control con findings.

## Evolución futura

- Etapa 11: tabla de findings (probablemente PK `control_id` + SK con fecha) y el 409 en el `DELETE`.
- Etapa 12: recrear la tabla con CDK y reevaluar deletion protection y PITR.
- Si el volumen creciera, el listado con `Scan` y la unicidad de `code` serían los primeros puntos a revisar (por ejemplo, con un GSI sobre `code`).
