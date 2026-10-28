# Etapa 11 — Checks read-only, findings y score

> 2026-10-25 → 2026-10-28. Decisiones D89–D101 · [ADR-009](architecture-decisions/009-checks-read-only.md) · PRs #19 a #22.
> Marcas: **[CONFIRMADO-REPO]** = leído en el código · **[CONVERSACIÓN]** = configurado a mano en la consola o CloudShell según el historial.

## 1. Objetivo

Hasta la Etapa 10, OpenAegis solo **guardaba** controles cuyo estado cargaba una persona. Nadie iba a mirar la cuenta. Esta etapa agrega al que mira: **checks de solo lectura** con boto3 que evalúan la cuenta real y dejan **findings** con evidencia, un **score** y un botón **Escanear** en la SPA.

```text
 CONTROL (la regla)            CHECK (el que mira)             FINDING (lo que encontró)
 "S3-003: buckets que     ──►  función Python con boto3   ──►  bucket-a: PASS
  solo aceptan TLS"            solo lectura (Get/List/          bucket-b: FAIL  ← evidencia:
  severidad MEDIUM             Describe)                        "no tiene un Deny con aws:SecureTransport=false"
                                                                         │
                               SCAN = correr todos los checks una vez    ▼
                                                               SCORE = cuánto cumple la cuenta
```

Regla del proyecto: **check → finding → reporte** separados. El check no sabe de DynamoDB ni de HTTP.

## 2. Conceptos clave

### 2.1 Control, check, finding, scan y score

| Concepto | Qué es | Dónde vive |
|---|---|---|
| **Control** | La regla. Si tiene `check_id` es **automático**; si no (`""`), **manual** (D92) | Tabla `cloud-sec-checklist-controls` |
| **Check** | La función que verifica la regla contra la cuenta, **solo leyendo** | `backend/checks.py` (`CHECKS`) |
| **Finding** | El resultado sobre **un recurso**: `PASS` / `FAIL` / `ERROR` + evidencia + fecha | Tabla `openaegis-findings` |
| **Scan** | Una pasada de todos los checks. Deja un resumen | Tabla `openaegis-scans` |
| **Score** | % de cumplimiento ponderado por severidad (D99) | Calculado en la SPA |

### 2.2 Los 5 checks [CONFIRMADO-REPO]

| `check_id` | Pregunta | APIs (solo lectura) | Recurso del finding |
|---|---|---|---|
| `s3-account-public-access-block` | ¿Las 4 opciones de Block Public Access están activas **a nivel cuenta**? | `s3control:GetPublicAccessBlock` | `account` |
| `s3-bucket-public-access-block` | ¿Cada bucket está protegido por su BPA **o** por el de la cuenta? (D97) | `s3:ListBuckets`, `s3:GetBucketPublicAccessBlock` | ARN de cada bucket |
| `s3-bucket-tls-only` | ¿La bucket policy tiene un `Deny` con `aws:SecureTransport=false`? (D96) | `s3:ListBuckets`, `s3:GetBucketPolicy` | ARN de cada bucket |
| `cloudtrail-multi-region-logging` | ¿Hay al menos un trail **multi-región** que esté **logueando**? | `cloudtrail:DescribeTrails` (con shadow trails), `GetTrailStatus` | `account` |
| `iam-root-mfa` | ¿El usuario root tiene MFA? | `iam:GetAccountSummary` → `AccountMFAEnabled` | `root` |

Ninguno lee datos (objetos de S3, eventos de CloudTrail) ni modifica nada. Ninguno recorre regiones: son globales o miran un trail que cubre todas (D98).

### 2.3 PASS, FAIL y ERROR

`ERROR` significa **"no se pudo evaluar"** (por ejemplo, `AccessDenied` sobre un bucket). No es lo mismo que `FAIL`:

| Findings del control | Status del control (D94) |
|---|---|
| Algún `FAIL` | `FAIL` |
| Algún `ERROR` (y ningún `FAIL`), o ningún finding | `REVIEW`: no se pudo confirmar que cumple |
| Todos `PASS` | `PASS` |

