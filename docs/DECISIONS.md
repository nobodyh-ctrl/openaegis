# Decisiones técnicas

> Índice de **todas** las decisiones del proyecto. D1–D31 están desarrolladas en el doc de cada etapa (acá solo el resumen y el enlace). D32–D54 (Etapa 6) están acá con sus alternativas completas y resumidas en [06-dynamodb.md](06-dynamodb.md).
> **Próximo número libre: D61.** Cada decisión nueva se agrega acá y en el doc de su etapa.
> Las decisiones grandes tienen además un **ADR** completo (D55):
>
> | ADR | Tema | Decisiones |
> |---|---|---|
> | [ADR-001](architecture-decisions/001-serverless.md) | Arquitectura serverless (Lambda + API Gateway) | D6–D8, D18–D23, D46 |
> | [ADR-002](architecture-decisions/002-s3-cloudfront.md) | Frontend en S3 privado + CloudFront con OAC | D9–D17 |
> | [ADR-003](architecture-decisions/003-http-api.md) | API Gateway HTTP API | D22, D26–D31, D41, D42 |
> | [ADR-004](architecture-decisions/004-dynamodb.md) | DynamoDB on-demand | D32–D45, D50, D53, D54 |
> | [ADR-005](architecture-decisions/005-deployment-model.md) | Modelo de despliegue self-hosted single-account | D48, D2 |

## D1–D31 (documentadas por etapa)

