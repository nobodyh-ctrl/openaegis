# Etapa 6 — Amazon DynamoDB + CRUD de controles

> **Estado:** ✅ completada (2026-10-13)
> **Costo de la etapa:** fracciones de centavo (algunas decenas de lecturas y escrituras on-demand; almacenamiento de KB dentro de los 25 GB del Free Tier)

## 1. Objetivo

Darle **persistencia** a la aplicación y construir la API real de controles:

- entender NoSQL, partition key, sort key y la diferencia entre `GetItem`, `Query` y `Scan`;
- **diseñar el modelo de datos** a partir de las operaciones de la app (*access patterns*);
- crear la tabla y darle a la Lambda **solo** los permisos que necesita;
- implementar el CRUD completo: `GET`, `GET {id}`, `POST`, `PATCH` y `DELETE`;
- separar el backend por responsabilidades para poder testearlo y hacerlo evolucionar.

## 2. Conceptos clave

### 2.1 Qué problema resuelve

La Lambda es **stateless**: no puede guardar nada entre ejecuciones. Para que los controles existan mañana hace falta una base de datos. En una arquitectura serverless, lo natural es **DynamoDB**: no tiene servidor, cobra por uso y escala sola.

### 2.2 Vocabulario

| DynamoDB | SQL (equivalente aproximado) | Ejemplo |
|---|---|---|
| **Table** | Tabla | `cloud-sec-checklist-controls` |
| **Item** | Fila | Un control |
| **Attribute** | Columna | `title`, `severity` |
| **Primary key** | Primary key | `id` |

**Solo la primary key es obligatoria.** No hay esquema fijo: cada item puede tener atributos distintos. **El esquema lo controla el código** (por eso la validación es tan importante).

### 2.3 Partition key y sort key

| Tipo de clave | Compuesta por | Identifica un item por… |
|---|---|---|
| **Simple** | Partition key (PK) | La PK, que debe ser única |
| **Compuesta** | PK + sort key (SK) | La combinación PK + SK |

DynamoDB aplica un **hash** a la PK para decidir en qué partición (servidor) guarda el item. Por eso, con la PK, sabe exactamente dónde buscar. En la consola y en la CLI, la PK aparece como **`HASH`** y la SK como **`RANGE`**.

> **Regla:** se agrega una sort key cuando **un mismo valor de PK agrupa varios items** (por ejemplo, los findings de un control, ordenados por fecha). Si cada PK tiene un solo item, alcanza con la clave simple.

### 2.4 Cómo se lee: GetItem, Query y Scan

| Operación | Necesita | Lee | Costo |
|---|---|---|---|
| **GetItem** | La primary key completa | **Un** item | Mínimo |
| **Query** | La PK (y opcionalmente una condición sobre la SK) | **Una** partición | Proporcional a lo que devuelve |
| **Scan** | Nada | **Toda la tabla** | Proporcional al **tamaño de la tabla**, aunque se filtre |

Analogía: GetItem es buscar un libro por su código; Query, ir al estante de un autor; Scan, recorrer **toda** la biblioteca. Con decenas de controles, un Scan cuesta prácticamente nada. No hay que demonizarlo, hay que saber cuándo deja de ser aceptable.

### 2.5 Diseñar por access patterns

| SQL | DynamoDB |
|---|---|
| Se diseñan las tablas según los **datos**; las consultas vienen después | Se diseñan las **claves** según las **consultas** |
| `JOIN` | **No hay joins** ni foreign keys |
| `WHERE` sobre cualquier columna | Eficiente solo sobre la primary key (o índices creados para eso) |

Para esta app: **una** operación necesita **todos** los controles (listar) y **cuatro** necesitan **uno**, por su `id`.

### 2.6 Scan: paginación y la trampa del `Limit`

- Un Scan devuelve **como máximo 1 MB por llamada**. Si hay más, la respuesta trae **`LastEvaluatedKey`** y hay que pedir la página siguiente con `ExclusiveStartKey`.
- **`Count`** es lo que devolvió; **`ScannedCount`** es lo que **leyó** (y lo que se cobra).
- ⚠️ **`Limit` acota los items leídos, no los devueltos.** Con un `FilterExpression`, DynamoDB primero lee `Limit` items y **después** filtra. Ver el debugging 6.3.