- Un `ERROR` de **un** bucket no corta el check: los demás buckets se evalúan igual.
- La evidencia guarda solo el **código** del error (`AccessDenied`), nunca el mensaje: el mensaje trae ARNs con el ID de la cuenta.
- Los recursos de cuenta se guardan como `account` o `root`, nunca con el ID de la cuenta.
- Un `ERROR` **no** dispara la alarma del scanner: la Lambda termina bien. Ver §10.

### 2.4 Inyección de dependencias: checks testeables sin AWS

`checks.py` **no importa boto3**. Cada check recibe un `ScanContext(client, account_id)`, donde `client("s3")` devuelve un cliente. En producción, `scanner.py` pasa clientes reales de boto3; en los tests, clientes falsos (`FakeS3`, `FakeCloudTrail`…) que devuelven respuestas armadas o lanzan errores. Así hay 35 tests de los checks que corren en milisegundos y sin credenciales.

Los errores se atrapan con `client.exceptions.ClientError`. Detalle aprendido: en `s3control`, `NoSuchPublicAccessBlockConfiguration` es una excepción **modelada**, pero en `s3` no (ni ella ni `NoSuchBucketPolicy`): ahí se reconoce por el **código** del error.

### 2.5 Findings: estado actual + historial de scans (D91)

- `openaegis-findings` (PK `control_id`, SK `resource_id`): cada scan **pisa** el finding del mismo recurso. Después borra los findings de ese control que no escribió este scan (`delete_stale_findings`). Ejemplo real: al borrar un bucket, sus findings desaparecieron solos en el scan siguiente (`stale_deleted: 2`).
- `openaegis-scans` (PK fija `"SCAN"`, SK `started_at` en ISO con formato fijo): un resumen por scan. El último se lee con `Query`, `ScanIndexForward=False`, `Limit=1`. Es el historial del que saldrá un gráfico de evolución.
- Los contadores del resumen (`pass_count`, `fail_count`, `error_count`) cuentan **findings**, no controles.

### 2.6 Invocación asincrónica: 202 Accepted (D93)

```text
SPA ── POST /scans ──► API ── lambda:Invoke (InvocationType="Event") ──► openaegis-scanner
   ◄── 202 en ~50 ms ──┘                                                     │ 2-5 s
SPA ── GET /scans/latest (cada 2 s) ──► hasta que cambia started_at  ◄───────┘ guarda el resumen
```

- La API no espera al scanner: su timeout es de 3 s y el scan puede tardar más.
- Los reintentos asincrónicos de Lambda se bajaron a **0**: un scan fallido no se repite solo. Lo avisa la alarma `openaegis-scanner-errors`.
- La SPA sabe que terminó cuando cambia el `started_at` del último scan. Compara **dos datos del servidor**: comparar contra la hora del navegador fallaría con un reloj desfasado (D100).

### 2.7 Least privilege a nivel de atributo (D94)

El scanner escribe el `status` de los controles automáticos, pero su rol **no** puede tocar ningún otro campo. La condición de IAM:

```json
"Condition": {
  "ForAllValues:StringEquals": { "dynamodb:Attributes": ["id", "status", "updated_at"] },
  "StringEquals": { "dynamodb:ReturnValues": ["NONE", "UPDATED_OLD", "UPDATED_NEW"] }
}
```

- `dynamodb:Attributes` lista **todos** los atributos que toca el pedido, incluida la clave (`id`): por eso va en la lista.
- `ReturnValues` se limita para que el scanner no pueda **leer** el item entero con `ALL_OLD`/`ALL_NEW`.

Del lado de la API, la regla de negocio: un `PATCH` con `status` sobre un control automático responde **`409`** (nadie puede tapar a mano un `FAIL` del scanner). Para editarlo a mano, primero hay que pasarlo a manual.

## 3. Decisiones técnicas

