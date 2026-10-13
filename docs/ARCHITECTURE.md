# Arquitectura implementada

> Estado al 2026-10-12. Describe **solo lo que existe**. Lo planificado está en [ROADMAP.md](ROADMAP.md).
> Marcas: **[CONFIRMADO-REPO]** = leído en el código · **[CONVERSACIÓN]** = configurado a mano en la consola según el historial, sin verificación independiente · **[INCIERTO]** = verificar.

## 1. Vista general

```text
                           Navegador
                 ┌────────────┴─────────────┐
                 │ HTTPS                    │ HTTPS + CORS (fetch / curl)
                 ▼                          ▼
        ┌─────────────────┐       ┌───────────────────────────┐
        │   CloudFront    │       │  API Gateway (HTTP API)   │
        │ OAC · HTTP→HTTPS│       │  stage $default           │
        └────────┬────────┘       │  throttling 10/20 · CORS  │
                 │ s3:GetObject   └────────────┬──────────────┘
                 │ (firmado, OAC)              │ lambda:InvokeFunction
                 ▼                             │ (resource-based policy)
        ┌─────────────────┐                    ▼
        │ S3 (privado)    │       ┌───────────────────────────┐      ┌────────────────────┐
        │ index.html      │       │ Lambda cloud-sec-         │─────►│ CloudWatch Logs    │
        │ (de prueba)     │       │ checklist-api (Py 3.14)   │ logs │ retención 1 semana │
        └─────────────────┘       └────────────┬──────────────┘      └────────────────────┘
                                               │ execution role:
                                               │ Scan/Get/Put/Update/DeleteItem
                                               ▼
                                  ┌───────────────────────────┐
                                  │ DynamoDB                  │
                                  │ cloud-sec-checklist-      │
                                  │ controls (on-demand)      │
                                  └───────────────────────────┘
```

Todo en **`us-east-1`**, en una sola cuenta. Hoy el frontend **no** consume la API (solo hubo un `fetch` de prueba en la Etapa 5): son dos caminos independientes. El frontend real es la Etapa 8.

**Diagramas del repo:**

- [architecture/architecture.drawio.png](../architecture/architecture.drawio.png) — ⚠️ **desactualizado**: todavía muestra API Gateway y DynamoDB como "planificados". Hay que actualizarlo (editable con la extensión draw.io de VS Code; fondo blanco para que se lea en el modo oscuro de GitHub).
- [architecture/permissions-flow.drawio.png](../architecture/permissions-flow.drawio.png) — "quién le pide permiso a quién", flechas ① a ⑤.

## 2. Recursos de AWS [CONVERSACIÓN]

Todos creados **a mano en la consola**, con tag `Project = cloud-security-checklist`. CDK los va a reemplazar en la Etapa 12.

| Recurso | Configuración relevante | Doc |
|---|---|---|
| S3 `cloud-sec-checklist-frontend-<sufijo>` | Privado, BPA 4/4, ACLs desactivadas (*bucket owner enforced*), SSE-S3, sin versioning, sin Object Lock | [02-s3.md](02-s3.md) |
| CloudFront `cloud-sec-checklist-frontend` | Pay-as-you-go, OAC, bucket policy con `AWS:SourceArn` = la distribución, redirect HTTP→HTTPS, default root object `index.html`, dominio `<distribucion>.cloudfront.net`, sin WAF, sin logging | [03-cloudfront.md](03-cloudfront.md) |
| Lambda `cloud-sec-checklist-api` | Python 3.14, arm64, 128 MB, timeout 3 s, sin Function URL, sin VPC, handler `handler.lambda_handler`, env `TABLE_NAME=cloud-sec-checklist-controls` | [04-lambda.md](04-lambda.md) |
| Execution role `cloud-sec-checklist-api-role-<sufijo>` | Trust: `lambda.amazonaws.com`. Policy de logs creada por la consola + inline **`controls-table-crud`** (ver §5) | [04-lambda.md](04-lambda.md) |
| Log group `/aws/lambda/cloud-sec-checklist-api` | Retención 1 semana | [04-lambda.md](04-lambda.md) |
| HTTP API `cloud-sec-checklist-http-api` | Stage `$default` con auto-deploy · throttling rate 10 / burst 20 · CORS Allow-Origin = solo `https://<distribucion>.cloudfront.net` · Allow-Headers `content-type` · Allow-Methods: `POST` en la Etapa 5; en la Etapa 6 se indicó agregar `GET`, `PATCH`, `DELETE` [INCIERTO: no hay salida que lo confirme] | [05-api-gateway.md](05-api-gateway.md) |
| DynamoDB `cloud-sec-checklist-controls` | PK `id` (String), sin sort key, on-demand, Standard, cifrado *Owned by Amazon DynamoDB*, **deletion protection desactivado** (a propósito, para la migración a CDK), sin PITR, sin GSI | Pendiente: `06-dynamodb.md` |

