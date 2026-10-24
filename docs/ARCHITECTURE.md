# Arquitectura implementada

> Estado al 2026-10-24. Describe **solo lo que existe**. Lo planificado está en [ROADMAP.md](ROADMAP.md).
> Marcas: **[CONFIRMADO-REPO]** = leído en el código · **[CONVERSACIÓN]** = configurado a mano en la consola según el historial, sin verificación independiente · **[INCIERTO]** = verificar.

## 1. Vista general

```text
                                   Navegador (SPA)
            ┌──────────────────────────┼───────────────────────────────┐
            │ HTTPS                    │ login: Authorization Code     │ HTTPS + CORS
            │                          │ + PKCE, contraseña + MFA      │ Authorization: Bearer <access token>
            ▼                          ▼                               ▼
   ┌─────────────────┐       ┌───────────────────┐       ┌───────────────────────────┐
   │   CloudFront    │       │ Cognito User Pool │ JWKS  │  API Gateway (HTTP API)   │
   │ OAC · HTTP→HTTPS│       │ Essentials · MFA  │◄······│  stage $default           │
   └────────┬────────┘       │ app client público│ claves│  throttling 10/20 · CORS  │
            │ s3:GetObject   └───────────────────┘públicas│  JWT authorizer (scope    │
            │ (firmado, OAC)                              │  openid) → 401/403        │
            ▼                                             └────────────┬──────────────┘
   ┌─────────────────┐                                                 │ lambda:InvokeFunction
   │ S3 (privado)    │                                                 │ (solo si el token es válido)
   │ SPA (build)     │                                                 ▼
   │ index + assets/ │       ┌────────────────────┐      ┌───────────────────────────┐
   └─────────────────┘       │ CloudWatch Logs    │◄─────│ Lambda cloud-sec-         │
                             │ retención 1 semana │ logs │ checklist-api (Py 3.14)   │
                             └────────────────────┘      └────────────┬──────────────┘
                                                                      │ execution role:
                                                                      │ Scan/Get/Put/Update/DeleteItem
                                                                      ▼
                                                         ┌───────────────────────────┐
                                                         │ DynamoDB                  │
                                                         │ cloud-sec-checklist-      │
                                                         │ controls (on-demand)      │
                                                         └───────────────────────────┘
```

Todo en **`us-east-1`**, en una sola cuenta. Desde el 2026-10-21 (paso 8.8, D79) CloudFront sirve el **build de la SPA**, que consume la API con `fetch` a la URL de API Gateway inyectada al compilar (`VITE_API_URL`). En **desarrollo**, la SPA usa `/api` (proxy de Vite + TanStack Query).

Desde la Etapa 9 (D80–D83, [ADR-007](architecture-decisions/007-autenticacion-cognito.md)), `/app` exige login en **Cognito** (contraseña + MFA), la SPA manda el **access token** en cada llamada y el **JWT authorizer** de API Gateway rechaza los pedidos sin un token válido (`401`) o sin el scope `openid` (`403`) **antes** de invocar la Lambda. Detalle: [09-cognito.md](09-cognito.md).

**Diagramas del repo:**

- [architecture/architecture.drawio.png](../architecture/architecture.drawio.png) — vista general, actualizada al cierre de la Etapa 8 (2026-10-21). Todavía no muestra Cognito como implementado ni el JWT authorizer [PENDIENTE]. PNG editable con la extensión draw.io de VS Code (XML embebido; fondo blanco para el modo oscuro de GitHub).
- [architecture/permissions-flow.drawio.png](../architecture/permissions-flow.drawio.png) — "quién le pide permiso a quién", flechas ① a ⑤.

## 2. Recursos de AWS [CONVERSACIÓN]

Todos creados **a mano en la consola**, con tag `Project = cloud-security-checklist`. CDK los va a reemplazar en la Etapa 12.