| # | Decisión | Por qué | Alternativas descartadas |
|---|---|---|---|
| D89 | Los checks corren en una **Lambda aparte**, `openaegis-scanner` (mismo zip, handler `scanner.lambda_handler`, timeout 30 s, 256 MB), con **su propio rol** | El rol de la API no lee la configuración de la cuenta (blast radius chico); timeout propio | En la Lambda de la API (su rol leería toda la cuenta; timeout 3 s); programado con EventBridge (se puede sumar después) |
| D90 | **Policy propia mínima** `openaegis-scanner-checks`: solo las acciones de los checks | Una herramienta de seguridad que pide permisos de más da mal ejemplo; auditable (D48) | `SecurityAudit` (cientos de servicios; AWS la cambia cuando quiere) |
| D91 | **Estado actual + historial de scans**: `openaegis-findings` (PK `control_id`, SK `resource_id`) y `openaegis-scans` (PK `"SCAN"`, SK `started_at`), on-demand, sin índices | `Query` por control (D40) directo; el historial del score queda | Historial completo por recurso (crece sin fin); por scan con GSI (un índice desde el día 1) |
| D92 | Campo **`check_id`** en el control; solo acepta los `check_id` de `CHECKS` o `""` (manual) | Explícito; el `code` es editable; un error de tipeo da `400` al guardar, no un `ERROR` en el scan | Vincular por `code`; texto libre |
| D93 | `POST /scans` **asincrónico**: `InvocationType="Event"` → `202`; reintentos asincrónicos en 0 | La API sigue rápida; el scan puede durar hasta 30 s | Sincrónico (timeout de 3 s, dos Lambdas facturando a la vez) |
| D94 | El **scanner escribe el `status`** de los controles automáticos, con una condición de IAM que solo le deja escribir `status` y `updated_at`. La API rechaza con `409` el `status` manual de un automático (y con `400` un `POST` con `check_id` y `status`) | La SPA y el score leen `status` como siempre; least privilege por atributo | Calcularlo al leer (N+1 consultas); calcularlo en la SPA (regla de negocio en el frontend) |
| D95 | Borrar un control con findings → **`409`** "pasalo a manual". Pasarlo a manual (`check_id: ""`) **borra sus findings** | Dos pasos deliberados: nadie pierde evidencia por accidente. Resuelve el caso que D40 no previó (un manual con findings viejos sería imborrable) | `409` siempre; borrado en cascada |
| D96 | El check de "cifrado de S3" se **reemplaza** por `s3-bucket-tls-only` | Desde enero de 2023 todo bucket nuevo tiene SSE-S3: el check siempre daría `PASS` y no aportaría información | Exigir SSE-KMS (USD 1/mes por clave); eliminarlo |
| D97 | Un bucket sin BPA propio, con el BPA de la cuenta completo → **`PASS` con evidencia** ("cubierto por el de la cuenta") | Mide la protección **efectiva**; el riesgo de desactivar el de la cuenta ya lo mide otro check | `FAIL` igual (ruido sobre algo protegido) |
| D98 | **Sin loop por región** en la V1 | Los 5 checks son globales o multi-región | Recorrer todas las regiones (más llamadas sin beneficio) |
| D99 | **Score ponderado** por severidad (crítica 8, alta 4, media 2, baja 1); `REVIEW` no suma; se calcula **en la SPA** con `GET /controls` | Arreglar un crítico pesa más que arreglar uno bajo; refleja también los cambios manuales sin esperar un scan | % simple; dos scores (verificado/declarado); calcularlo en el scanner |
| D100 | La SPA espera el scan con **polling** a `GET /scans/latest` cada 2 s hasta que **cambia** `started_at`, con límite de 60 s | No depende del reloj del navegador; sin infraestructura nueva | No esperar; WebSocket |
| D101 | **Remediación manual** de los `FAIL` del primer scan: `Deny` sin TLS en las bucket policies; trail multi-región `openaegis-trail` solo con management events, sin KMS, con log file validation y lifecycle de 90 días | Cierra los dos `FAIL` reales a costo ~0; la app sigue sin remediar (fuera de la V1) | CloudWatch Logs + KMS en el trail (~USD 1/mes + ingesta); aceptar el riesgo |

