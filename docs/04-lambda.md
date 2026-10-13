# Etapa 4 — AWS Lambda + Python

> **Estado:** ✅ completada
> **Costo de la etapa:** USD 0 (invocaciones de prueba dentro del Free Tier permanente de Lambda)
>
> **Cambios posteriores (Etapa 6):** el handler pasó a ser `handler.lambda_handler` y el código se despliega como zip; el backend se separó en 5 módulos; se agregó la variable `TABLE_NAME` y la inline policy `controls-table-crud` al rol. Las secciones afectadas lo indican. Estado actual: [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Objetivo

Crear el primer componente del backend **sin servidores**:

- entender qué es Lambda y cómo ejecuta el código;
- escribir y probar un handler en Python con events escritos a mano, todavía sin API Gateway;
- entender el **execution role**: trust policy, permissions policy y credenciales temporales;
- leer los logs y las métricas de cada ejecución.

## 2. Conceptos clave

### 2.1 ¿Qué es Lambda?

Un servicio que **ejecuta una función cuando ocurre un evento** y cobra solo por el tiempo de ejecución.

| Backend tradicional | Lambda |
|---|---|
| Proceso corriendo siempre, esperando requests | No hay nada corriendo hasta que llega un evento |
| *Route handler* de un framework (Flask, Express) | Función **handler** que recibe un **event** |
| El equipo escala servidores o contenedores | AWS crea más entornos de ejecución automáticamente |
| Se paga 24/7 | Se paga por invocación y duración |

### 2.2 El handler

```text
def lambda_handler(event, context):
    ...
    return <respuesta>
```

| Parte | Qué es | Analogía |
|---|---|---|
| `event` | Diccionario con los datos de entrada. Su forma depende de **quién invoca** la función | El objeto `request` |
| `context` | Información de la ejecución (ID de la request, tiempo restante, etc.) | Metadatos del servidor |
| `return` | La respuesta. Si la invoca API Gateway, debe tener `statusCode`, `headers` y `body` | El `Response` |

> El `event` **no es una request HTTP cruda**: es un JSON que arma quien invoca la función. En la consola lo escribe quien prueba; con API Gateway trae método, path, headers y body.

**Formato de respuesta para API Gateway:** `body` es un **string** que contiene JSON, no un diccionario, porque el body de una respuesta HTTP es texto.

### 2.3 Ciclo de vida: cold start y warm start

```text
Llega un evento
   │
   ▼
¿Hay un entorno de ejecución disponible?
   ├── No → COLD START
   │        1. AWS crea un entorno aislado (micro-VM)
   │        2. Carga el runtime de Python
   │        3. Carga el código y ejecuta lo que está FUERA del handler
   │        4. Ejecuta el handler
   │
   └── Sí → WARM START: ejecuta directamente el handler

Tras responder, el entorno queda congelado un tiempo.
Si no recibe eventos, AWS lo destruye.
Cada Deploy descarta los entornos con el código anterior.
```

| Hecho | Implicación para el código |
|---|---|
| El código fuera del handler corre una vez por entorno | Crear ahí clientes reutilizables (por ejemplo, el de DynamoDB) |
| Los entornos se crean y destruyen sin aviso | **Stateless**: el estado se guarda en DynamoDB, no en memoria ni en disco |
| Puede haber varios entornos en paralelo | Cada uno tiene su propia memoria; no comparten variables globales |
| El cold start agrega latencia | En Python, una fracción de segundo; aceptable para el proyecto |

### 2.4 Permisos: dos direcciones

```text
        ¿QUIÉN puede invocarla?                      ¿QUÉ puede hacer?
                 │                                           │
API Gateway ──invoca──► [ LAMBDA ] ──credenciales del rol──► CloudWatch Logs
                 │                                           DynamoDB (futuro)
     Resource-based policy                            Execution role
   (adjunta a la Lambda)                       (rol que la Lambda asume)
```

| Mecanismo | Tipo | Responde | En esta etapa |
|---|---|---|---|
| **Execution role** | Identity-based (IAM role) | ¿Qué puede hacer la Lambda? | Solo escribir logs |
| **Resource-based policy** | Resource-based | ¿Quién puede invocar la Lambda? | Se configura en la Etapa 5 (API Gateway) |

### 2.5 Las dos policies de un rol

| Policy | Responde | Ejemplo |
|---|---|---|
| **Trust policy** | ¿**Quién puede asumir** el rol? | El servicio `lambda.amazonaws.com` |
| **Permissions policy** | ¿**Qué puede hacer** quien lo asume? | Escribir logs en CloudWatch |

**Cómo obtiene credenciales la Lambda:**

```text
Lambda ──sts:AssumeRole──► STS
                            │ ¿La trust policy permite a lambda.amazonaws.com?  → Sí
                            ▼
                Credenciales temporales (ASIA...)
                            │
                            ▼
        El código (boto3) las usa automáticamente, sin access keys
```

## 3. Decisiones técnicas

| # | Decisión | Alternativas evaluadas | Motivo |
|---|---|---|---|
| D18 | **Lambda** para el backend | EC2 con Flask; ECS Fargate; Lambda Function URL | Pago por uso, sin servidor, escalado automático. EC2 y Fargate cobran mientras corren |
| D19 | **Python 3.14** | Python 3.13; Python 3.15 (preview) | Versión estable más reciente. Las versiones en preview no se usan en el proyecto |
| D20 | **arm64** (Graviton) | x86_64 | Menor precio por GB-segundo; sin diferencias para código Python puro |
| D21 | **128 MB / timeout 3 s** | Más memoria; timeout mayor | El handler usa ~38 MB. Un timeout corto limita el costo ante cuelgues |
| D22 | **Sin Function URL** | Function URL con `AuthType: NONE` | Sería un endpoint público. La exposición se hará por API Gateway (throttling, autenticación) |
| D23 | **Sin VPC** | Lambda en una VPC | No se necesita red privada. Una Lambda en VPC suele requerir NAT Gateway, que cobra por hora |
| D24 | Execution role **creado por la consola** (solo logs) | Rol escrito a mano | Suficiente para esta etapa. Se reescribirá con CDK aplicando least privilege |
| D25 | Retención de logs: **1 semana** | Sin vencimiento (por defecto) | Evita la acumulación de logs y su costo |

> **Contexto para entrevistas:** el backend es una Lambda en Python 3.14 sobre arm64, con 128 MB y timeout corto. No tiene Function URL ni VPC: se expone solo a través de API Gateway. Su execution role tiene una trust policy que solo permite que Lambda lo asuma, permisos para escribir sus propios logs y, desde la Etapa 6, las 5 acciones del CRUD sobre una sola tabla de DynamoDB. Las credenciales son temporales, emitidas por STS: no hay access keys en el código.

## 4. Configuración realizada

### 4.1 Función

| Opción | Valor |
|---|---|
| Nombre | `cloud-sec-checklist-api` |
| Runtime | Python 3.14 |
| Architecture | arm64 |
| Handler | `handler.lambda_handler` (en esta etapa era `lambda_function.lambda_handler`; cambió en la Etapa 6 al desplegar con zip) |
| Memory | 128 MB |
| Timeout | 3 s |
| Variables de entorno | `TABLE_NAME = cloud-sec-checklist-controls` (desde la Etapa 6) |
| Function URL | ❌ Desactivada |
| VPC | ❌ Ninguna |
| Tags | `Project = cloud-security-checklist` |

### 4.2 Código

Código **al cerrar esta etapa** (commit `6c35796`), escrito en el editor de la consola como `lambda_function.py`. Hoy el backend está separado en 5 módulos de [`backend/`](../backend/) y se despliega como zip: ver [ARCHITECTURE.md](ARCHITECTURE.md#3-backend-confirmado-repo).

```python
import json

def lambda_handler(event, context):

    nombre = event.get("name", None)

    print(event)

    if not nombre:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "El nombre no puede estar vacío."})
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": f"Hola, {nombre}"})
    }
```

| Aspecto | Detalle |
|---|---|
| Entrada | `event` con la clave `name` |
| Salida | Respuesta con formato de API Gateway (`statusCode`, `headers`, `body` como string JSON) |
| Validación | Si `name` falta o está vacío → **400** |
| Logs | Imprime el event recibido (ver la advertencia de seguridad en la sección 8) |
| Caracteres no ASCII | `json.dumps` escapa `í` como `í` por defecto; es JSON válido |

### 4.3 Execution role

**Trust policy:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": { "Service": "lambda.amazonaws.com" },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

**Permissions policy** (de logs, creada por la consola):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "logs:CreateLogGroup",
            "Resource": "arn:aws:logs:us-east-1:<cuenta>:*"
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": [
                "arn:aws:logs:us-east-1:<cuenta>:log-group:/aws/lambda/cloud-sec-checklist-api:*"
            ]
        }
    ]
}
```

| Statement | Acciones | Recurso | Análisis |
|---|---|---|---|
| 1 | `logs:CreateLogGroup` | Cualquier log group de la cuenta en la región | Más amplio de lo necesario (default de AWS). Se ajustará en CDK |
| 2 | `logs:CreateLogStream`, `logs:PutLogEvents` | Solo su propio log group | ✅ Least privilege |

Observaciones:

- **Puede escribir logs, pero no leerlos** (no tiene `logs:GetLogEvents`).
- Al cerrar esta etapa **no tenía permisos de DynamoDB**: cualquier intento recibía `AccessDenied` (deny by default). En la Etapa 6 se provocó ese error a propósito y se agregó la inline policy **`controls-table-crud`** (`Scan`, `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` solo sobre la tabla `cloud-sec-checklist-controls`). Ver [ARCHITECTURE.md](ARCHITECTURE.md#5-iam-quién-le-pide-permiso-a-quién).

### 4.4 Logs

| Configuración | Valor |
|---|---|
| Log group | `/aws/lambda/cloud-sec-checklist-api` (lo crea la Lambda en su primera ejecución) |
| Retención | 1 semana |

## 5. Verificación

### 5.1 Tests desde la consola

| # | Event | Esperado | Resultado |
|---|---|---|---|
| T1 | `{"name": "Facundo"}` | 200 + `{"message": "Hola, Facundo"}` | ✅ |
| T2 | `{"name": ""}` | 400 + mensaje de error | ✅ |
| T3 | `{}` | 400 + mensaje de error | ✅ |

### 5.2 Lectura de la línea `REPORT`

| Métrica | Cold start | Warm start |
|---|---|---|
| Duration | 2,06 ms | 1,76 ms |
| **Init Duration** | **115,85 ms** | — |
| **Billed Duration** | **118 ms** | **2 ms** |
| Memory Size | 128 MB | 128 MB |
| Max Memory Used | 38 MB | 38 MB |

- **Billed Duration = Init Duration + Duration** en un cold start: **la fase de inicialización también se factura**.
- El **Code SHA-256** identifica el código desplegado. Cada Deploy lo cambia y provoca un nuevo cold start.
- **Max Memory Used (38 MB)** confirma que 128 MB es suficiente.

### 5.3 Invocación por CLI (CloudShell)

```text
aws lambda invoke --function-name cloud-sec-checklist-api \
  --cli-binary-format raw-in-base64-out \
  --payload '{"name": "Facundo"}' respuesta.json
