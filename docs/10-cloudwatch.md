# Etapa 10 — CloudWatch: logs estructurados, access logs, alarmas y dashboard

> **Estado:** ✅ completa (2026-10-24 → 2026-10-25). Logs JSON con el usuario de cada cambio, access logs de API Gateway, 3 alarmas con aviso por email, dashboard y un simulacro de falla que verificó la cadena completa (§4.7). Checkpoint en §12.
> **Costo de la etapa:** USD 0. Todo entra en el free tier de CloudWatch y de SNS (§7).

## 1. Objetivo

Hasta la Etapa 9, OpenAegis funcionaba, pero **los problemas solo se veían si alguien los buscaba**:

| Pregunta | Antes de esta etapa |
|---|---|
| ¿La Lambda está fallando ahora? | Solo entrando a mirar los logs |
| ¿Alguien está probando tokens falsos? | No: los `401` del authorizer no llegan a la Lambda y no dejaban rastro |
| ¿Quién borró el control X? | No: el log decía `[DELETE] code=... id=...`, sin el **quién** |
| Si algo se rompe a las 3 AM, ¿te enterás? | No |

Esta etapa agrega:

- **logs estructurados** (JSON) en la Lambda, con el `sub` del usuario en cada cambio;
- **access logs** de API Gateway, para ver lo que el authorizer rechaza;
- consultas con **Logs Insights**;
- **3 alarmas** que avisan por email (SNS);
- un **dashboard**;
- un **simulacro de falla** para comprobar que todo lo anterior funciona de verdad.

Decisión grande: [ADR-008](architecture-decisions/008-observabilidad-cloudwatch.md).

## 2. Conceptos clave

### 2.1 Las cuatro piezas de CloudWatch

```text
           ┌──────────────────────────────────────────────────────────────┐
           │                        CLOUDWATCH                           │
 Lambda ──►│  MÉTRICAS   números en el tiempo     "Errors = 3 a las 14:05"│──► DASHBOARD
 API GW ──►│  (gratis las de los servicios)                              │
 DynamoDB ►│  LOGS       el detalle de cada pedido  "eliminado por <sub>"│──► LOGS INSIGHTS
           │  ALARMAS    una regla sobre una métrica "Errors ≥ 1 en 5 min"│──► SNS ──► email
           └──────────────────────────────────────────────────────────────┘
```

| Pieza | Analogía | Ejemplo en OpenAegis |
|---|---|---|
| **Métrica** | El velocímetro | `Errors`, `Duration`, `4xx`, `Latency` |
| **Log** | La caja negra del avión | El traceback de un error, el `user_sub` de un borrado |
| **Alarma** | La luz del tablero | `Errors ≥ 1 en 5 min → email` |
| **Dashboard** | El tablero completo | 7 paneles en una pantalla |

Las métricas **básicas** de Lambda, API Gateway y DynamoDB existen desde que se creó cada servicio y no tienen costo: no hay que activarlas, solo mirarlas.

### 2.2 Latency vs. IntegrationLatency

```text
         ┌──────────────────────── Latency (todo el recorrido) ─────────────────────────┐
Pedido ─►│ API Gateway ─────► Lambda ──► DynamoDB ──► Lambda ─────► API Gateway         │─► Respuesta
         │ (CORS, authorizer, ┌────── IntegrationLatency (lo que tardó la Lambda) ───┐  │
         │  throttling)       └─────────────────────────────────────────────────────┘  │
         └──────────────────────────────────────────────────────────────────────────────┘
```

Siempre: **Latency ≥ IntegrationLatency ≥ Duration de la Lambda**. La diferencia entre las dos primeras es el trabajo de API Gateway (validar el JWT, CORS, enrutar). Un pedido rechazado por el authorizer **no tiene** `IntegrationLatency`: nunca llegó a la Lambda.

### 2.3 Cada capa ve solo lo que pasa por ella

```text
Pedido ──► API Gateway ──────────────────────────────► Lambda ──────────► DynamoDB
           │ access log (10.3): TODO pedido que          │ log JSON (10.2): solo los
           │ coincide con una ruta, incluso 401/403/429  │ pedidos que la invocan
           │ métricas: Count, 4xx, 5xx, Latency          │ métricas: Invocations, Errors, Duration
```