## 4. Configuración realizada

### 4.1 Paso 11.1 — Diseño (2026-10-25)

Decisiones D89–D92, sin código ni AWS. Quedaron respondidas las dos preguntas abiertas de etapas anteriores: `SecurityAudit` vs. policy propia (D90) y qué regiones evalúa cada check (D98).

### 4.2 Paso 11.2 — Tablas (2026-10-25) [CONVERSACIÓN]

`openaegis-findings` y `openaegis-scans`, on-demand, sin índices, cifrado *Owned by Amazon DynamoDB*. Verificadas con `describe-table` (claves, modo e índices).

### 4.3 Pasos 11.3 y 11.4 — Scanner y primer check (2026-10-26, PR #19) [CONFIRMADO-REPO + CONVERSACIÓN]

| Archivo | Qué hace |
|---|---|
| `backend/checks.py` | Los checks (sin boto3), `CHECKS`, `run_checks`, `control_status` |
| `backend/scanner.py` | Handler `scanner.lambda_handler`: lista los controles con `check_id` → corre los checks → guarda findings → borra los viejos → escribe el `status` → guarda el resumen. El ID de la cuenta sale de `context.invoked_function_arn` |
| `backend/findings_repository.py` | Único módulo que habla con las tablas de findings y scans |
| `backend/repository.py` | + `set_control_status` (solo `status` y `updated_at`, sin `ReturnValues`) |

Lambda `openaegis-scanner`: Python 3.14, arm64, 256 MB, timeout 30 s, log format JSON (nivel INFO), retención 1 semana, variables `TABLE_NAME`, `FINDINGS_TABLE`, `SCANS_TABLE`. Alarma `openaegis-scanner-errors` (`Errors` ≥ 1 en 5 min → SNS). Sin resource-based policy: solo la invoca la API, con permisos del rol de la API.

**Primer finding real:** el BPA de la cuenta dio `FAIL`. Se corrigió en la consola y el scan siguiente dio `PASS`: el ciclo *FAIL → corrección → PASS* que la app tiene que mostrar.

### 4.4 Paso 11.5 — API (2026-10-27, PR #20) [CONFIRMADO-REPO + CONVERSACIÓN]

| Ruta | Respuesta |
|---|---|
| `POST /scans` | `202` (invoca al scanner de forma asincrónica) |
| `GET /scans/latest` | `200 {"item": {...}}` o `{"item": null}` |
| `GET /findings?control_id=<id>` | `200 {"items": [...]}` · `400` sin `control_id` o inválido |

Las 3 rutas tienen el JWT authorizer con scope `openid` y un statement propio en la resource-based policy de la API (D57). Policy nueva en el rol de la API, `openaegis-api-scans`: `lambda:InvokeFunction` sobre el scanner, `Query`/`BatchWriteItem` sobre findings (para el `409` del `DELETE` y el borrado al pasar a manual) y `Query` sobre scans. Variable nueva en la API: `SCANNER_FUNCTION`.

Verificado: `202`, `200`, `400`, `400` con la lista de `check_id` válidos, `409` en el `PATCH` y `409` en el `DELETE`; las 8 rutas con JWT + `openid`; el mismo `CodeSha256` en las dos Lambdas.

### 4.5 Paso 11.6 — El resto de los checks (2026-10-27, PR #21) [CONFIRMADO-REPO + CONVERSACIÓN]

5 statements más en `openaegis-scanner-checks`, todos de lectura. Controles creados **por la API**: `S3-003`, `S3-007`, `CT-001` e `IAM-001` (el `S3-002` existente era de cifrado y quedó manual). 83 tests en total.