| # | Decisión | Doc |
|---|---|---|
| D1 | Trabajar con un IAM user, no con el root | [00](00-account-setup.md#3-decisiones-técnicas) |
| D2 | No usar IAM Identity Center (requiere Organizations → la cuenta pasa al Paid plan y vencen los créditos) | [00](00-account-setup.md#3-decisiones-técnicas) |
| D3 | `AdministratorAccess` para el usuario de trabajo, asignado vía grupo `Admins` | [00](00-account-setup.md#3-decisiones-técnicas) |
| D4 | Sin access keys (CLI vía CloudShell) | [00](00-account-setup.md#3-decisiones-técnicas) |
| D5 | Región única `us-east-1` | [00](00-account-setup.md#3-decisiones-técnicas) |
| D6 | Arquitectura serverless | [01](01-cloud-fundamentals.md#4-decisiones-técnicas) |
| D7 | Una sola región, aceptando el riesgo de caída regional | [01](01-cloud-fundamentals.md#4-decisiones-técnicas) |
| D8 | No usar EC2, RDS, ECS, EKS, NAT Gateway ni load balancers | [01](01-cloud-fundamentals.md#4-decisiones-técnicas) |
| D9 | Frontend en S3 privado + CloudFront con OAC | [02](02-s3.md#3-decisiones-técnicas) |
| D10 | Versioning desactivado en el bucket del frontend | [02](02-s3.md#3-decisiones-técnicas) |
| D11 | Tag `Project = cloud-security-checklist` en todos los recursos | [02](02-s3.md#3-decisiones-técnicas) |
| D12 | Recursos creados a mano primero; se recrean con CDK | [02](02-s3.md#3-decisiones-técnicas) |
| D13 | OAC (no OAI, no bucket público) | [03](03-cloudfront.md#3-decisiones-técnicas) |
| D14 | CloudFront pay-as-you-go (el Free plan no es elegible para flat-rate) | [03](03-cloudfront.md#3-decisiones-técnicas) |
| D15 | Sin AWS WAF | [03](03-cloudfront.md#3-decisiones-técnicas) |
| D16 | Dominio `*.cloudfront.net` | [03](03-cloudfront.md#3-decisiones-técnicas) |
| D17 | Standard logging de CloudFront desactivado | [03](03-cloudfront.md#3-decisiones-técnicas) |
| D18 | Lambda para el backend | [04](04-lambda.md#3-decisiones-técnicas) |
| D19 | Python 3.14 | [04](04-lambda.md#3-decisiones-técnicas) |
| D20 | arm64 (Graviton) | [04](04-lambda.md#3-decisiones-técnicas) |
| D21 | 128 MB / timeout 3 s | [04](04-lambda.md#3-decisiones-técnicas) |
| D22 | Sin Function URL | [04](04-lambda.md#3-decisiones-técnicas) |
| D23 | Sin VPC | [04](04-lambda.md#3-decisiones-técnicas) |
| D24 | Execution role creado por la consola (se reescribe con CDK) | [04](04-lambda.md#3-decisiones-técnicas) |
| D25 | Retención de logs de 1 semana | [04](04-lambda.md#3-decisiones-técnicas) |
| D26 | HTTP API (no REST API) | [05](05-api-gateway.md#3-decisiones-técnicas) |
| D27 | Throttling rate 10 / burst 20 | [05](05-api-gateway.md#3-decisiones-técnicas) |
| D28 | CORS restringido al dominio de CloudFront | [05](05-api-gateway.md#3-decisiones-técnicas) |
| D29 | CORS gestionado por API Gateway | [05](05-api-gateway.md#3-decisiones-técnicas) |
| D30 | Frontend y API en orígenes distintos | [05](05-api-gateway.md#3-decisiones-técnicas) |
| D31 | Logs con método, path y request IDs; nunca el event completo | [05](05-api-gateway.md#3-decisiones-técnicas) |

## D32 en adelante (Etapa 6 y posteriores; todavía no están en un doc de etapa)

Todas tomadas con el usuario entre el 2026-10-08 y el 2026-10-10 [CONVERSACIÓN].

| # | Tema | Decisión | Por qué | Alternativas descartadas |
|---|---|---|---|---|
| D32 | Base de datos | **DynamoDB** | Serverless de verdad: sin servidor, pago por uso, acceso por IAM (sin credenciales de base de datos que guardar). Access patterns simples y conocidos | RDS/Aurora: cobra por hora encendido y requiere secretos (Secrets Manager tiene costo). Desventajas aceptadas: sin joins, consultas nuevas pueden requerir índices, reportes tipo `GROUP BY` en el código |
| D33 | Capacity mode | **On-demand** | Costo de fracciones de centavo; el throttling de API Gateway (D27) le pone techo | Provisioned 5 WCU/5 RCU (Free Tier): si se supera la capacidad, la Lambda recibe throttling y el usuario ve 500 |
| D34 | Claves | PK **`id` = UUID v4** generado por el backend + **`code`** legible y editable (`S3-001`) | La PK no se puede modificar en DynamoDB; los findings van a referenciar un id que nunca cambia; sin colisiones (clave sustituta + clave natural) | `code` como PK |
| D35 | Sort key | **Ninguna** en `controls` | Hay un solo item por `id`; una SK `created_at` obligaría a enviar la fecha en cada operación. La SK tiene sentido en los findings | PK `id` + SK `created_at` (propuesta inicial del usuario) |
| D36 | Unicidad de `code` | Validada **en el código** con un Scan paginado **sin `Limit`** antes de crear/editar → 409 | Simple. *Race condition* teórica aceptada (un usuario, decenas de controles) | Transacción con un item que "reserva" el `code` (correcto a escala, complejo para la V1) |
| D37 | Severidad | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` | Escala estándar de la industria | Otra escala |
| D38 | Fechas y estado | `created_at`/`updated_at` los pone el servidor, string ISO 8601 UTC; `status` default `REVIEW` | DynamoDB no tiene tipo fecha; en ISO el orden alfabético = cronológico; UTC sin ambigüedad | — |
| D39 | Findings | **Tabla aparte**, relación 1:N por `control_id` (no hay foreign keys: la relación la mantiene el código). Se diseña en la Etapa 11 | Claridad | *Single-table design* (más eficiente a escala, más difícil de entender) |
| D40 | Borrado | **No se puede borrar un control que tiene findings → 409**. Requisito: la tabla de findings tiene que poder consultarse por `control_id` eficientemente | No perder historial de evaluaciones por un clic | Borrar en cascada; dejar findings huérfanos |
| D41 | Rutas | REST: `GET/POST /controls`, `GET/PATCH/DELETE /controls/{id}` | La URL nombra el recurso, el método es el verbo | `/edit/control`, `/estado/control` (verbos en la URL) |
| D42 | Edición y cambio de estado | **`PATCH /controls/{id}`** para ambos; sin ruta propia para el estado | Semántica REST (modificación parcial), idempotencia, menos rutas y menos statements en la resource-based policy | `PUT` (reemplazo completo); `POST` (el usuario lo preguntó; no es idempotente) |
| D43 | SDK | **`boto3.resource`** | Devuelve JSON "normal" en vez del DynamoDB JSON tipado. Ojo: los números vuelven como `Decimal` (se resuelve en `responses._json_default`) | `boto3.client` |
| D44 | IAM del rol | Inline policy `controls-table-crud`: `Scan`, `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` **solo** sobre el ARN de la tabla | Least privilege | `AmazonDynamoDBFullAccess`, `dynamodb:*` (incluiría `DeleteTable`) |
| D45 | Configuración de la tabla | Standard, cifrado *Owned by Amazon DynamoDB*, sin PITR, sin GSI, **deletion protection desactivado temporalmente** | Sin costo extra; la protección haría fallar el borrado de la tabla manual al migrar a CDK. Se rediscute en la Etapa 12 | KMS (cobra por clave y uso); PITR (tiene costo); Standard-IA (encarece lecturas) |
| D46 | Estructura del backend | **5 módulos** (opción A): `handler`, `controls`, `validation`, `repository`, `responses`. Python puro | Testabilidad sin AWS, agregar checks/findings sin tocar lo existente, migración futura cambiando solo `handler.py` | **FastAPI + Mangum** (descartado para la V1: empaquetar `pydantic-core` para Linux arm64 desde Windows, más cold start, más supply chain; va al Bloque B). **Lambda Powertools** (alternativa considerada; su logger es candidato para la Etapa 10) |
| D47 | Deploy del código | Zip de `backend/*.py` subido por la consola; handler `handler.lambda_handler`; **el repo es la fuente de verdad** (no editar en la consola) | Un solo paso manual hasta tener CDK | Editar varios archivos en el editor de la consola |
| D48 | Modelo de despliegue | **Self-hosted, single-account**: cada usuario despliega su copia en su cuenta (`git clone` + `cdk deploy` desde la Etapa 12) y evalúa esa cuenta. Los datos no salen de la cuenta; cada uno paga su consumo; los permisos read-only se pueden auditar antes de desplegar (`cdk diff`) | Simple, seguro, coherente con open source | CLI local; SaaS multi-tenant (findings de todos los clientes en una sola nube, aislamiento entre tenants, costos); híbrido. Multi-cuenta y SaaS → revisión V1 → V2 |
| D49 | Validación | Reglas como datos (`FIELD_RULES`): tipo `str` → `strip` → obligatorio no vacío → largo → enums. Es también la **allowlist** contra mass assignment | Un único lugar para POST y PATCH; evita 500 por tipos inesperados | `if` explícitos por campo |
| D50 | Escrituras condicionales | `PutItem` con `attribute_not_exists(id)`; `UpdateItem` con `attribute_exists(id)` | `PutItem` pisa sin avisar; `UpdateItem` es un *upsert* y sin condición el `PATCH` sería una puerta trasera para crear controles inválidos | Leer antes de escribir |
| D51 | Manejo de errores | Atrapar **solo** lo que se sabe manejar (`ConditionalCheckFailedException` → `None` en el repositorio). Sin `except Exception` | Un `except` amplio oculta errores de la métrica *Errors* y del traceback | `except Exception` → 500 genérico |
| D52 | Traducción de errores | Cada capa habla su idioma: el repositorio devuelve `None`, `validation.py` devuelve mensajes y `controls.py` decide el status code | Desacople de AWS y de HTTP | Lanzar respuestas HTTP desde la validación (era así antes del refactor) |
| D53 | Borrado de controles | **Borrado real** (`DeleteItem`) permitido; cuando existan findings (Etapa 11), **409 si el control tiene findings** (D40). Decidida el 2026-10-13 | Un control es una **definición** (regla), no un registro histórico: el historial de evaluaciones vive en los findings, y D40 lo protege justo cuando existe. Resuelve duplicados y errores de carga (los dos `S3-002`). Lo pide el requisito original ("eliminar"). Quién borró qué: logs de CloudWatch hoy, usuario con Cognito (Etapa 9), audit trail completo en la V2 | **Soft delete** (`archived_at`: todas las consultas filtran, el `code` archivado ocupa lugar, el Scan los sigue leyendo; evolución posible si aparece la necesidad de recuperar controles). **No permitir borrar** (contradice el requisito; los errores quedan para siempre o se borran a mano en la consola) |
| D54 | Semántica del `DELETE` | `DeleteItem` con `attribute_exists(id)` → **404** si no existe; **200 + item borrado** (`ReturnValues="ALL_OLD"`); se loguea el `code` borrado. Decidida el 2026-10-13 | `DeleteItem` responde éxito aunque el item no exista: sin condición, un id mal escrito parece un borrado exitoso. Misma técnica que el `PATCH` (D50). `ALL_OLD` evita una lectura extra y sirve `build_response` sin cambios | Éxito silencioso (idempotencia estricta); 204 sin body (requiere un caso especial en `responses.py`) |
| D55 | Documentación de decisiones | **`DECISIONS.md` como índice** de todas las decisiones (una línea cada una) + **ADR completo solo para las decisiones grandes** (`docs/architecture-decisions/NNN-tema.md`). Decidida el 2026-10-13 | No duplicar 50+ decisiones; los ADRs quedan para lo que vale la pena explicar a fondo (contexto, alternativas, ventajas, desventajas, seguridad, costo, evolución) | Un ADR por decisión (texto repetido para decisiones chicas); solo `DECISIONS.md` (no cumple el formato pedido en el documento de evolución) |
| D56 | Etapa 7 · H1: `logs:CreateLogGroup` | **Restringirlo al log group de la función** (versión `v2` de la policy creada por la consola; `v1` queda para rollback). Decidida el 2026-10-13; **aplicada y verificada el 2026-10-15** con `simulate-principal-policy`: propio → `allowed`, otro → `implicitDeny` | Least privilege sin perder la capacidad de recrear el log group si se borra | Quitar la acción (si se borra el log group, la Lambda deja de loguear en silencio); dejarlo sobre toda la cuenta |
| D57 | Etapa 7 · H2: permisos de invocación | **Un statement por ruta, con el método** en el `SourceArn` (`.../*/GET/controls`), en lugar de uno por path con método comodín. Se agregan los nuevos antes de borrar los viejos. Decidida el 2026-10-13; **aplicada y verificada el 2026-10-15**: 5 statements `apigw-<método>-<ruta>`, las 5 rutas responden 200 antes y después de borrar los 2 viejos | Precisión: solo las 5 rutas del CRUD pueden invocar la Lambda. Práctica de `add-permission` / `remove-permission` | Dejar el comodín hasta CDK |
| D58 | Etapa 7 · verificación | **IAM Access Analyzer solo de _external access_** (tipo `ACCOUNT`, zona de confianza = la cuenta). Decidida el 2026-10-13 | Gratis según la página oficial de precios; verifica con una herramienta de AWS que ninguna resource-based policy dé acceso fuera de la cuenta | Analyzers de *unused access* (USD 0,20 por rol/usuario/mes) e *internal access* (USD 9 por recurso/región/mes): con costo y sin necesidad actual. **Creado y verificado el 2026-10-15**: `openaegis-external-access`, tipo `ACCOUNT`, analizó 1 bucket, 1 función, 1 tabla y 6 roles; **0 findings activos** |
| D59 | Alcance de la Etapa 13 (CI/CD) | **Opción A: CI sin credenciales de AWS** en la V1 (tests, chequeos y, con CDK, `cdk synth`). Deploy automático y OIDC → Bloque B. Decidida el 2026-10-15 | Resuelve la contradicción entre el prompt original (CI/CD en la V1) y el documento de evolución (CI/CD en el Bloque B): la V1 queda probada automáticamente sin que el CI toque la cuenta | Opción B: todo el CI/CD al Bloque B |
| D60 | Orden del roadmap: CI | Adelantar una **Etapa 13a — CI mínimo** antes de la Etapa 8: tests unitarios de `validation.py` y `responses.py` (`unittest`, sin dependencias) + chequeo de identificadores reales en el repo. `cdk synth` se suma en la Etapa 12. Decidida el 2026-10-15 | Dos problemas actuales: el código no se verifica antes del deploy, y el riesgo de publicar IDs (cuenta, API, CloudFront) crece en la Etapa 8, cuando el frontend necesite la URL de la API | Hacerlo en la Etapa 13 como estaba previsto; pasarlo al Bloque B |

## Propuestas (no decididas)

| Tema | Propuesta | Estado |
|---|---|---|
| Testing (Etapa 14) | **moto** para tests unitarios (sin Docker). **Floci** como candidato de tests de integración en el Bloque B (no aplica IAM por defecto; requiere el socket de Docker). AWS real para lo que dependa de IAM | [PROPUESTA] |
| Alcance de la Etapa 13 | Resuelto: opción A (D59) y Etapa 13a adelantada (D60) | ✅ |
| Permisos de los checks (Etapa 11) | `SecurityAudit` (administrada por AWS, simple, da mucho más de lo necesario) vs. policy propia mínima (least privilege estricto, hay que mantenerla) | [PENDIENTE] |
| CLI | Reutilizar los checks desde una CLI local | [PROPUESTA] para la revisión V1 → V2 |
| Terraform | CDK para la app, Terraform para un *security lab* | Hipótesis del usuario, no decidida |
| API bajo CloudFront | Servir la API en `/api/*` (mismo origen, sin CORS) | Mejora posible mencionada en D30 |

## Preguntas abiertas para el usuario

1. **Nombre:** el repo de GitHub **ya se llama `openaegis`** (verificado el 2026-10-15). Quedan: ¿actualizar la URL del remoto local? ¿Renombrar los recursos de AWS (`cloud-sec-checklist-*`) cuando se recreen con CDK? (Engram toma el nombre del proyecto del remoto.)
2. **Etapa 11:** ¿`SecurityAudit` o policy propia?
3. **Enums:** ¿aceptar `"high"` normalizando con `.upper()`, o mantener el 400?
4. **Opcionales vacíos:** hoy `"description": ""` se guarda como string vacío. ¿Guardarlo así, omitir el atributo o, en `PATCH`, usarlo para **borrar** el campo (`REMOVE`)?
5. **`CLAUDE.md`:** Claude Code lee automáticamente `CLAUDE.md`, no `AGENTS.md`. ¿Crear un `CLAUDE.md` mínimo que remita a `AGENTS.md`?