| Qué pasó | Dónde se ve |
|---|---|
| Token falso o ausente (`401`) | Access log (con `authorizerError`) y métrica `4xx` |
| Ruta inexistente (`/.env`) → `404` | **Solo** la métrica `4xx` (§4.3, limitación de HTTP API) |
| Bug en el código (excepción) | Log de la Lambda (traceback), `Errors` y `5xx` |
| API Gateway no puede invocar la Lambda | Access log (`integrationStatus` ≠ 200) y `5xx`. **No** `Errors`: la Lambda nunca se ejecutó |

### 2.4 Logs estructurados

Con el **log format JSON** de Lambda, cada línea del módulo `logging` de Python sale como un JSON con `timestamp`, `level`, `message`, `logger` y `requestId`. `extra={...}` agrega campos propios. Así, Logs Insights puede filtrar **por campo** (`filter message = "control eliminado"`) en lugar de buscar texto.

Verificado en la documentación de Lambda (2026-10-24):

- `print()` sigue saliendo como **texto plano**, aunque el formato sea JSON.
- Con formato JSON, el nivel se configura **en la Lambda** (no con `setLevel` en el código).
- En formato texto, el nivel por defecto de Python en Lambda es **WARN**: los `logger.info` no aparecen.
- Las claves de `extra` no pueden pisar atributos de `LogRecord` (`message`, `name`, `msg`, `module`...): `KeyError`.

### 2.5 Errores: por qué no hay `try/except` central

Si el handler envolviera todo en `try/except Exception` y devolviera un 500 prolijo, para Lambda la ejecución **terminaría bien**: la métrica `Errors` quedaría en 0 y la alarma no sonaría nunca. El "manejo de errores centralizado" de OpenAegis es:

- errores **esperables** (validación, no encontrado, duplicado) → respuestas `4xx` en `controls.py`;
- errores **inesperados** → la excepción llega al runtime, que la loguea en JSON (`errorType`, `errorMessage`, `stackTrace`), suma a `Errors` y API Gateway responde `500`.

Es la regla del proyecto: atrapar solo lo que se sabe manejar.

## 3. Decisiones técnicas

| # | Decisión | Por qué | Alternativas descartadas |
|---|---|---|---|
| D84 | **Logs estructurados**: log format **JSON nativo** de Lambda (nivel INFO, sistema INFO) + módulo `logging`. Una línea `request` por invocación (`route`, `apigw_request_id`, `user_sub`) y una de auditoría por cambio (`control creado/actualizado/eliminado` con `control_id`, `code`, `user_sub`). Se loguea el **`sub`**, no el email. Sin `try/except` central (§2.5). 2026-10-24 | Sin dependencias; Lambda agrega `requestId` y `timestamp`; el `sub` es estable y el access token no trae el email | AWS Lambda Powertools (dependencia nueva); `print(json.dumps(...))` a mano (sin niveles ni `requestId`); loguear el body completo (datos de más) |
| D85 | **Access logs de API Gateway** en JSON (15 campos, §4.3) en `/aws/vendedlogs/apigateway/cloud-sec-checklist-http-api`, **retención 1 semana**, log class Standard. Limitación aceptada: los pedidos a rutas inexistentes no se loguean (opción a, §4.3). 2026-10-24 | Única forma de ver los `401`/`403`/`429` que la Lambda no ve; la IP es un dato personal: retención corta | Sin access logs; ruta `$default` con authorizer para loguear los escaneos (opción b: una pieza más que puede quedar mal configurada) |
| D86 | **Alarmas**: `openaegis-lambda-errors` (`Errors` ≥ 1), `openaegis-api-5xx` (`5xx` ≥ 1) y `openaegis-api-4xx-pico` (`4xx` ≥ 50), todas Sum en 5 min, 1 de 1, *missing data* = **not breaching**, acción en `ALARM` → topic SNS **`openaegis-alarmas`** (Standard, **sin cifrado**) → email. 2026-10-25 | Cubren bug en el código, falla entre API Gateway y Lambda, y ataque o escaneo; sin tráfico no suenan | Sin notificación (mirar la consola); Slack/Chatbot (más piezas); SNS cifrado con `alias/aws/sns` (CloudWatch no puede publicar) o con KMS propio (USD 1/mes) |
| D87 | **Dashboard `OpenAegis`** creado con `put-dashboard` (JSON, §4.6): alarmas, métricas de API y Lambda, rechazos del authorizer y auditoría (**sin** `user_sub`). 2026-10-25 | Un minuto, repetible, primer contacto con infraestructura como código | Armarlo a mano en la consola |
| D88 | **Las alarmas se verifican con una falla real** (simulacro, §4.7), no solo con `set-alarm-state`. La verificación de una alarma incluye **namespace, métrica y dimensiones**. 2026-10-25 | `set-alarm-state` fuerza el estado sin mirar la métrica: no detecta una alarma "muda" (pasó, §4.7) | Confiar en la prueba manual |

