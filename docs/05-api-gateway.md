# Etapa 5 — Amazon API Gateway (HTTP API)

> **Estado:** ✅ completada
> **Costo de la etapa:** fracciones de centavo (algunos cientos de requests de prueba)
>
> **Cambios posteriores (Etapa 6):** se agregaron las 5 rutas de `/controls` (un statement por **path** en la resource-based policy; desde la Etapa 7, uno por **ruta** con el método: D57); CORS pasó a `GET`, `POST`, `PATCH`, `DELETE`; el handler pasó a un router por `routeKey` repartido en 5 módulos. `POST /hello` se **eliminó** el 2026-10-13 (código, ruta y statement); los ejemplos de este doc la usan porque era la ruta de esta etapa. Estado actual: [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Objetivo

Exponer la Lambda a internet mediante una **URL HTTPS pública**, de forma controlada:

- recibir requests HTTP normales (sin credenciales de AWS) y enviarlas a la Lambda;
- adaptar el handler al formato de evento de API Gateway;
- limitar el abuso y el costo con **throttling**;
- permitir que solo el frontend propio use la API desde el navegador (**CORS**);
- entender la resource-based policy que autoriza a API Gateway a invocar la Lambda.

## 2. Conceptos clave

### 2.1 ¿Qué es API Gateway?

La **puerta de entrada HTTP** del backend. Cumple el rol de un reverse proxy + router + rate limiter, como servicio administrado.

Sin API Gateway, la Lambda solo puede ser invocada por identidades de AWS con `lambda:InvokeFunction` y requests firmadas. Un navegador no tiene credenciales de AWS.

### 2.2 Tipos de API

| | **HTTP API** ✅ | REST API |
|---|---|---|
| Precio (`us-east-1`) | USD 1,00 por millón de requests | USD 3,50 por millón |
| Autorizador JWT (Cognito) | Nativo y simple | *Cognito authorizer*, más configuración |
| CORS | Configuración integrada | Por método |
| AWS WAF | ❌ | ✅ |
| API keys / usage plans | ❌ | ✅ |
| Validación, caché, transformaciones | ❌ | ✅ |
| Complejidad | Baja | Alta |

### 2.3 Vocabulario

| Concepto | Qué es | En el proyecto |
|---|---|---|
| **Route** | Método HTTP + path | `POST /hello` (ruta de prueba) |
| **Integration** | Destino de la request | Lambda proxy → `cloud-sec-checklist-api` |
| **Stage** | Versión desplegada de la API | `$default` con auto-deploy |
| **Invoke URL** | URL pública | `https://<api-id>.execute-api.us-east-1.amazonaws.com` |
| **Payload format** | Forma del `event` que recibe la Lambda | Versión 2.0 |

### 2.4 El event de API Gateway (payload 2.0)

Con *Lambda proxy*, la Lambda recibe la request HTTP completa. Simplificado:

```text
{
  "routeKey": "POST /hello",
  "rawPath": "/hello",
  "headers": { "content-type": "application/json", "user-agent": "...", ... },
  "requestContext": {
    "accountId": "...", "apiId": "...",
    "http": { "method": "POST", "path": "/hello", "sourceIp": "...", ... },
    "requestId": "...", "stage": "$default", ...
  },
  "body": "{\"name\": \"Facundo\"}",
  "isBase64Encoded": false
}
```

> **`body` es un string**, no un diccionario. Hay que convertirlo con `json.loads` antes de leer sus campos. `event["body"]["name"]` falla con `TypeError`.

### 2.5 El viaje de una request

```text
Navegador / curl
   │  POST https://<api-id>.execute-api.us-east-1.amazonaws.com/hello
   ▼
API Gateway
   │  1. ¿Existe la route?                  → no: 404 (sin invocar la Lambda)
   │  2. ¿Se superó el throttling?          → sí: 429 (sin invocar la Lambda)
   │  3. ¿Autorizador? (Etapa 9: Cognito)   → token inválido: 401
   │  4. Arma el event e invoca la Lambda
   ▼
Lambda
   │  Resource-based policy: ¿API Gateway, desde ESTA API y ESTA ruta, puede invocarme?
   │  lambda_handler(event, context) → {statusCode, headers, body}
   ▼
API Gateway convierte la respuesta en HTTP → cliente
```

### 2.6 CORS

**Origin** = protocolo + dominio + puerto. El frontend (`https://<distribucion>.cloudfront.net`) y la API (`https://<api-id>.execute-api...`) son orígenes distintos. Por la *same-origin policy*, **el navegador** bloquea que el JavaScript de un origen lea respuestas de otro, salvo que la API lo autorice:

```text
Access-Control-Allow-Origin: https://<distribucion>.cloudfront.net
```

Para requests como un `POST` con JSON, el navegador envía antes un **preflight** `OPTIONS`.

| Hecho | Consecuencia |
|---|---|
| CORS lo aplica **el navegador** | `curl`, Postman y scripts lo ignoran: **no es autenticación** |
| `Access-Control-Allow-Origin: *` | Cualquier sitio podría usar la API desde el navegador de sus visitantes |

> **CORS no protege la API de atacantes.** Protege a los usuarios de que un sitio malicioso use su navegador contra la API. La API se protege con autenticación, throttling y validación de entrada.

### 2.7 Throttling y *denial of wallet*

El throttling funciona como un **balde de fichas** (*token bucket*):

| Límite | Qué controla | Analogía |
|---|---|---|
| **Burst** | Requests que pueden entrar de golpe | Tamaño del balde |
| **Rate** | Fichas que se reponen por segundo | Caudal de la canilla |

Sin fichas → **429 Too Many Requests**, **sin invocar la Lambda**.

**Denial of wallet:** en serverless, el ataque típico no busca tirar el servicio sino **generar costo**. Cada request implica API Gateway + Lambda (+ DynamoDB en el futuro). Hasta incorporar Cognito, la API es pública: el throttling pone un techo.

### 2.8 La URL de la API no es un secreto

Un frontend que llama a la API expone su URL en el JavaScript (visible con F12). La seguridad **no puede depender de que nadie conozca la URL** (*security through obscurity*). Depende de autenticación, throttling y validación.

## 3. Decisiones técnicas

| # | Decisión | Alternativas evaluadas | Motivo |
|---|---|---|---|
| D26 | **HTTP API** | REST API | Autorizador JWT nativo para Cognito, CORS integrado y menor costo. No requiere WAF (D15), API keys ni caché. Si se necesitara WAF, podría ubicarse en CloudFront. No condiciona la V2 |
| D27 | Throttling **rate 10 / burst 20** | Sin throttling; límites por defecto de la cuenta | Techo de costo mientras la API no tiene autenticación |
| D28 | CORS restringido al dominio de CloudFront | `Access-Control-Allow-Origin: *` | Solo el frontend propio puede usar la API desde un navegador |
| D29 | CORS gestionado por **API Gateway** | Headers CORS desde la Lambda | API Gateway responde los preflight `OPTIONS` sin invocar la Lambda |
| D30 | Frontend y API en **orígenes distintos** (con CORS) | Servir la API desde CloudFront bajo `/api/*` (mismo origen) | Más simple y más común. La alternativa queda como mejora posible |
| D31 | Logs con **método, path y request IDs**, sin el event completo | `print(event)` | El event incluye headers, IP del cliente e ID de cuenta; con Cognito incluiría tokens |

> **Contexto para entrevistas:** expuse la Lambda con una HTTP API de API Gateway. Elegí HTTP API sobre REST API por el autorizador JWT nativo, el CORS integrado y el menor costo. Configuré throttling como protección contra *denial of wallet* mientras la API no tiene autenticación, restringí CORS al dominio de CloudFront y la Lambda solo puede ser invocada por esta API, por la resource-based policy con condición sobre el ARN de la ruta.

## 4. Configuración realizada

### 4.1 API

| Opción | Valor |
|---|---|
| Tipo | HTTP API |
| Nombre | `cloud-sec-checklist-http-api` |
| Integración | Lambda proxy → `cloud-sec-checklist-api` (payload 2.0) |
| Rutas | En esta etapa: `POST /hello` (eliminada en la Etapa 6). Hoy: `GET /controls`, `GET /controls/{id}`, `POST /controls`, `PATCH /controls/{id}`, `DELETE /controls/{id}` |
| Stage | `$default`, auto-deploy |
| Throttling | Rate 10 req/s · Burst 20 |
| CORS — Allow-Origin | `https://<distribucion>.cloudfront.net` |
| CORS — Allow-Methods | En esta etapa: `POST`. Desde la Etapa 6: `GET`, `POST`, `PATCH`, `DELETE` (verificado con `aws apigatewayv2 get-api --api-id <api-id> --query CorsConfiguration`) |
| CORS — Allow-Headers | `content-type`. Desde la Etapa 9: `content-type`, `authorization` ([09 §4.2](09-cognito.md)) |
| Tags | `Project = cloud-security-checklist` |

### 4.2 Resource-based policy de la Lambda

Creada automáticamente al configurar la integración:

```json
{
  "Version": "2012-10-17",
  "Id": "default",
  "Statement": [
    {
      "Sid": "<sid>",
      "Effect": "Allow",
      "Principal": { "Service": "apigateway.amazonaws.com" },
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-1:<cuenta>:function:cloud-sec-checklist-api",
      "Condition": {
        "ArnLike": {
          "AWS:SourceArn": "arn:aws:execute-api:us-east-1:<cuenta>:<api-id>/*/*/hello"
        }
      }
    }
  ]
}
```

| Campo | Significado |
|---|---|
| `Principal` | El servicio API Gateway |
| `Action` | Solo invocar la función |
| `Resource` | Esta Lambda |
| `Condition` | Solo desde **esta API** y **esta ruta** |

```text
arn:aws:execute-api:us-east-1:<cuenta>:<api-id> / * / * / hello
                                                 │   │    └── path
                                                 │   └── método
                                                 └── stage
```

Sin la `Condition`, cualquier API Gateway de cualquier cuenta podría invocar la función. Cada **path** nuevo agrega su propio statement: **least privilege a nivel de path**. El método queda con comodín (`*`): en la Etapa 6 se comprobó que `PATCH` y `DELETE` sobre `/controls/{id}` reutilizan el statement creado para `GET /controls/{id}`.

### 4.3 Handler

Código **al cerrar esta etapa** (commit `f1b38d4`). Desde la Etapa 6, `lambda_handler` busca la función en un diccionario `ROUTES` según `event["routeKey"]`, loguea `routeKey` + los dos request IDs, y la validación del body vive en `responses.parse_json_body`: ver [ARCHITECTURE.md](ARCHITECTURE.md#3-backend-confirmado-repo).

```python
import json

def build_response(status_code, body_dict):
    """Función auxiliar para eliminar la duplicación de código en las respuestas."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_dict)
    }

def lambda_handler(event, context):
    raw_body = event.get("body")

    # Extraemos metadatos de la solicitud HTTP
    request_context = event.get("requestContext", {})
    http_data = request_context.get("http", {})
    http_method = http_data.get("method", "UNKNOWN")
    path = http_data.get("path", "UNKNOWN")

    # IDs de rastreo: Correlacionamos el ID de API Gateway con el de Lambda
    apigw_request_id = request_context.get("requestId", "UNKNOWN")
    lambda_request_id = context.aws_request_id

    print(f"[{http_method}] {path} | APIGW_ID: {apigw_request_id} | LAMBDA_ID: {lambda_request_id}")

    if not raw_body:
        return build_response(400, {"error": "El cuerpo de la solicitud está vacío."})

    try:
        body_data = json.loads(raw_body)
    except json.JSONDecodeError:
        return build_response(400, {"error": "JSON inválido."})

    # json.loads también acepta listas, strings y números; esperamos un objeto JSON
    if not isinstance(body_data, dict):
        return build_response(400, {"error": "El body debe ser un objeto JSON."})

    name = body_data.get("name")
    if not name or str(name).strip() == "":
        return build_response(400, {"error": "El nombre no puede estar vacío o ausente."})

    return build_response(200, {"message": f"Hola, {name}!"})
```

| Validación (en orden) | Respuesta |
|---|---|
| Body ausente o vacío | 400 |
| Body que no es JSON | 400 `JSON inválido` |
| JSON que no es un objeto (lista, string, número) | 400 |
| `name` ausente, vacío o solo espacios | 400 |
| Todo correcto | 200 |

**Dos request IDs:**

| ID | Origen | Dónde aparece |
|---|---|---|
| `requestContext.requestId` | API Gateway | Header `apigw-requestid` de la respuesta al cliente |
| `context.aws_request_id` | Lambda | Líneas `START` / `END` / `REPORT` de los logs |

Loguear ambos permite ir desde un error reportado por un cliente hasta su ejecución en CloudWatch.

## 5. Verificación

| # | Prueba | Esperado | Resultado |
|---|---|---|---|
| V1 | `POST` `{"name": "Facundo"}` | 200 | ✅ |
| V2 | `POST` `{}` y `{"name": ""}` | 400 | ✅ |
| V3 | `POST` `hola` / `{"name" = "Facundo"}` | 400 `JSON inválido` | ✅ |
| V4 | `GET /hello` | 404 generado por API Gateway, sin invocar la Lambda | ✅ |
| V5 | Logs | Método, path y request IDs; sin headers | ✅ |
| V6 | 60 requests en paralelo | Algunas 429 | ✅ `50 × 200`, `10 × 429` |
| V7 | `fetch` desde el frontend | Respuesta OK | ✅ |
| V7b | `fetch` desde `https://example.com` | Bloqueado por CORS en el preflight | ✅ |
| V8 | `POST` `[]`, `"hola"`, `123` | 400 | ✅ |

**Comandos útiles:**

```text
# Request con status y headers
curl -i -X POST https://<api-id>.execute-api.us-east-1.amazonaws.com/hello \
  -H "Content-Type: application/json" -d '{"name": "Facundo"}'

# Prueba de throttling (subshell sin avisos de jobs, con conteo de status)
( for i in $(seq 1 60); do curl -s -o /dev/null -w "%{http_code}\n" -X POST <url>/hello \
  -H "Content-Type: application/json" -d '{"name":"x"}' & done; wait ) | sort | uniq -c

# Configuración del stage (throttling)
aws apigatewayv2 get-stage --api-id <api-id> --stage-name '$default'

# Logs de todos los streams, en vivo
aws logs tail /aws/lambda/cloud-sec-checklist-api --since 10m --follow
```

## 6. Debugging

### 6.1 Body sin parsear

**Síntoma:** `POST` con `{"name": "Facundo"}` → 400.
**Causa:** el handler leía `event.get("name")`, pero con API Gateway `name` llega dentro de `event["body"]`, como string.
**Solución:** `json.loads(event["body"])` y luego leer `name`.

### 6.2 JSON válido que no es un objeto

**Síntoma:** `POST` con `[]` → **500** `{"message":"Internal Server Error"}`.

**Evidencia** (`aws logs tail`):

```text
[ERROR] AttributeError: 'list' object has no attribute 'get'
Traceback (most recent call last):
  File "/var/task/lambda_function.py", line 30, in lambda_handler
    name = body_data.get("name")
```

**Causa:** `json.loads` acepta listas, strings y números. Una lista no tiene `.get()`.
**Solución:** validar con `isinstance(body_data, dict)` → 400 (es un error del cliente).

**Observaciones:**

- El cliente recibió un 500 genérico; el traceback quedó solo en CloudWatch. **Nunca se devuelven tracebacks al cliente** (*information disclosure*).
- La métrica **Errors** de Lambda cuenta excepciones no manejadas. Un 400 devuelto por el código es una ejecución exitosa para Lambda.

### 6.3 "No aparecen los logs"

**Causa:** los logs existían, pero en otro **log stream**. Cada entorno de ejecución escribe en su propio stream; las requests a un entorno caliente agregan eventos al mismo stream, por lo que el contador de streams no aumenta.

```text
Log group  /aws/lambda/cloud-sec-checklist-api      ← uno por función
 └── Log stream 2026/10/07/[$LATEST]<id-entorno>     ← uno por entorno de ejecución
      └── Log events (START, prints, ERROR, REPORT)  ← uno por línea
```

**Herramienta:** `aws logs tail` agrupa todos los streams. Al leer logs, agrupar por **RequestId**: las líneas de distintos escritores (prints y runtime) pueden aparecer desordenadas por milisegundos.

### 6.4 El throttling no actuaba

**Síntoma:** 60 requests en paralelo → `60 × 200`.

**Evidencia indirecta (no concluyente):** la métrica *Invocations* mostraba 60 invocaciones, pero agrupa por minuto y no permite ver el comportamiento por segundo.

**Evidencia directa** (`get-stage`):

```json
"ThrottlingBurstLimit": 10,
"ThrottlingRateLimit": 20.0
```

**Causa:** valores invertidos (rate 20 / burst 10). El balde se reponía más rápido de lo que CloudShell lanzaba las requests.
**Solución:** rate 10 / burst 20 → `50 × 200`, `10 × 429`.

> **Lección:** leer la configuración (evidencia directa) resolvió en un minuto lo que dos pruebas indirectas no podían determinar.

## 7. Costos

Según la [página oficial de precios de API Gateway](https://aws.amazon.com/api-gateway/pricing/):

| Concepto | Precio | Uso del proyecto |
|---|---|---|
| HTTP API | USD 1,00 por millón de requests | Cientos de requests → fracciones de centavo |
| Free Tier | 1 M de llamadas/mes durante 12 meses (modelo anterior); en una cuenta con Free plan se descuenta de créditos | — |

| Riesgo | Mitigación |
|---|---|
| Denial of wallet | Throttling (D27) + Cognito (Etapa 9) |
| Access logs en CloudWatch | No activados en esta etapa. **Activados en la Etapa 10** (D85, JSON, retención 1 semana): ver [10-cloudwatch.md §4.3](10-cloudwatch.md) |
| WAF | No utilizado (D15) |

## 8. Relación con Cloud Security

| Control | Implementación |
|---|---|
| Solo esta API (y esta ruta) invoca la Lambda | Resource-based policy con `Condition` sobre el ARN |
| Cifrado en tránsito | API Gateway solo acepta HTTPS |
| Abuso y costo | Throttling 10/20 |
| Uso desde sitios ajenos | CORS restringido al dominio de CloudFront |
| Validación de entrada | 5 validaciones antes de usar los datos |
| Sin *information disclosure* | Errores genéricos al cliente; detalle solo en logs |
| Datos sensibles en logs | Solo método, path e IDs (D31) |
| Autenticación | ⚠️ **Pendiente** (Etapa 9): hasta entonces la API es pública |

## 9. Cómo revertir esta etapa

| Paso | Acción | Motivo |
|---|---|---|
| 1 | API Gateway → la API → **Delete** | — |
| 2 | Lambda → *Configuration* → *Permissions* → borrar **todos** los statements de API Gateway (desde la Etapa 7 hay uno por ruta: 5) | Quedan huérfanos, apuntando a una API inexistente |
| 3 | Verificar que la API no aparece y que la Lambda no tiene statements | *Destroy → Verify* |

## 10. Cosas que NO se deben hacer

- ❌ Usar `Access-Control-Allow-Origin: *`.
- ❌ Considerar CORS como mecanismo de autenticación.
- ❌ Dejar una API pública sin throttling.
- ❌ Confiar en que la URL de la API es secreta.
- ❌ Devolver tracebacks o detalles internos al cliente.
- ❌ Loguear el event completo.
- ❌ Concluir sobre el throttling con métricas agregadas por minuto: verificar la configuración.