| Scan | Resultado | Qué se hizo |
|---|---|---|
| 1 | 3 PASS, 2 FAIL: TLS del bucket del frontend y sin trail | — |
| 2 | S3-003 en `PASS` | `Deny` sin TLS en la bucket policy, después de verificar que CloudFront usa `redirect-to-https` (con OAC, CloudFront le habla a S3 con el protocolo del visitante) |
| 3 | CT-001 en `PASS`, pero 2 `FAIL` nuevos en S3-003 | Trail creado: el check encontró **los buckets nuevos** de CloudTrail sin el `Deny` |
| 4 | 7 findings `PASS`, 0 `FAIL`, `stale_deleted: 2` | Bucket huérfano borrado y `Deny` en el bucket del trail. CloudTrail siguió entregando logs |

### 4.6 Paso 11.7 — SPA (2026-10-28, PR #22) [CONFIRMADO-REPO + CONVERSACIÓN]

| Pantalla | Cambio |
|---|---|
| Formulario | Select "Cómo se evalúa" (Manual o un check). Si es automático, el estado no se edita y el body va **sin** `status` |
| Tabla | Columna Evaluación; "Cambiar estado" deshabilitado en los automáticos |
| Panel de detalle | Nombre del check y tabla de findings (resultado, recurso, evidencia) |
| Dashboard | "Último scan" con botón **Escanear**, y KPI **Score de seguridad** |

Archivos nuevos: `lib/checks.ts` (textos), `lib/score.ts` (función pura) y `lib/use-scans.ts` (hooks, incluido el polling). Desplegada con el procedimiento de [08 §4.11](08-frontend.md); la subida a S3 confirmó que el `Deny` sin TLS no afecta a `aws s3 sync` (usa HTTPS).

Pruebas: manuales del usuario contra la API real y 13 con Playwright **fuera del repo**, con una sesión falsa y la API simulada con las reglas del backend (incluido el timeout de 60 s con el reloj simulado).

### 4.7 Debugging en el camino

| Problema | Causa | Lección |
|---|---|---|
| Logs del scanner en texto plano | El log format no se configuró al crear la Lambda | `update-function-configuration --logging-config LogFormat=JSON,...` |
| El 2º scan siguió en `FAIL` | Corrió antes de que se guardara el BPA de la cuenta | Verificar el cambio antes de re-escanear |
| `401` en todas las rutas | `AUTH` vacía | `echo ${#AUTH}` antes de probar |
| La consola creó statements `*/path` en las dos Lambdas | "Attach integration" agrega permisos por su cuenta | Borrarlos con `remove-permission` (D57) |
| Variables y zip de la API aplicados al scanner | Dos funciones abiertas en la consola | Verificar el título de la pantalla |
| Rutas nuevas apuntando a la integración del scanner | Se eligió la función equivocada | `update-route --target`; borrar las integraciones sobrantes |
| **`S3-001` borrado** por un `DELETE` de prueba | Corrió con el código **viejo** (sin el `409`) | Restaurado con el mismo `id`. Antes de una prueba destructiva, verificar `CodeSha256` |
| Rutas sin scope | No se configuró al adjuntar el authorizer | `update-route --authorization-scopes openid` |
| `S3-002` (Encryption) convertido en automático por error | El `PATCH` corrió en el mismo pegado que el `GET`, antes de leer el título | Comando de lectura → leer → recién ahí el de escritura. Revertido con `check_id: ""` |
| `jq` devolvía `null` | La API usa `{"error": ...}` y `{"item": ...}`, no `.message` ni el objeto suelto | Mirar el contrato (`openapi.yaml`) |
| El `Deny` se revirtió sin querer | El comando de revertir estaba en un bloque copiable | Los comandos condicionales van **comentados**. El scan siguiente lo detectó |
| Bucket de CloudTrail con el ID de la cuenta en el nombre, y otro huérfano | La consola propone `aws-cloudtrail-logs-<cuenta>-…` y un primer intento dejó un bucket | Elegir el nombre. El check guardó el ID en un `resource_id` hasta que el bucket se borró |
| "Cambiar estado" deshabilitado pero clickeable en la tabla | En `ButtonDropdown`, el `disabled` del grupo no se hereda | Deshabilitar cada opción. La API igual respondió `409`: la UI es comodidad, el backend protege |
| `dist.zip` no se pudo subir a CloudShell | CloudShell no pisa archivos | `rm -f ~/dist.zip` antes de subir |