## 4. Configuración realizada

### 4.1 Paso 10.1 — Explorar las métricas existentes (2026-10-24) [CONVERSACIÓN]

Sin cambios en AWS. Se miraron las pestañas *Monitor* de la Lambda y de DynamoDB, y las métricas de API Gateway en **CloudWatch → Metrics → All metrics → ApiGateway → ApiId** (en la consola de HTTP API no aparecían sin elegir el stage).

| Servicio | Valores observados |
|---|---|
| Lambda | 7 invocaciones, 0 errores, 0 throttles; Duration mín. 63 / prom. 152 / máx. 304 ms |
| DynamoDB | Picos de lectura y escritura en los días de uso; 0 throttles. Valores como `0.02` porque el gráfico muestra **unidades por segundo promediadas** |

El máximo de Duration corresponde a la primera ejecución de un contenedor nuevo, que además de la `Init Duration` (aparte) abre la conexión con DynamoDB.

### 4.2 Paso 10.2 — Logs estructurados (2026-10-24, PR #17) [CONFIRMADO-REPO + CONVERSACIÓN]

Código (`backend/`):

| Archivo | Cambio |
|---|---|
| `responses.py` | `user_sub(event)`: `event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]` con `.get(..., {})` en cadena; `None` si no hay authorizer |
| `handler.py` | `logger.info("request", extra={route, apigw_request_id, user_sub})`; `logger.warning` si la ruta no está en `ROUTES`. Sin `lambda_request_id` (Lambda agrega `requestId`) |
| `controls.py` | `_log_change(acción, event, item)` en crear, actualizar y borrar; reemplaza el `print` del DELETE. `getLogger(__name__)` → `"logger": "controls"` |
| `tests/test_responses.py` | 2 tests de `user_sub` (44 en total) |

Configuración: Lambda → *Configuration → Monitoring and operations tools → Logging configuration*: **Log format JSON**, application log level **INFO**, system log level **INFO**, log group sin cambios. Se cambió apenas desplegado el código (en formato texto, los `logger.info` no salen).

Verificación (crear, cambiar el estado y borrar un control desde la SPA):

```bash
aws logs tail /aws/lambda/cloud-sec-checklist-api --since 10m
aws logs tail /aws/lambda/cloud-sec-checklist-api --since 10m --filter-pattern '{ $.message = "control eliminado" }'
```

Resultado: líneas `request` y `control creado/actualizado/eliminado` con `user_sub`; los `platform.start` / `platform.report` también salen en JSON. El filtro por campo devolvió solo el borrado. Además se vio:

- 3 acciones → 6 `request`: después de cada cambio, la SPA vuelve a pedir `GET /controls`.
- Arranque en frío: `initDurationMs 502`, `durationMs 369`, `billedDurationMs 872` (≈ 369 + 502: **el init se factura**). Contenedor caliente: 35 a 51 ms.
- Una línea `botocore.credentials` con `requestId: ""`: boto3 loguea al arrancar, fuera de un pedido.

### 4.3 Paso 10.3 — Access logs de API Gateway (2026-10-24) [CONVERSACIÓN]

1. CloudWatch → *Log groups* → **Create**: `/aws/vendedlogs/apigateway/cloud-sec-checklist-http-api`, retención **1 week**, clase **Standard** (Infrequent Access no permite filtros por campo). El prefijo `/aws/vendedlogs/` es el recomendado para logs que escribe un servicio (evita el límite de tamaño de la resource policy de CloudWatch Logs).
2. API Gateway → *Monitor → Logging* → stage `$default` → *Edit* → Access logging **ON**, destino = el ARN del log group (sin `:*`), formato (una sola línea; cada `$context.*` es un espacio que API Gateway completa por pedido):