cat respuesta.json
```

| Aspecto | Detalle |
|---|---|
| Permiso | `lambda:InvokeFunction` (el mismo que necesitará API Gateway) |
| `--cli-binary-format raw-in-base64-out` | Indica que el payload es JSON plano y no base64 |
| `StatusCode` en pantalla | Estado **de la invocación** (200 = la Lambda se ejecutó) |
| `statusCode` en el archivo | Estado **de la respuesta** que devolvió el código (200 o 400) |

## 6. Debugging: el valor por defecto que ocultaba un error

**Código original:**

```python
nombre = event.get("nombre", "Mundo")
```

| Event | Esperado | Obtenido |
|---|---|---|
| `{}` | 400 | **200 `"Hola, Mundo"`** ❌ |

**Causa:** el segundo argumento de `.get()` es el valor por defecto. Con `"Mundo"`, la variable nunca quedaba vacía y la validación nunca se ejecutaba.

**Por qué no se detectó:** el test de error usó `{"nombre": ""}` en lugar de `{}`. El test pasaba, pero no cubría el caso especificado.

> **Lecciones:**
> - Un valor por defecto no debe ocultar un error que debería reportarse.
> - Un test que pasa solo demuestra que el código funciona **para ese input**. Los tests deben cubrir los casos de la especificación.

## 7. Costos

Según la [página oficial de precios de Lambda](https://aws.amazon.com/lambda/pricing/):

**Free Tier permanente:** 1 M de requests y 400.000 GB-segundos por mes, disponible en el Free plan y en el Paid plan.

```text
GB-segundo = memoria (GB) × segundos de ejecución
128 MB = 0,125 GB
400.000 GB-s ÷ 0,125 GB = 3.200.000 segundos/mes gratis (~37 días de ejecución continua)
```

| Riesgo | Mitigación |
|---|---|
| Logs sin retención | Retención de 1 semana (D25) |
| Recursión infinita (la Lambda dispara un evento que la vuelve a invocar) | Sin triggers que la propia Lambda active |
| **Provisioned concurrency** (cobra por hora aunque no se use) | No activado |
| Timeout largo + código colgado | Timeout de 3 s (D21) |

## 8. Relación con Cloud Security

| Riesgo | Control |
|---|---|
| Rol con permisos excesivos | Execution role con least privilege |
| Credenciales en código o variables de entorno | Credenciales temporales vía STS. Las variables de entorno son visibles para quien pueda leer la configuración de la función |
| Función invocable por cualquiera | Sin Function URL; resource-based policy restringida a la API (Etapa 5) |
| Dependencias vulnerables | Sin dependencias externas (`boto3` viene incluido en el runtime) |
| Input malicioso o inválido | Validación del `event` antes de usarlo |

### 8.1 Impacto de un rol excesivo

Escenario: un bug permite a un atacante ejecutar código arbitrario dentro de la Lambda.

| Rol | Qué podría hacer el atacante |
|---|---|
| Actual (solo logs) | Escribir líneas en su propio log group. Nada más |
| `AdministratorAccess` | **Todo**: leer y borrar datos, borrar buckets, crear usuarios y access keys para mantener el acceso, lanzar recursos que consuman los créditos |

### 8.2 ⚠️ Datos sensibles en los logs

`print(event)` es útil en esta etapa, pero cuando la Lambda reciba requests de API Gateway el event incluirá **todos los headers HTTP**. Con Cognito, eso incluye `Authorization: Bearer <token>`.

| Pregunta | Respuesta |
|---|---|
| ¿Dónde queda el token? | En CloudWatch Logs, durante todo el período de retención |
| ¿Quién puede leerlo? | Cualquier identidad con permisos de lectura de logs (`logs:GetLogEvents`, `logs:FilterLogEvents`) |
| ¿Cómo se evita? | **No registrar el event completo**: loguear solo los campos necesarios (método, path, ID de la request) y nunca headers de autenticación ni datos personales |

> El token **sí** debe viajar en la request (es el mecanismo de autenticación). Lo que no debe hacerse es **persistirlo en los logs**.

Este cambio se aplicará antes de integrar Cognito.

## 9. Cómo revertir esta etapa

| Recurso | ¿Se borra al borrar la función? | Cómo eliminarlo |
|---|---|---|
| Función Lambda | — | Lambda → función → *Actions* → *Delete* |
| Execution role | ❌ No, queda huérfano | IAM → *Roles* → el rol de la función → *Delete* |
| Log group | ❌ No, queda huérfano | CloudWatch → *Log groups* → `/aws/lambda/cloud-sec-checklist-api` → *Delete* |

## 10. Cosas que NO se deben hacer

- ❌ Dar `AdministratorAccess` (o permisos amplios) a un execution role.
- ❌ Guardar access keys en el código o en variables de entorno.
- ❌ Activar una Function URL con `AuthType: NONE`.
- ❌ Activar provisioned concurrency en un proyecto de bajo tráfico.
- ❌ Guardar estado en variables globales esperando que persista.
- ❌ Loguear el event completo cuando contenga tokens o datos personales.
- ❌ Editar el código en el editor de la consola. La fuente de verdad es el repo: se edita en VS Code y se sube el zip (en esta etapa, cuando se editaba en la consola, el error típico era olvidar el **Deploy**).