## 5. Plan de la etapa

| Paso | Qué | Estado |
|---|---|---|
| 11.1 | Diseño (D89–D92) | ✅ 2026-10-25 |
| 11.2 | Tablas `findings` y `scans` | ✅ 2026-10-25 |
| 11.3 | Código del scanner + primer check + tests sin AWS | ✅ PR #19 |
| 11.4 | Lambda `openaegis-scanner` + rol mínimo + alarma + primer scan | ✅ 2026-10-26 |
| 11.5 | `check_id`, rutas de scans y findings, reglas de controles automáticos | ✅ PR #20 |
| 11.6 | El resto de los checks + remediación de los `FAIL` | ✅ PR #21 |
| 11.7 | Score + pantallas en la SPA + deploy | ✅ PR #22 |
| 11.8 | Docs y checkpoint | ✅ este documento |

## 6. Verificación (resumen de la etapa)

| Qué | Resultado |
|---|---|
| Tests | 83 OK (`python -m unittest discover -s tests`), sin AWS |
| Scanner | 5 controles evaluados en ~2 s, sin `AccessDenied` |
| Último scan | 7 findings `PASS`, 0 `FAIL`, 0 `ERROR`; los 5 controles automáticos en `PASS` |
| Least privilege | El scanner solo escribe `status`/`updated_at` de los controles (condición IAM); la API no lee la configuración de la cuenta |
| Reglas de negocio | `409` al cambiar a mano el estado de un automático y al borrar un control con findings |
| SPA en producción | Escanear (`POST /scans` → `202`, sin errores de CORS), findings en el panel, score y recarga en `/app/controles` |

## 7. Costos

| Recurso | Costo |
|---|---|
| Lambda `openaegis-scanner` (2-5 s, 256 MB por scan) | Free tier |
| DynamoDB `openaegis-findings` y `openaegis-scans` (on-demand, pocos items) | Free tier |
| Llamadas de lectura a S3, IAM y CloudTrail | Sin cargo o fracciones de centavo |
| Trail `openaegis-trail` | Primera copia de management events **gratis** (página de precios de CloudTrail) |
| Bucket de logs del trail | Almacenamiento + PUTs de S3: centavos por mes; techo de 90 días por el lifecycle |

## 8. Relación con Cloud Security

Los 5 checks corresponden a controles conocidos de los estándares de AWS (como referencia, no como certificación):

| Check | Control equivalente en AWS Security Hub (FSBP / CIS) |
|---|---|
| `s3-account-public-access-block` | S3.1 |
| `s3-bucket-public-access-block` | S3.8 |
| `s3-bucket-tls-only` | S3.5 |
| `cloudtrail-multi-region-logging` | CloudTrail.1 |
| `iam-root-mfa` | IAM.9 |

Lo que la etapa mostró en la práctica:

- **Un check automático encuentra lo que nadie revisa:** los buckets que creó la consola de CloudTrail aparecieron en `FAIL` sin que nadie los buscara, y un `Deny` revertido por error se detectó en el scan siguiente.
- **La herramienta aplica a sí misma lo que mide:** el scanner tiene permisos de lectura mínimos, escritura limitada a 2 atributos y ningún permiso sobre la configuración que evalúa.
- **Evidencia sin datos sensibles:** ni mensajes de error, ni ARNs con la cuenta, ni el ID de la cuenta.
- OpenAegis **no** reemplaza a Security Hub ni a Prowler (cientos de checks): es un proyecto educativo con 5.

## 9. Cómo revertir esta etapa