```json
{"requestId":"$context.requestId","ip":"$context.identity.sourceIp","userAgent":"$context.identity.userAgent","requestTime":"$context.requestTime","method":"$context.httpMethod","routeKey":"$context.routeKey","path":"$context.path","status":"$context.status","responseLength":"$context.responseLength","responseLatency":"$context.responseLatency","integrationLatency":"$context.integrationLatency","integrationStatus":"$context.integrationStatus","authorizerError":"$context.authorizer.error","errorMessage":"$context.error.message","sub":"$context.authorizer.claims.sub"}
```

En HTTP API no hay rol que crear: la consola configura la entrega. El `requestId` del access log es el mismo valor que el `apigw_request_id` de la Lambda.

Prueba (`curl` sin token, con `Bearer falso` y a `/.env`, más un `GET` desde la SPA):

| Pedido | Resultado en el access log |
|---|---|
| Sin token | `401`, `authorizerError: "missing: token not provided"`, `integrationStatus: "-"` |
| Token falso | `401`, `"invalid_token: token contains an invalid number of segments"` (un JWT tiene 3 partes) |
| Preflight de la SPA | `OPTIONS`, `routeKey: "-"`, `204`: lo responde API Gateway (pasa en cada llamada con `MaxAge 0`) |
| `GET` desde la SPA | `200`, `responseLatency 998`, `integrationLatency 926` (Lambda fría), `sub` presente |
| `/.env` y `/wp-admin` | `curl` recibe `404`, pero **no hay línea en el access log** |

**Limitación encontrada:** HTTP API **no escribe access logs para pedidos que no coinciden con ninguna ruta**. Se descartó la hipótesis de la demora: el primer `/.env` tenía varios minutos y no apareció con `--filter-pattern '{ $.status = "404" }'`. Un escaneo de rutas solo se ve como un pico en la métrica `4xx` (alarma `openaegis-api-4xx-pico`). Opción elegida: aceptarlo (D85).

### 4.4 Paso 10.4 — Logs Insights (2026-10-25) [CONVERSACIÓN]

CloudWatch → *Logs → Logs Insights*, lenguaje Logs Insights QL, rango 1 semana. Se cobra por GB **escaneado** (entra en los 5 GB gratis): elegir siempre un rango chico.

```text
# 1. Auditoría (log de la Lambda)
fields @timestamp, message, code, user_sub
| filter logger = "controls"
| sort @timestamp desc

# 2. Rechazos por IP y motivo (access log)
filter status = "401"
| stats count(*) as intentos by ip, authorizerError
| sort intentos desc

# 3. Rendimiento y arranques en frío (log de la Lambda)
filter type = "platform.report"
| stats count(*) as invocaciones, avg(record.metrics.durationMs) as promedio_ms,
        max(record.metrics.durationMs) as maximo_ms, count(record.metrics.initDurationMs) as arranques_en_frio

# 4. Un pedido de punta a punta (los dos log groups)
fields @timestamp, @log, message, status, route, authorizerError
| filter requestId = "<apigw-request-id>" or apigw_request_id = "<apigw-request-id>"
| sort @timestamp asc
```

Resultados: 3 filas de auditoría (crear, actualizar y borrar `S3-009`); 2 rechazos (`missing` e `invalid_token`); 7 invocaciones, 2 en frío (~29 %), promedio 160 ms, máximo 369 ms.

⚠️ Los dos logs tienen un campo `requestId` con **significados distintos**: en el access log es el ID de API Gateway; en la Lambda, el de Lambda (el de API Gateway está en `apigw_request_id`). Para seguir un error: access log (`500`) → línea `request` de la Lambda por `apigw_request_id` → su `requestId` de Lambda → todas sus líneas, incluido el traceback.

### 4.5 Paso 10.5 — Alarmas y SNS (2026-10-25) [CONVERSACIÓN]

1. SNS → topic **Standard** `openaegis-alarmas`, **sin cifrado**, access policy por defecto (permite que CloudWatch de la cuenta publique).
2. Suscripción **Email** a `<email>`, confirmada desde el mail de AWS (sin confirmar no llega nada).
3. Las 3 alarmas de D86. Configuración definitiva de `openaegis-lambda-errors`, recreada por CLI después de los errores de §4.7:

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws cloudwatch put-metric-alarm --alarm-name openaegis-lambda-errors \
  --namespace AWS/Lambda --metric-name Errors \
  --dimensions Name=FunctionName,Value=cloud-sec-checklist-api \
  --statistic Sum --period 300 --evaluation-periods 1 --datapoints-to-alarm 1 \
  --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions arn:aws:sns:us-east-1:$ACCOUNT:openaegis-alarmas