### 2.7 Escrituras condicionales

DynamoDB **no valida la existencia** de un item por vos. Las tres operaciones de escritura tienen una trampa, y las tres se resuelven con `ConditionExpression`:

| Operación | Comportamiento por defecto | Riesgo | Condición usada |
|---|---|---|---|
| `PutItem` | Si la clave existe, **la pisa sin avisar** | Sobrescribir un control | `attribute_not_exists(id)` |
| `UpdateItem` | Si la clave **no** existe, **la crea** (*upsert*) | El `PATCH` sería una puerta trasera para crear controles sin `code`, `title` ni `created_at` | `attribute_exists(id)` |
| `DeleteItem` | Si la clave no existe, **responde éxito igual** | Un id mal escrito parece un borrado exitoso | `attribute_exists(id)` |

Si la condición falla, DynamoDB lanza **`ConditionalCheckFailedException`**, que el repositorio traduce a `None` y la API a **404**.

### 2.8 Expresiones, palabras reservadas y marcadores

`UpdateItem` no recibe un diccionario: recibe una **expresión**.

```text
UpdateExpression          = "SET #status = :status, #updated_at = :updated_at"
ExpressionAttributeNames  = {"#status": "status", "#updated_at": "updated_at"}
ExpressionAttributeValues = {":status": "FAIL", ":updated_at": "2026-10-13T22:47:04Z"}
```

| Marcador | Para qué |
|---|---|
| `#nombre` | `status` es una **palabra reservada** de DynamoDB. Con `#` se usan todos los nombres sin preocuparse |
| `:valor` | Los valores **nunca** van dentro de la expresión. Es la misma idea que una consulta parametrizada en SQL |

### 2.9 `boto3.resource` vs. `boto3.client`

| | `client` | `resource` ✅ |
|---|---|---|
| Formato | DynamoDB JSON tipado: `{"title": {"S": "..."}}` | JSON "normal": `{"title": "..."}` |
| Números | Strings con tipo `N` | **`Decimal`** de Python, que `json.dumps` no sabe serializar (lo resuelve `responses._json_default`) |

### 2.10 Capacity modes

| Modo | Cómo cobra | Riesgo |
|---|---|---|
| **On-demand** ✅ | Por request de lectura y de escritura | **No tiene techo propio**: el límite lo pone el throttling de API Gateway |
| Provisioned | Por capacidad reservada (WCU/RCU) por hora; el Free Tier incluye 25 WCU + 25 RCU | Si se supera la capacidad, DynamoDB rechaza requests (throttling) y el usuario ve 500 |

### 2.11 Control vs. finding

| Concepto | Qué es | Quién lo crea |
|---|---|---|
| **Control** | Una **regla**: *qué* debería cumplirse. La tabla guarda solo su estado **actual** (cada `PATCH` pisa el anterior) | El usuario |
| **Finding** | El **resultado** de evaluar un control sobre un recurso, en un momento. **Es el historial** | La Lambda de checks (Etapa 11) |

## 3. Decisiones técnicas