| Qué | Cómo |
|---|---|
| Rutas nuevas | `delete-route` de `POST /scans`, `GET /scans/latest`, `GET /findings` + `remove-permission` de sus statements |
| Scanner | Borrar la Lambda `openaegis-scanner`, su rol, su log group y la alarma `openaegis-scanner-errors` |
| Rol de la API | Quitar la policy `openaegis-api-scans` y la variable `SCANNER_FUNCTION` |
| Tablas | `delete-table` de `openaegis-findings` y `openaegis-scans` |
| Trail | `delete-trail --name openaegis-trail`; vaciar y borrar su bucket (sin versionado) |
| `Deny` sin TLS | `put-bucket-policy` con la policy anterior (sacar el statement `DenyInsecureTransport`) |
| Código | Revertir los PRs #19 a #22 y desplegar el zip y la SPA anteriores |

## 10. Pendientes y mejoras posibles

- **Alarma por findings `ERROR`:** hoy un `AccessDenied` deja el control en `REVIEW` sin avisar. Un metric filter sobre el log `check con error` lo resolvería.
- **`updated_at` en cada scan:** el scanner escribe `updated_at` aunque el status no cambie, y llena "Actividad reciente" de ruido. Alternativas: escribir solo si el status cambia (condición en el `UpdateItem`) o un `evaluated_at` aparte.
- **Scans programados** con EventBridge (D89 lo dejó abierto).
- **Gráfico de evolución del score** con `openaegis-scans`.
- **`openapi.yaml`** todavía dice "Sin autenticación" y `security: []`: falta documentar el JWT.
- El rol de la API tiene **dos** policies administradas `AWSLambdaBasicExecutionRole-…` (una de más, creada por la consola).
- Patrones de Cognito en `check_identifiers.py` (pendiente de la Etapa 9).
- Pruebas de Playwright en el repo (Etapa 14; sería una dependencia nueva).
- El procedimiento de deploy de la SPA tiene que empezar con `rm -f ~/dist.zip`.

## 11. Cosas que NO se deben hacer

- Dar al scanner `SecurityAudit`, `ReadOnlyAccess` o cualquier permiso de escritura sobre recursos evaluados (D90).
- Atrapar `Exception` en un check: un error desconocido tiene que llegar a la métrica `Errors`.
- Guardar mensajes de error de AWS, ARNs con la cuenta o el ID de la cuenta en findings o logs.
- Cambiar a mano el `status` de un control automático en DynamoDB: el próximo scan lo pisa, y es justo lo que el `409` impide por la API.
- Correr una prueba destructiva sin verificar antes el `CodeSha256` desplegado.
- Aceptar el nombre de bucket que propone la consola de CloudTrail (lleva el ID de la cuenta).
- Presentar el score como una garantía de seguridad: mide 5 controles.

## 12. Checkpoint

| Tema | Resumen |
|---|---|
| **CONCEPTO** | Control → check → finding → scan → score; `ERROR` ≠ `FAIL`; checks testeables por inyección de dependencias |
| **ARQUITECTURA** | API y scanner en Lambdas separadas; invocación asincrónica con `202`; findings como estado actual + historial de scans |
| **SEGURIDAD** | Policy mínima de solo lectura; condición IAM por atributo; `409` para que nadie tape un `FAIL`; evidencia sin datos sensibles |
| **COSTOS** | USD 0 en la app; centavos por el bucket del trail, con techo de 90 días |
| **PRÁCTICA** | 2 `FAIL` reales corregidos; el check encontró buckets nuevos y una reversión accidental |
| **VERIFICACIÓN** | 83 tests, 13 pruebas de Playwright, scan final 7/7 `PASS`, SPA verificada en producción |

Preguntas:

1. Un atacante con acceso a la cuenta detiene el trail con `StopLogging`. ¿Qué muestra OpenAegis en el próximo scan, y por qué el check no se conforma con que el trail exista?
2. Agregás un check nuevo, `ec2-ebs-encryption`, y desplegás el zip solo en el scanner. ¿Qué pasa cuando intentás crear el control con ese `check_id` desde la SPA?
3. El scanner pierde el permiso `s3:GetBucketPolicy`. ¿Qué status queda en `S3-003`, suena alguna alarma, y cómo te enterarías hoy?
4. ¿Por qué el rol del scanner puede ejecutar `UpdateItem` en la tabla de controles y aun así no puede cambiar el `title` de un control?
