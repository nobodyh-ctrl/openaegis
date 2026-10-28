# ADR-009: Checks read-only en una Lambda aparte, con findings como estado actual

- **Estado:** aceptada
- **Fecha:** 2026-10-25 → 2026-10-28 (Etapa 11)
- **Decisiones relacionadas:** D89–D101 ([DECISIONS.md](../DECISIONS.md)) · se apoya en [ADR-001](001-serverless.md) (Lambda), [ADR-004](004-dynamodb.md) (DynamoDB) y [ADR-005](005-deployment-model.md) (single-account, permisos auditables) · detalle en [11-checks.md](../11-checks.md)

## Contexto

Hasta la Etapa 10, el estado de cada control lo cargaba una persona: nadie verificaba la cuenta. La V1 promete **checks automáticos de solo lectura** que generen findings y un score.

Requisitos:

- evaluar la cuenta **sin modificar nada** y con permisos que alguien pueda revisar antes de instalar (D48);
- que un bug en la API no le dé acceso a la configuración de toda la cuenta;
- consultar los findings de un control de forma eficiente (D40: no borrar un control con findings);
- que nadie pueda tapar a mano un resultado del scanner;
- testear los checks sin AWS;
- sin dependencias nuevas, sin servidores y dentro del free tier.

## Decisión

- **Una Lambda aparte, `openaegis-scanner`**, con el mismo zip que la API, otro handler y **su propio rol** (D89).
- **Policy propia mínima** con solo las acciones de lectura de los checks (D90). La única escritura sobre la tabla de controles está limitada por una **condición de IAM** a los atributos `status` y `updated_at` (D94).
- **Findings como estado actual** (PK `control_id`, SK `resource_id`) + una tabla de **resúmenes de scans** como historial (D91).
- Un control es automático si tiene **`check_id`**, validado contra los checks que existen (D92). El scanner escribe su `status`; la API rechaza con `409` el cambio manual (D94).
- La API dispara el scan de forma **asincrónica** (`202`) y la SPA espera con **polling** (D93, D100).
- Los checks **no importan boto3**: reciben los clientes por parámetro (inyección de dependencias).

## Por qué

- Separar los roles achica el *blast radius*: el rol de la API solo toca sus tablas y puede invocar al scanner; el del scanner lee configuración y no puede editar controles más allá del status.
- Una herramienta de seguridad que pide `SecurityAudit` da mal ejemplo: es lo primero que mira quien la quiere instalar.
- El estado actual responde lo que muestra la app (findings vigentes, `Query` por control); el historial del score queda en los resúmenes.
- `202 Accepted` es justamente el código HTTP de "lo proceso después", y deja a la API con su timeout de 3 s.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| Checks en la Lambda de la API | Su rol pasaría a leer la configuración de toda la cuenta; timeout de 3 s |
| `SecurityAudit` | Lectura de cientos de servicios que no se usan; AWS la cambia cuando quiere |
| Historial completo de findings por recurso | Para ver lo actual hay que filtrar por el último scan; la tabla crece sin fin |
| Tabla por scan con un GSI por control | Un índice extra desde el día 1 |
| Vincular check y control por `code` | El `code` es editable: el check quedaría huérfano |
| Scan sincrónico | Timeout de la API; dos Lambdas facturando a la vez |
| Calcular el status al leer o en la SPA | N+1 consultas, o la regla de negocio en el frontend |

## Ventajas

- Permisos mínimos y auditables, con escritura limitada por atributo.
- 35 tests de los checks sin AWS, en milisegundos.
- La SPA y el score siguen leyendo `status` como antes.
- Agregar un check = una función + su entrada en `CHECKS` + sus acciones en la policy.

## Desventajas

- Cada check nuevo exige actualizar la policy a mano (hasta CDK, Etapa 12).
- Dos Lambdas que hay que desplegar juntas: el zip es el mismo y la API valida `check_id` con `CHECKS`.
- Sin historial por recurso ("¿desde cuándo falla este bucket?").
- El polling hace algunas requests de más.

## Consideraciones de seguridad

- Ninguna acción del scanner lee datos (objetos de S3, eventos de CloudTrail) ni modifica recursos evaluados.
- La condición `dynamodb:Attributes` incluye la clave (`id`); `dynamodb:ReturnValues` impide leer el item entero al actualizar.
- La evidencia guarda el código del error, nunca el mensaje (trae ARNs con la cuenta); los recursos de cuenta se guardan como `account`/`root`.
- Reintentos asincrónicos en 0: un scan fallido no se repite en silencio; lo avisa la alarma `openaegis-scanner-errors`.
- Un finding `ERROR` deja el control en `REVIEW`, nunca en `PASS`.

## Consideraciones de costo

USD 0 dentro del free tier: Lambda de pocos segundos por scan, dos tablas on-demand con pocos items y llamadas de lectura sin cargo. La remediación de los `FAIL` (D101) suma centavos de S3 por el bucket del trail, con techo de 90 días.

## Consecuencias

- El modelo *Security Check → Finding → Report* queda separado en el código: `checks.py` (sin AWS), `findings_repository.py` (persistencia) y la SPA (reporte).
- La V2 (remediación) va a necesitar **otro** rol con permisos de escritura y aprobación: no se amplía este.
- CDK (Etapa 12) tiene que crear la Lambda, las tablas, los dos roles con estas policies exactas y la alarma.

## Evolución futura

- Scans programados con EventBridge, sin rehacer nada.
- Gráfico de evolución del score con la tabla de scans.
- Alarma por findings `ERROR` (metric filter).
- Checks regionales (por ejemplo, de EC2): ahí se decide cómo recorrer regiones (D98).
- Una CLI que reutilice `checks.py`: ya no depende de Lambda ni de boto3 directamente.