```

4. Prueba de la cadena alarma → SNS → email (no prueba la métrica, ver D88):

```bash
aws cloudwatch set-alarm-state --alarm-name openaegis-lambda-errors \
  --state-value ALARM --state-reason "Prueba manual del paso 10.5"
```

Verificación (incluye las dimensiones):

```bash
aws cloudwatch describe-alarms --alarm-name-prefix openaegis \
  --query "MetricAlarms[].[AlarmName,MetricName,Dimensions[0].Name,ComparisonOperator,Threshold]" --output table
```

Resultado final: `4xx`/`ApiId`/≥ 50, `5xx`/`ApiId`/≥ 1, `Errors`/`FunctionName`/≥ 1. El email llegó con el asunto `ALARM: "openaegis-lambda-errors" in US East (N. Virginia)`.

### 4.6 Paso 10.6 — Dashboard (2026-10-25) [CONVERSACIÓN]

Creado desde CloudShell; los IDs se obtienen con la CLI, sin escribirlos:

```bash
APIID=$(aws apigatewayv2 get-apis --query "Items[?Name=='cloud-sec-checklist-http-api'].ApiId" --output text)
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
FN=cloud-sec-checklist-api
APILOGS=/aws/vendedlogs/apigateway/cloud-sec-checklist-http-api
ALARM=arn:aws:cloudwatch:us-east-1:$ACCOUNT:alarm
cat > dashboard.json <<EOF
{
  "widgets": [
    {"type":"alarm","x":0,"y":0,"width":24,"height":2,
     "properties":{"title":"Alarmas","alarms":["$ALARM:openaegis-lambda-errors","$ALARM:openaegis-api-5xx","$ALARM:openaegis-api-4xx-pico"]}},
    {"type":"metric","x":0,"y":2,"width":12,"height":6,
     "properties":{"title":"API: pedidos, 4xx y 5xx","region":"us-east-1","stat":"Sum","period":300,"view":"timeSeries",
       "metrics":[["AWS/ApiGateway","Count","ApiId","$APIID"],[".","4xx",".","."],[".","5xx",".","."]]}},
    {"type":"metric","x":12,"y":2,"width":12,"height":6,
     "properties":{"title":"API: Latency vs IntegrationLatency (ms)","region":"us-east-1","stat":"Average","period":300,"view":"timeSeries",
       "metrics":[["AWS/ApiGateway","Latency","ApiId","$APIID"],[".","IntegrationLatency",".","."]]}},
    {"type":"metric","x":0,"y":8,"width":12,"height":6,
     "properties":{"title":"Lambda: invocaciones, errores y throttles","region":"us-east-1","stat":"Sum","period":300,"view":"timeSeries",
       "metrics":[["AWS/Lambda","Invocations","FunctionName","$FN"],[".","Errors",".","."],[".","Throttles",".","."]]}},
    {"type":"metric","x":12,"y":8,"width":12,"height":6,
     "properties":{"title":"Lambda: Duration (ms)","region":"us-east-1","period":300,"view":"timeSeries",
       "metrics":[["AWS/Lambda","Duration","FunctionName","$FN",{"stat":"Average","label":"Promedio"}],["...",{"stat":"Maximum","label":"Máximo"}]]}},
    {"type":"log","x":0,"y":14,"width":12,"height":6,
     "properties":{"title":"Rechazos del authorizer por motivo","region":"us-east-1","view":"table",
       "query":"SOURCE '$APILOGS' | filter status = \"401\" or status = \"403\" | stats count(*) as intentos by status, authorizerError | sort intentos desc"}},
    {"type":"log","x":12,"y":14,"width":12,"height":6,
     "properties":{"title":"Auditoría: últimos cambios","region":"us-east-1","view":"table",
       "query":"SOURCE '/aws/lambda/$FN' | fields @timestamp, message, code | filter logger = \"controls\" | sort @timestamp desc | limit 20"}}
  ]
}
EOF
aws cloudwatch put-dashboard --dashboard-name OpenAegis --dashboard-body file://dashboard.json
```

`[".","4xx",".","."]` repite los campos de la fila anterior; `["..."]` la repite entera. Los paneles de logs corren una consulta de Logs Insights cada vez que se abre o refresca el dashboard. El panel de auditoría no muestra `user_sub`, para poder compartir capturas.

### 4.7 Paso 10.7 — Simulacro de falla (2026-10-25) [CONVERSACIÓN]

**Falla provocada:** `TABLE_NAME = cloud-sec-checklist-controls-ROTA` en la Lambda (sin deploy de código), 2 o 3 recargas de la SPA y vuelta al valor correcto.

**Primer simulacro:**

| Paso | Resultado |
|---|---|
| SPA | "No se pudieron cargar los controles / Internal Server Error" |
| Email | `openaegis-api-5xx` a las 20:13:01; primer error a las 20:12:17 (< 1 min) |
| Access log | `status 500`, **`integrationStatus 200`**: API Gateway invocó bien a la Lambda; falló el código |
| Log de la Lambda | `errorType: ClientError`, `AccessDeniedException ... dynamodb:Scan on resource ...table/cloud-sec-checklist-controls-ROTA because no identity-based policy allows the dynamodb:Scan action` |
| Traceback | `handler.py:36` → `controls.py:27` (`list_controls`) → `repository.py:18` (`table.scan`) → botocore |
| `openaegis-lambda-errors` | **No sonó** |

Debugging de la alarma que no sonó:

| Paso | |
|---|---|
| Esperado | Que sonaran las dos alarmas |
| Evidencia 1 | `describe-alarm-history`: el único paso a `ALARM` era el de `set-alarm-state` (19:19), ninguno a las 20:12 |
| Evidencia 2 | `describe-alarms` con dimensiones: `FunctionName = Errors` |
| Causa | Al corregir el nombre de la métrica (que había quedado igual al de la alarma), `Errors` quedó como **valor de la dimensión**. La alarma miraba una función inexistente: sin datos + *not breaching* = `OK` para siempre |
| Por qué no se vio antes | `set-alarm-state` no mira la métrica, y la verificación del 10.5 no mostraba las dimensiones |
| Arreglo | Recrear la alarma con `put-metric-alarm` (§4.5) |

**Segundo simulacro:** sonaron **las dos** alarmas: `openaegis-api-5xx` (20:31:01, valor `1.0`) y `openaegis-lambda-errors` (20:31:33, valor `4.0`).

Lo que enseñó:

- **`AccessDenied` y no "tabla no encontrada":** la inline policy del rol (D56–D58) solo permite la tabla real, e IAM evalúa antes de que DynamoDB busque la tabla. Es least privilege funcionando: la Lambda no puede tantear otros recursos, y AWS no revela si un recurso existe a quien no tiene permiso. Antes de tocar IAM ante un `AccessDenied`, **leer el ARN del mensaje**.
- **`integrationStatus` vs. `status`:** distingue "falló mi código" (`200` / `500`) de "API Gateway no pudo invocar" (`integrationStatus` ≠ 200).
- **4 errores con 2 recargas:** la SPA reintenta una vez los `5xx` (`query-client.ts`).
- **El valor del email puede ser parcial:** la alarma evalúa con los datos que llegaron hasta ese momento (`2.0` con 5 pedidos `500` en el access log; `1.0` de `5xx` con 4 de `Errors`). El total se ve después en el dashboard.
- El runtime escribe el nivel de una excepción no manejada como **`log_level`**, no `level`: para buscar errores, `ispresent(errorType)`.

## 5. Plan de la etapa

| Paso | Qué | Toca AWS | Estado |
|---|---|---|---|
| 10.1 | Explorar las métricas que ya existen | No | ✅ 2026-10-24 (§4.1) |
| 10.2 | Logs JSON + `user_sub` | Sí (configuración + deploy) | ✅ 2026-10-24, PR #17 (§4.2) |
| 10.3 | Access logs de API Gateway | Sí (log group) | ✅ 2026-10-24 (§4.3) |
| 10.4 | Logs Insights | No | ✅ 2026-10-25 (§4.4) |
| 10.5 | Alarmas + SNS por email | Sí | ✅ 2026-10-25 (§4.5) |
| 10.6 | Dashboard | Sí | ✅ 2026-10-25 (§4.6) |
| 10.7 | Simulacro de falla | Sí (variable de entorno, revertida) | ✅ 2026-10-25 (§4.7) |
| 10.8 | Documentación, diagramas, checkpoint y nota de Obsidian | No | ✅ 2026-10-25 |

## 6. Verificación (resumen de la etapa)

| Qué | Cómo | Resultado |
|---|---|---|
| Logs JSON con `user_sub` | `aws logs tail` + filtro por campo | ✅ (§4.2) |
| Access logs con el motivo de cada `401` | `curl` sin token y con token falso | ✅ (§4.3) |
| Logs Insights | 4 consultas | ✅ (§4.4) |
| Cadena alarma → SNS → email | `set-alarm-state` | ✅ (§4.5) |
| Configuración de las alarmas | `describe-alarms` con dimensiones | ✅ después de 3 correcciones (§4.7) |
| Alarmas ante una falla real | Simulacro con `TABLE_NAME` incorrecto | ✅ las dos, en el segundo intento (§4.7) |
| Código | Tests (44) + CI `checks` en el PR #17 | ✅ |

## 7. Costos

USD 0 (verificado en la página de precios de CloudWatch y de SNS el 2026-10-24):

| Qué | Free tier | Uso | Después del free tier |
|---|---|---|---|
| Métricas básicas de Lambda, API Gateway y DynamoDB | Siempre gratis | — | — |
| Alarmas de resolución estándar | 10 | 3 | USD 0,10 por alarma por mes |
| Dashboards | 3 | 1 | — |
| Logs: ingesta + almacenamiento + escaneo de Logs Insights | 5 GB en total | KB | Ingesta USD 0,50/GB; almacenamiento USD 0,03/GB-mes |
| Emails de SNS | 1.000 por mes | Un puñado | USD 2 cada 100.000 |
| Métricas *detalladas* de API Gateway | — | **No activadas** | Se cobran como métricas custom (USD 0,30 cada una) |

Cada línea del access log pesa unos 600 bytes: un millón de pedidos son unos 0,6 GB. Las retenciones de 1 semana acotan el almacenamiento.

## 8. Relación con Cloud Security

| Tema | Qué se aplicó |
|---|---|
| Auditoría | Cada cambio queda con quién (`user_sub`), qué (`control_id`, `code`) y cuándo |
| Detección | Los rechazos del authorizer quedan con IP, `userAgent` y motivo; alarma ante picos de `4xx` |
| Respuesta | Email en menos de un minuto ante errores; dashboard y consultas para investigar |
| Minimización de datos | `sub` en vez de email; nunca el body ni el event completo; IP con retención de 1 semana; dashboard sin `user_sub` |
| Least privilege | Visto desde un error: `AccessDenied` sobre una tabla que no es la del rol (§4.7) |
| Alarmas confiables | Una alarma sin probar con una falla real puede estar muda (D88) |
| Errores visibles | Sin `try/except` amplio: los errores inesperados llegan a la métrica `Errors` |
| Controles detectivos | Logs, alarmas y dashboard **detectan**; no impiden nada (los preventivos son el authorizer, IAM y el throttling) |

## 9. Cómo revertir esta etapa

1. **Dashboard:** `aws cloudwatch delete-dashboards --dashboard-names OpenAegis`.
2. **Alarmas:** `aws cloudwatch delete-alarms --alarm-names openaegis-lambda-errors openaegis-api-5xx openaegis-api-4xx-pico`.
3. **SNS:** borrar la suscripción y el topic `openaegis-alarmas`.
4. **Access logs:** API Gateway → *Logging* → Access logging **OFF**, y borrar el log group `/aws/vendedlogs/apigateway/cloud-sec-checklist-http-api`.
5. **Logs JSON:** Lambda → *Logging configuration* → **Text**, y revertir el PR #17 si se quiere volver al `print` (con formato texto, los `logger.info` no se ven).

## 10. Pendientes y mejoras posibles

- `MaxAge` del CORS en 0: el access log muestra un `OPTIONS` antes de cada llamada [PROPUESTA, de la Etapa 9].
- Ver los escaneos de rutas inexistentes con una ruta `$default` + JWT authorizer (opción b de D85) [PROPUESTA].
- Alarma de `Duration` cerca del timeout (3 s) [PROPUESTA].
- Silenciar la línea `botocore.credentials` de cada arranque en frío (`logging.getLogger("botocore").setLevel(logging.WARNING)`) [PROPUESTA].
- Etapa 12 (CDK): alarmas, topic, log group, access logs y dashboard como código.
- `check_identifiers.py`: detectar IDs de Cognito [PENDIENTE, de la Etapa 9].

## 11. Cosas que NO se deben hacer

- Envolver el handler en `try/except Exception`: la métrica `Errors` y su alarma dejan de funcionar.
- Usar `print` para logs nuevos: sale como texto plano aunque el formato sea JSON.
- Loguear el body, el event completo, tokens o emails.
- Dar por buena una alarma solo con `set-alarm-state`.
- Verificar una alarma sin mirar su **métrica y sus dimensiones**.
- *Missing data* = *breaching* en una app con poco tráfico: suena todo el fin de semana y se aprende a ignorarla.
- Cifrar el topic de SNS con `alias/aws/sns`: CloudWatch no puede publicar y las alarmas fallan en silencio.
- Activar las métricas detalladas de API Gateway sin calcular el costo.
- Ante un `AccessDenied`, agregar permisos amplios (`dynamodb:*` sobre `*`) sin leer primero el ARN del mensaje.
- Pegar salidas con el ID de la cuenta, el ID de la API, IPs o el `sub` sin taparlos.

## 12. Checkpoint

Checkpoint (2026-10-25):

| Eje | Qué quedó |
|---|---|
| **CONCEPTO** | Métricas (números en el tiempo), logs (el detalle) y alarmas (reglas que avisan). Las métricas básicas de los servicios ya existían |
| **ARQUITECTURA** | Logs JSON en la Lambda, access logs en API Gateway, 3 alarmas → SNS → email, dashboard. Cada capa ve solo lo que pasa por ella (§2.3) |
| **SEGURIDAD** | Ver §8 |
| **COSTOS** | USD 0 (§7) |
| **PRÁCTICA** | Logs Insights, seguir un pedido de punta a punta, alarmas por consola y por CLI, dashboard como JSON, simulacro de falla |
| **VERIFICACIÓN** | La alarma muda: `set-alarm-state` pasaba; solo la falla real la descubrió (§4.7) |

Las preguntas finales las respondió el asistente, a pedido del usuario:

| Pregunta | Respuesta |
|---|---|
| Un compañero propone envolver el handler en `try/except Exception` y devolver un 500 prolijo. ¿Qué alarma deja de funcionar y cuál sigue sonando? | Deja de funcionar **`openaegis-lambda-errors`**: para Lambda la ejecución termina bien, así que `Errors` queda en 0. Sigue sonando **`openaegis-api-5xx`**, porque el navegador igual recibe un 500. Pero se pierde el traceback automático y la distinción entre "falló mi código" y "falló la integración" |
| 600 `401` en 10 minutos contra `/controls`, con `invalid_token`. ¿Dónde ves la IP? ¿Por qué no aparecen en el log de la Lambda? | En el **access log** de API Gateway (`ip`, `userAgent`, `authorizerError`), con la consulta 2 de §4.4. No están en la Lambda porque el **JWT authorizer** los rechaza antes de invocarla. Si fueran 50 o más en 5 minutos, además suena `openaegis-api-4xx-pico` |
| `AccessDeniedException` en `dynamodb:Scan` sobre una tabla que la Lambda debería poder leer. ¿Qué mirás primero? | El **ARN del recurso** en el mensaje: nombre de la tabla, región y cuenta. Si no es la tabla real (como `-ROTA` en el simulacro), la causa es la configuración (`TABLE_NAME`), no IAM. Después, el rol que aparece en el mensaje |
| ¿Por qué no alcanza con `set-alarm-state`? | Porque fuerza el estado **sin mirar la métrica**: prueba la cadena alarma → SNS → email, pero no que la alarma mire la métrica y las dimensiones correctas. Con `FunctionName = Errors`, la prueba manual pasó y la alarma nunca habría sonado con un error real |

Respuestas del usuario durante la etapa: [LEARNING_LOG.md §3](LEARNING_LOG.md#3-predicciones-del-patch).