### Rutas configuradas en API Gateway

| Ruta | ¿Existe en API Gateway? |
|---|---|
| `POST /hello` | Sí (temporal, a eliminar) |
| `GET /controls` | Sí (respondió 200) |
| `GET /controls/{id}` | Sí (respondió 200/400/404) |
| `POST /controls` | Sí (respondió 201/400/409) |
| `PATCH /controls/{id}` | Sí: respondió **200** a un `curl` el 2026-10-10, así que la ruta existe y está integrada |
| `DELETE /controls/{id}` | Sí: respondió 200/404/400 el 2026-10-13 |

**Resource-based policy de la Lambda** (verificada con `aws lambda get-policy` el 2026-10-13): **3 statements, uno por _path_, no uno por ruta**: `/hello`, `/controls` y `/controls/{id}`. El `SourceArn` tiene la forma `.../<api-id>/*/*/<path>`: el segundo `*` es el **método**, así que el statement de `/controls` cubre `GET` y `POST`, y el de `/controls/{id}` cubre `GET`, `PATCH` y `DELETE`. Por eso `PATCH` y `DELETE` funcionaron sin agregar statements. Restringir también por método (`.../*/GET/controls`) sería más estricto [PROPUESTA para la Etapa 7 / CDK].

## 3. Backend [CONFIRMADO-REPO]

Python puro, **sin dependencias externas** (boto3 viene en el runtime). Separado en 5 módulos con dependencias en un solo sentido:

```text
handler.py ──► controls.py ──► validation.py      (sin AWS ni HTTP)
   │                │
   │                ├────────► repository.py ──► DynamoDB (boto3)
   │                │
   └────────────────┴────────► responses.py       (formato API Gateway)
```

| Archivo | Responsabilidad | Sabe de… | No sabe de… |
|---|---|---|---|
| [handler.py](../backend/handler.py) | `ROUTES` (`routeKey` → función) y `lambda_handler`. Loguea `routeKey` + request ID de API Gateway + request ID de Lambda. Ruta desconocida → 404 | El event de API Gateway | DynamoDB, validaciones |
| [controls.py](../backend/controls.py) | `list_controls`, `get_control`, `create_control`, `update_control`, `hello` (temporal). Decide los status codes | Reglas de negocio (400/404/409/201) | boto3 |
| [validation.py](../backend/validation.py) | `SEVERITY_VALUES`, `STATUS_VALUES`, `FIELD_RULES`, `validate_fields(body, partial=False)`, `validate_control_id`. Devuelve **mensajes**, no respuestas HTTP | Qué es un control válido | AWS, HTTP |
| [repository.py](../backend/repository.py) | `table` (creada en el cold start), `_scan_all` paginado, `list_controls`, `get_control`, `find_control_by_code`, `create_control`, `update_control`. Traduce `ConditionalCheckFailedException` a `None` | DynamoDB | HTTP |
| [responses.py](../backend/responses.py) | `build_response` (con `_json_default` para `Decimal`), `error_response`, `parse_json_body` | Payload 2.0 | DynamoDB |

Por qué esta separación (D46): testear la validación sin AWS, agregar checks/findings al lado sin tocar lo existente y, en el Bloque B, poder cambiar solo `handler.py` si se migra a FastAPI.

### Flujo de una request (`PATCH /controls/{id}`)

```text
API Gateway (payload 2.0, body como string)
  └► handler.lambda_handler: event["routeKey"] = "PATCH /controls/{id}" → ROUTES
       └► controls.update_control
            ├► validation.validate_control_id   → UUID canónico, o 400
            ├► responses.parse_json_body        → dict, o 400 (vacío / JSON inválido / no es objeto)
            ├► validation.validate_fields(partial=True) → solo campos permitidos, o 400
            ├► repository.find_control_by_code  → 409 si el code es de OTRO control
            ├► agrega updated_at (lo pone el servidor)
            └► repository.update_control        → UpdateItem con attribute_exists(id)
                                                   → item (200) o None (404, sin crear nada)
```

### API