Detalle completo, con alternativas: [DECISIONS.md](DECISIONS.md#d32-en-adelante-etapa-6-y-posteriores-todavía-no-están-en-un-doc-de-etapa).

| # | Decisión | Alternativas evaluadas | Motivo |
|---|---|---|---|
| D32 | **DynamoDB** | RDS/Aurora | Serverless, pago por uso, acceso por IAM (sin credenciales de base de datos). RDS cobra por hora y requiere secretos |
| D33 | **On-demand** | Provisioned 5/5 | Costo mínimo; el throttling de API Gateway pone el techo |
| D34 | PK **`id` = UUID** + **`code`** legible | `code` como PK | La PK es inmutable; los findings van a referenciar un id que nunca cambia |
| D35 | **Sin sort key** | PK `id` + SK `created_at` | Un solo item por `id`; la SK obligaría a enviar la fecha en cada operación |
| D36 | `code` único validado **en el código** (Scan sin `Limit`) | Transacción que reserva el `code` | Simple; *race condition* teórica aceptada |
| D37 | Severidad `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` | Otra escala | Estándar de la industria |
| D38 | Fechas ISO 8601 UTC puestas por el servidor; `status` default `REVIEW` | — | Orden alfabético = cronológico |
| D39 | Findings en **tabla aparte**, 1:N | Single-table design | Claridad |
| D40 | **409** al borrar un control con findings | Cascada; huérfanos | No perder historial |
| D41 | Rutas REST sobre `/controls` y `/controls/{id}` | Verbos en la URL | El método HTTP es el verbo |
| D42 | **`PATCH`** para editar y cambiar estado | `PUT`; `POST`; ruta propia para el estado | Modificación parcial, idempotencia, menos rutas |
| D43 | `boto3.resource` | `boto3.client` | JSON normal |
| D44 | Inline policy con 5 acciones sobre 1 tabla | `AmazonDynamoDBFullAccess` | Least privilege |
| D45 | Standard, cifrado *Owned by Amazon DynamoDB*, sin PITR, sin GSI, **deletion protection desactivado temporalmente** | KMS; PITR; Standard-IA | Sin costo extra; la tabla se recrea con CDK |
| D46 | Backend en **5 módulos** | FastAPI + Mangum; Lambda Powertools | Testabilidad y evolución sin dependencias |
| D47 | Deploy con **zip**; el repo es la fuente de verdad | Editar en la consola | Un solo paso manual hasta CDK |
| D48 | **Self-hosted, single-account** | CLI; SaaS multi-tenant; híbrido | Los datos no salen de la cuenta del usuario |
| D49 | Validación declarativa (`FIELD_RULES`) = allowlist | `if` por campo | Un lugar para `POST` y `PATCH`; evita mass assignment |
| D50 | Escrituras condicionales | Leer antes de escribir | Ver 2.7 |
| D51 | Sin `except Exception` | 500 genérico | No ocultar errores de la métrica *Errors* |
| D52 | Traducir errores en el borde | Respuestas HTTP desde la validación | Desacople de AWS y de HTTP |
| D53 | **Borrado real** de controles (409 con findings, Etapa 11) | Soft delete; no permitir borrar | Un control es una regla, no un historial |
| D54 | `DELETE`: **404** si no existe, **200 + item borrado** (`ALL_OLD`) | Éxito silencioso; 204 | Consistente con el `PATCH`; sin casos especiales en `responses.py` |

> **Contexto para entrevistas:** la persistencia es una tabla de DynamoDB on-demand, diseñada a partir de los access patterns: PK `id` (UUID inmutable) y un `code` legible cuya unicidad se valida en el código. La Lambda accede con su execution role, que solo puede hacer las 5 operaciones del CRUD sobre esa tabla: no hay credenciales de base de datos. Uso escrituras condicionales para evitar sobrescrituras, upserts y borrados silenciosos, y una allowlist de campos contra mass assignment. El backend está separado en router, reglas de negocio, validación, repositorio y respuestas, y solo el repositorio conoce boto3.

## 4. Configuración realizada

### 4.1 Tabla

**Dónde:** consola → **DynamoDB** → región `us-east-1` → **Tables** → **Create table** → **Customize settings**.

| Opción | Valor | Por qué |
|---|---|---|
| Nombre | `cloud-sec-checklist-controls` | Prefijo del proyecto + entidad |
| Partition key | `id` (String) | D34 |
| Sort key | Ninguna | D35 |
| Table class | DynamoDB Standard | Standard-IA encarece las lecturas |
| Capacity | On-demand | D33 |
| Maximum table throughput | Sin configurar | El throttling de API Gateway cumple esa función |
| Secondary indexes | Ninguno | Ningún access pattern lo necesita |
| Encryption at rest | Owned by Amazon DynamoDB | Gratis; siempre hay cifrado, cambia quién gestiona la clave |
| Deletion protection | **Desactivado** (temporal) | D45: se borra al migrar a CDK |
| Point-in-time recovery | Desactivado | Tiene costo |
| Resource-based policy | Vacía | El acceso es por el rol de la Lambda |
| Tags | `Project = cloud-security-checklist` | D11 |

El primer item (`S3-001`) se cargó a mano: *Explore table items* → *Create item* → vista JSON, con un UUID generado en CloudShell (`python3 -c "import uuid; print(uuid.uuid4())"`).

### 4.2 Permisos de la Lambda

Inline policy **`controls-table-crud`** en el execution role (IAM → *Roles* → el rol de la función → *Add permissions* → *Create inline policy*):

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

Sin `dynamodb:*`, sin `DeleteTable` y sin otras tablas. `ConditionExpression` y `ReturnValues` no requieren permisos adicionales.

### 4.3 Lambda

| Configuración | Valor |
|---|---|
| Variable de entorno | `TABLE_NAME = cloud-sec-checklist-controls` (el código no tiene el nombre de la tabla escrito a mano) |
| Handler | `handler.lambda_handler` (antes `lambda_function.lambda_handler`) |
| Deploy | `Compress-Archive -Path backend\*.py -DestinationPath lambda.zip -Force` → *Code* → *Upload from* → *.zip file*. Los `.py` tienen que quedar en la **raíz** del zip |

### 4.4 API Gateway

| Ruta | Statement en la resource-based policy |
|---|---|
| `GET /controls`, `POST /controls` | Uno, `SourceArn` `.../*/*/controls` |
| `GET /controls/{id}`, `PATCH /controls/{id}`, `DELETE /controls/{id}` | Uno, `SourceArn` `.../*/*/controls/{id}` |

El permiso es **por path**: el segundo `*` del `SourceArn` es el método. CORS: Allow-Methods `GET`, `POST`, `PATCH`, `DELETE`. La ruta de prueba `POST /hello` y su statement se eliminaron.

### 4.5 Modelo de datos y backend

Modelo de la tabla, API y estructura de los 5 módulos: [ARCHITECTURE.md](ARCHITECTURE.md#3-backend-confirmado-repo).

## 5. Verificación

Todas las pruebas, con `curl` desde CloudShell:

| Ruta | Casos verificados |
|---|---|
| `GET /controls` | 200 con `items` y `count` |
| `GET /controls/{id}` | 200 · 404 inexistente · 400 `abc` · UUID sin guiones o en mayúsculas → 200 (normalización) |
| `POST /controls` | 201 · 400 por campo faltante, tipo (`"title": 123`, `"severity": ["HIGH"]`) o enum inválido · **409** por `code` duplicado, también con espacios (`" S3-001 "`) · campos extra (`"id": "hack"`, `"admin": true`) ignorados |
| `PATCH /controls/{id}` | 200 (`updated_at` cambia, `created_at` no) · 400 `title` vacío o solo espacios · **404 sin crear item** (`count` igual) · 400 `abc` · 400 `{}`, `{"admin": true}`, `{"created_at": ...}` · 409 `code` de otro control · 200 su propio `code` · 200 varios campos |
| `DELETE /controls/{id}` | 200 + item borrado · 404 al repetirlo (sin éxito silencioso) · `count` 4 → 3 · 400 `abc` · 404 inexistente · log con el `code` borrado |
| `POST /hello` | 404 `{"message":"Not Found"}` de API Gateway, sin invocar la Lambda |

**Comandos útiles:**

```text
# Variables para no repetir la URL
API=https://<api-id>.execute-api.us-east-1.amazonaws.com

# Configuración de la tabla
aws dynamodb describe-table --table-name cloud-sec-checklist-controls

# Contenido de la tabla (Scan: lee todo)
aws dynamodb scan --table-name cloud-sec-checklist-controls

# Count vs. ScannedCount (ver 6.3)
aws dynamodb scan --table-name cloud-sec-checklist-controls \
  --filter-expression "code = :c" --expression-attribute-values '{":c": {"S": "S3-002"}}' --limit 1

# Rutas, statements y CORS
aws apigatewayv2 get-routes --api-id <api-id> --query 'Items[].RouteKey'
aws lambda get-policy --function-name cloud-sec-checklist-api
aws apigatewayv2 get-api --api-id <api-id> --query CorsConfiguration

# Logs
aws logs tail /aws/lambda/cloud-sec-checklist-api --since 10m --filter-pattern DELETE
```

## 6. Debugging

### 6.1 `AccessDenied` en `dynamodb:Scan` (provocado a propósito)

**Síntoma:** el primer `GET /controls` → **500**.
**Evidencia:** en `aws logs tail`, una `AccessDeniedException`: el rol no está autorizado a ejecutar `dynamodb:Scan` sobre la tabla.
**Causa:** deny by default: el rol solo tenía permisos de logs.
**Solución:** la inline policy `controls-table-crud`, con las acciones exactas sobre el ARN de la tabla.
**Lección:** el cliente ve un 500 aunque quien no tiene permiso es el **rol**. La verdad está en los logs.

### 6.2 `uuid.UUID()` fuera del `try`

**Síntoma:** `GET /controls/abc` → 500 en vez de 400.
**Causa:** la conversión que lanza `ValueError` estaba fuera del `try`.
**Solución:** validar dentro del `try` → 400. Además, normalizar el id a su forma canónica (minúsculas, con guiones). Sin esa normalización, un id en mayúsculas no encontraría el item y daría un 409 falso contra sí mismo en el `PATCH`.

### 6.3 `Limit=1` en un Scan con filtro: los dos `S3-002`

**Síntoma:** el chequeo de `code` duplicado no detectaba el duplicado, y se crearon **dos** `S3-002`.
**Evidencia:**

```text
aws dynamodb scan ... --filter-expression "code = :c" ... --limit 1
"Count": 0, "ScannedCount": 1, "LastEvaluatedKey": {...}
```

**Causa:** `Limit` acota los items **leídos**. DynamoDB leyó un item, no era el `S3-002`, filtró y devolvió 0, con más páginas pendientes.
**Solución:** Scan paginado **sin `Limit`** en `find_control_by_code`.
**Consecuencia:** uno de los duplicados se dejó a propósito y fue la primera prueba del `DELETE`.

### 6.4 Tipos de datos → 500

**Síntoma:** `"title": 123` → `TypeError` en `len()`; `"severity": ["HIGH"]` → `unhashable type: 'list'`. Los dos terminaban en 500.
**Causa:** se validaba que los campos **existieran**, no **de qué tipo** eran.
**Solución:** `FIELD_RULES`: primero `isinstance(valor, str)`, después `strip`, obligatorio, largo y enums.

### 6.5 `except Exception`

**Problema:** un `except` amplio convertía cualquier error en una respuesta "controlada". La invocación contaba como exitosa y desaparecía de la métrica *Errors*.
**Solución:** atrapar **solo** `ConditionalCheckFailedException`, que tiene un significado conocido (no existe).

### 6.6 `PATCH` con `title` vacío

**Síntoma (revisión de código):** `{"title": ""}` → 200, y el control quedaba sin título.
**Causa:** el chequeo de "no vacío" tenía un `not partial`, así que no se ejecutaba en el `PATCH`.
**Solución:** "obligatorio" en el `PATCH` significa *"no hace falta que venga, pero si viene, no puede estar vacío"*. Se prueba también con `"   "`.

### 6.7 ¿Quién respondió?

| Síntoma | ¿Hay log en la Lambda? | Quién respondió |
|---|---|---|
| 404 `{"message":"Not Found"}` | No | API Gateway: la ruta no existe en la API |
| 404 `{"error": "Ruta no encontrada: ..."}` | Sí | El router de `handler.py`: la ruta existe en la API pero no en `ROUTES` |
| 500 y **ninguna** línea `START` | No | API Gateway: no pudo invocar la Lambda (por ejemplo, falta el statement) |
| 500 con traceback | Sí | La Lambda falló: el detalle está en el traceback |

**Regla:** si no hay log en la Lambda, el problema está **antes** de la Lambda.

## 7. Costos

Según la [página oficial de precios de DynamoDB](https://aws.amazon.com/dynamodb/pricing/) (verificada el 2026-10-08, `us-east-1`):

| Concepto | Precio | Uso del proyecto |
|---|---|---|
| Escrituras on-demand | USD 0,625 por millón | Decenas → fracciones de centavo |
| Lecturas on-demand | USD 0,125 por millón | Cientos → fracciones de centavo |
| Almacenamiento | 25 GB gratis (Free Tier permanente) | KB |

En una cuenta con Free plan, el consumo se descuenta de los créditos. **Verificar los precios vigentes antes de reutilizar estos números.**

| Riesgo | Mitigación |
|---|---|
| On-demand no tiene techo propio | Throttling de API Gateway (rate 10 / burst 20) |
| Scans sobre tablas grandes | Diseño por access patterns; con decenas de items es irrelevante |
| Point-in-time recovery | No activado |
| KMS con clave propia | No usado: cifrado *Owned by Amazon DynamoDB* |
| Provisioned + auto scaling (usa alarmas de CloudWatch) | No usado |

## 8. Relación con Cloud Security

| Control | Implementación |
|---|---|
| Sin credenciales de base de datos | Acceso por el execution role (credenciales temporales de STS) |
| Least privilege | 5 acciones sobre 1 tabla; sin `DeleteTable` (*blast radius* acotado) |
| Cifrado en reposo y en tránsito | Siempre activo en DynamoDB; la API de AWS es HTTPS |
| Mass assignment | Allowlist `FIELD_RULES`; `id`, `created_at` y `updated_at` los pone el servidor |
| Validación de entrada | Tipo, `strip`, obligatorios, largos, enums |
| Integridad | Escrituras condicionales (2.7) |
| Inyección | Sin SQL; valores siempre como marcadores `:valor` en las expresiones |
| Sin *information disclosure* | Errores con mensajes genéricos; los tracebacks solo en CloudWatch |
| Auditoría | Cada request queda logueada con ruta e IDs; el `DELETE` loguea el `code` borrado |
| Autenticación | ⚠️ **Pendiente** (Etapa 9): hoy cualquiera con la URL puede leer, crear, editar y borrar controles. El throttling limita el abuso, pero no lo impide |
| Protección de la tabla | ⚠️ Deletion protection desactivado temporalmente (D45) |

## 9. Cómo revertir esta etapa

| Paso | Acción | Motivo |
|---|---|---|
| 1 | API Gateway → la API → **Routes** → borrar las 5 rutas de `/controls` | — |
| 2 | Lambda → *Configuration* → *Permissions* → borrar los 2 statements (`/controls` y `/controls/{id}`) | Quedan huérfanos |
| 3 | IAM → el rol de la Lambda → borrar la inline policy `controls-table-crud` | No tiene sentido un permiso sobre una tabla inexistente |
| 4 | Lambda → *Configuration* → *Environment variables* → borrar `TABLE_NAME` | — |
| 5 | DynamoDB → la tabla → **Delete** (deletion protection está desactivado; si estuviera activo, habría que desactivarlo primero) | ⚠️ **Los datos se pierden**: sin PITR ni backups |
| 6 | Verificar: `aws dynamodb list-tables`, `get-routes`, `get-policy` | *Destroy → Verify* |

## 10. Cosas que NO se deben hacer

- ❌ Usar `AmazonDynamoDBFullAccess` o `dynamodb:*` en el rol de la Lambda.
- ❌ Poner `Limit` en un Scan con `FilterExpression` esperando que limite los resultados.
- ❌ Usar `UpdateItem` sin `attribute_exists` cuando el item tiene que existir (upsert).
- ❌ Confiar en que `DeleteItem` avisa si el item no existe.
- ❌ Usar `PutItem` sin `attribute_not_exists` para crear (sobrescritura silenciosa).
- ❌ Escribir nombres de atributos directamente en las expresiones (palabras reservadas) o concatenar valores del cliente.
- ❌ Guardar en la tabla los campos que manda el cliente sin una allowlist.
- ❌ Atrapar `Exception` para "evitar" 500.
- ❌ Editar el código en la consola de Lambda: la fuente de verdad es el repo.
- ❌ Activar PITR, KMS propio o provisioned con auto scaling sin revisar el costo.
- ❌ Usar la tabla de controles como historial: el historial son los findings.