| Recurso | Configuración relevante | Doc |
|---|---|---|
| S3 `cloud-sec-checklist-frontend-<sufijo>` | Privado, BPA 4/4, ACLs desactivadas (*bucket owner enforced*), SSE-S3, sin versioning, sin Object Lock | [02-s3.md](02-s3.md) |
| CloudFront `cloud-sec-checklist-frontend` | Pay-as-you-go, OAC, bucket policy con `AWS:SourceArn` = la distribución, redirect HTTP→HTTPS, default root object `index.html`, error pages 403/404 → `/index.html` con 200 (D67, paso 8.7), dominio `<distribucion>.cloudfront.net`, sin WAF, sin logging | [03-cloudfront.md](03-cloudfront.md) |
| Lambda `cloud-sec-checklist-api` | Python 3.14, arm64, 128 MB, timeout 3 s, sin Function URL, sin VPC, handler `handler.lambda_handler`, env `TABLE_NAME=cloud-sec-checklist-controls` | [04-lambda.md](04-lambda.md) |
| Execution role `cloud-sec-checklist-api-role-<sufijo>` | Trust: `lambda.amazonaws.com`. Policy de logs creada por la consola + inline **`controls-table-crud`** (ver §5) | [04-lambda.md](04-lambda.md) |
| Log group `/aws/lambda/cloud-sec-checklist-api` | Retención 1 semana | [04-lambda.md](04-lambda.md) |
| HTTP API `cloud-sec-checklist-http-api` | Stage `$default` con auto-deploy · throttling rate 10 / burst 20 · CORS Allow-Origin = solo `https://<distribucion>.cloudfront.net` · Allow-Methods `GET`, `POST`, `PATCH`, `DELETE` · AllowCredentials `false` · MaxAge `0` (verificado con `get-api` el 2026-10-13). Allow-Headers `content-type`, `authorization` desde la Etapa 9 (verificado el 2026-10-22) · **JWT authorizer `cognito-openaegis`** (issuer = el User Pool, audience = `<client-id>`) en las 5 rutas con scope `openid` (verificado con `get-authorizers` y `get-routes` el 2026-10-24) | [05-api-gateway.md](05-api-gateway.md) |
| Cognito User Pool (`<user-pool-id>`) | Plan *Essentials* · MFA obligatorio (TOTP) · solo el admin crea usuarios · deletion protection · dominio del login `<dominio-cognito>` · app client `openaegis-spa` público (sin secret), Authorization Code + PKCE, scopes `openid email`, callbacks `/app/callback` y logout `/app` de localhost y CloudFront, access/ID token 60 min, refresh token 12 h, revocación activa (verificado el 2026-10-22) | [09-cognito.md](09-cognito.md) |
| IAM Access Analyzer `openaegis-external-access` | Tipo `ACCOUNT` (*external access*, gratis), zona de confianza = la cuenta, `us-east-1`. Creado el 2026-10-15; 0 findings activos al crearlo. Detectivo: no modifica nada | [07-iam.md](07-iam.md) |
| DynamoDB `cloud-sec-checklist-controls` | PK `id` (String), sin sort key, on-demand, Standard, cifrado *Owned by Amazon DynamoDB*, **deletion protection desactivado** (a propósito, para la migración a CDK), sin PITR, sin GSI | [06-dynamodb.md](06-dynamodb.md) |

### Rutas configuradas en API Gateway

| Ruta | ¿Existe en API Gateway? |
|---|---|
| `GET /controls` | Sí (respondió 200) |
| `GET /controls/{id}` | Sí (respondió 200/400/404) |
| `POST /controls` | Sí (respondió 201/400/409) |
| `PATCH /controls/{id}` | Sí: respondió **200** a un `curl` el 2026-10-10, así que la ruta existe y está integrada |
| `DELETE /controls/{id}` | Sí: respondió 200/404/400 el 2026-10-13 |

Desde el 2026-10-24, **las 5 rutas** exigen el JWT authorizer con scope `openid`: sin token o con uno inválido → `401`; con un token válido sin el scope (por ejemplo, un ID token) → `403`. En ambos casos la Lambda no se ejecuta.

**Resource-based policy de la Lambda** (verificada con `aws lambda get-policy` el 2026-10-15): **5 statements, uno por ruta, con el método explícito** (D57): `apigw-get-controls`, `apigw-post-controls`, `apigw-get-controls-id`, `apigw-patch-controls-id`, `apigw-delete-controls-id`, con `SourceArn` `.../<api-id>/*/<MÉTODO>/<path>`. Una ruta nueva con otro método (por ejemplo `PUT /controls/{id}`) **no** podría invocar la Lambda sin su propio statement. Antes de la Etapa 7 había 2 statements por path con método comodín (`.../*/*/<path>`), creados por la consola.

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
| [controls.py](../backend/controls.py) | `list_controls`, `get_control`, `create_control`, `update_control`, `delete_control`. Decide los status codes | Reglas de negocio (400/404/409/201) | boto3 |
| [validation.py](../backend/validation.py) | `SEVERITY_VALUES`, `STATUS_VALUES`, `FIELD_RULES`, `validate_fields(body, partial=False)`, `validate_control_id`. Devuelve **mensajes**, no respuestas HTTP | Qué es un control válido | AWS, HTTP |
| [repository.py](../backend/repository.py) | `table` (creada en el cold start), `_scan_all` paginado, `list_controls`, `get_control`, `find_control_by_code`, `create_control`, `update_control`, `delete_control`. Traduce `ConditionalCheckFailedException` a `None` | DynamoDB | HTTP |
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

Contrato completo: [backend/openapi.yaml](../backend/openapi.yaml) (OpenAPI 3.1, D69). Con `npm run dev` en `frontend/`, se puede ver y probar en `http://localhost:5173/swagger.html`.


| Método y ruta | Operación DynamoDB | Respuestas |
|---|---|---|
| `GET /controls` | `Scan` paginado | 200 `{"items": [...], "count": N}` |
| `GET /controls/{id}` | `GetItem` | 200 `{"item": {...}}` · 400 id inválido · 404 |
| `POST /controls` | `Scan` por `code` + `PutItem` con `attribute_not_exists(id)` | 201 `{"item": {...}}` · 400 · 409 `code` duplicado |
| `PATCH /controls/{id}` | `Scan` por `code` (si viene) + `UpdateItem` con `attribute_exists(id)` y `ReturnValues=ALL_NEW` | 200 · 400 · 404 · 409 |
| `DELETE /controls/{id}` | `DeleteItem` con `attribute_exists(id)` y `ReturnValues=ALL_OLD` | 200 `{"item": {...}}` (el borrado) · 400 · 404 |

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
| ③ | API Gateway → Lambda | Resource-based policy de la Lambda: un statement por ruta (método + path), Principal `apigateway.amazonaws.com`, `lambda:InvokeFunction`, Condition `SourceArn` = `arn:aws:execute-api:us-east-1:<cuenta>:<api-id>/*/<MÉTODO>/<path>` (stage / método / path) |
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