| Método y ruta | Operación DynamoDB | Respuestas |
|---|---|---|
| `GET /controls` | `Scan` paginado | 200 `{"items": [...], "count": N}` |
| `GET /controls/{id}` | `GetItem` | 200 `{"item": {...}}` · 400 id inválido · 404 |
| `POST /controls` | `Scan` por `code` + `PutItem` con `attribute_not_exists(id)` | 201 `{"item": {...}}` · 400 · 409 `code` duplicado |
| `PATCH /controls/{id}` | `Scan` por `code` (si viene) + `UpdateItem` con `attribute_exists(id)` y `ReturnValues=ALL_NEW` | 200 · 400 · 404 · 409 |
| `POST /hello` | — | Temporal (Etapa 5). A eliminar |

Errores: siempre `{"error": "<mensaje>"}`. Errores no previstos **no** se atrapan: la Lambda falla, API Gateway devuelve 500 y el traceback queda en CloudWatch (y en la métrica *Errors*).

## 4. Modelo de datos — tabla `controls`

| Atributo | Tipo | Regla |
|---|---|---|
| `id` | String (PK) | UUID v4 generado por el backend. Nunca cambia. Se acepta sin guiones y se normaliza a la forma canónica |
| `code` | String | Obligatorio, ≤ 20, **único** (validado en el código con un Scan; ver D36) |
| `title` | String | Obligatorio, ≤ 200 |
| `service` | String | Obligatorio, ≤ 50 |
| `category` | String | Obligatorio, ≤ 100 |
| `severity` | String | Obligatorio: `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` (mayúsculas exactas) |
| `status` | String | Opcional, default `REVIEW`: `PASS` / `REVIEW` / `FAIL` |
| `description`, `remediation` | String | Opcionales, ≤ 2000 |
| `created_at`, `updated_at` | String | Los pone el servidor, ISO 8601 UTC `YYYY-MM-DDTHH:MM:SSZ` |

Reglas de validación (`FIELD_RULES`, que además es la **allowlist** contra mass assignment): tipo `str` → `strip()` → obligatorio no vacío → largo máximo → valores permitidos. Cualquier otro campo del body se ignora. En `PATCH` (`partial=True`) ningún campo es obligatorio, no se aplican defaults y, si no queda ningún campo válido, 400.

Comportamientos a tener en cuenta (del código):

- Un opcional enviado vacío (`"description": ""`) **se guarda como string vacío** (pregunta abierta en DECISIONS).
- `"severity": "high"` → 400 (no se normalizan mayúsculas; pregunta abierta).
- La unicidad de `code` tiene una *race condition* teórica: dos `POST` simultáneos podrían pasar los dos (aceptado en D36).

**Findings:** todavía no existen. Planificado: tabla aparte, relación 1:N por `control_id` (ver D39–D40).

## 5. IAM: quién le pide permiso a quién

| Flecha | Quién → a quién | Mecanismo |
|---|---|---|
| ① | Navegador → CloudFront | Público (HTTPS) |
| ② | CloudFront → S3 | Bucket policy (resource-based) con Principal `cloudfront.amazonaws.com` y Condition `AWS:SourceArn` = la distribución (OAC) |
| ③ | API Gateway → Lambda | Resource-based policy de la Lambda: un statement por path (cualquier método), Principal `apigateway.amazonaws.com`, `lambda:InvokeFunction`, Condition `SourceArn` = `arn:aws:execute-api:us-east-1:<cuenta>:<api-id>/*/*/<path>` (stage / método / path) |
| ④ | Lambda → DynamoDB | Execution role (identity-based). Inline policy `controls-table-crud` |
| ⑤ | Lambda → CloudWatch Logs | Execution role, policy de logs creada por la consola |

Inline policy `controls-table-crud` [CONVERSACIÓN]:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["dynamodb:Scan", "dynamodb:GetItem", "dynamodb:PutItem",
               "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
    "Resource": "arn:aws:dynamodb:us-east-1:<cuenta>:table/cloud-sec-checklist-controls"
  }]
}
```

Sin `dynamodb:*`, sin `DeleteTable`, sin otras tablas.

## 6. Despliegue actual

```text
VS Code (backend/*.py) ──Compress-Archive──► lambda.zip ──Upload from .zip (consola)──► Lambda
```

La fuente de verdad es el repo. No hay IaC: la infraestructura **no es reproducible** todavía. Eso es lo que resuelve la Etapa 12 (CDK) y lo que hace viable el modelo self-hosted.
