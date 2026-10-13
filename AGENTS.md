# AGENTS.md — Instrucciones para agentes que trabajen en OpenAegis

> Última actualización: 2026-10-12. Este archivo es la **puerta de entrada** para cualquier sesión nueva (Claude Code, Amazon Q u otro agente). Leelo completo antes de proponer cambios.

Convenciones de estado usadas en toda la documentación:

| Marca | Significado |
|---|---|
| **[CONFIRMADO-REPO]** | Verificado leyendo el repositorio |
| **[CONVERSACIÓN]** | Surge del historial de trabajo con el usuario; **no** verificado contra AWS (los recursos se crearon a mano en la consola) |
| **[PENDIENTE]** | No hecho, o sin evidencia de que se haya hecho |
| **[INCIERTO]** | Dato dudoso o contradictorio: verificar antes de usarlo |
| **[PROPUESTA]** | Idea discutida, **no** decisión tomada |

---

## 1. Qué es OpenAegis

Aplicación web **serverless en AWS** para **gestionar controles de seguridad cloud** (S3 Block Public Access, cifrado de S3, CloudTrail habilitado, MFA, permisos, logging…) y, más adelante, **ejecutar checks automáticos de solo lectura** con boto3 que generen **findings**.

- Proyecto **educativo y de portfolio**. Empezó como **"Cloud Security Checklist"**; el nombre **OpenAegis** se adoptó el 2026-10-12. Los recursos de AWS, el remoto de GitHub (`aws-cloud-security-checklist`) y el `frontend/index.html` **siguen usando el nombre viejo**.
- **No** compite con Prowler, ScoutSuite, Wiz ni Prisma Cloud, y **no** debe presentarse como algo que garantiza la seguridad de una cuenta.
- **Modelo de despliegue (V1):** self-hosted y single-account. Cada usuario despliega su copia en **su** cuenta y la app evalúa **esa** cuenta. Ver [docs/DECISIONS.md](docs/DECISIONS.md) (D48).

Contexto completo (origen, objetivos, perfil del usuario): [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md).

## 2. Qué leer primero en una sesión nueva

1. Este archivo.
2. [docs/ROADMAP.md](docs/ROADMAP.md): en qué etapa estamos y qué sigue.
3. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): qué existe realmente (código y AWS).
4. [docs/DECISIONS.md](docs/DECISIONS.md): decisiones tomadas, propuestas y **preguntas abiertas**.
5. El doc de la etapa en curso o de la anterior (`docs/0N-*.md`).
6. [docs/LEARNING_LOG.md](docs/LEARNING_LOG.md): qué conceptos ya se enseñaron (no repetirlos desde cero; sí reforzarlos).
7. `git status` y `git log --oneline -10`.

## 3. Estructura del repositorio [CONFIRMADO-REPO]

```text
openaegis/
├── AGENTS.md                 ← este archivo
├── README.md                 ← presentación pública (solo lo implementado)
├── LICENSE                   ← MIT
├── .gitignore                ← secretos, __pycache__, cdk.out/, *.zip
├── architecture/
│   ├── architecture.drawio.png       ← diagrama editable (extensión draw.io de VS Code). ⚠️ desactualizado: muestra API Gateway y DynamoDB como "planificados"
│   └── permissions-flow.drawio.png   ← "quién le pide permiso a quién" (flechas ① a ⑤)
├── backend/                  ← código de la Lambda (Python, sin dependencias externas)
│   ├── handler.py            ← punto de entrada: ROUTES + lambda_handler
│   ├── controls.py           ← lógica de cada ruta de /controls
│   ├── validation.py         ← reglas de un control válido (sin AWS ni HTTP)
│   ├── repository.py         ← ÚNICO módulo que usa boto3 / DynamoDB
│   └── responses.py          ← formato de entrada/salida de API Gateway (payload 2.0)
├── docs/
│   ├── 00..05-*.md           ← un doc por etapa (decisiones D1–D31)
│   ├── PROJECT_CONTEXT.md · ARCHITECTURE.md · ROADMAP.md · DECISIONS.md · LEARNING_LOG.md
└── frontend/
    └── index.html            ← solo un <h1> de prueba
```

Localmente existe `lambda.zip` (artefacto de deploy, ignorado por `.gitignore`). No hay `tests/`, `infra/` ni `.github/` todavía.

## 4. Qué está implementado y qué falta

| Parte | Estado |
|---|---|
| Cuenta AWS segura + control de costos (Etapa 0) | ✅ [CONVERSACIÓN] |
| S3 privado + CloudFront con OAC (Etapas 2–3) | ✅ [CONVERSACIÓN] — sirve un `index.html` de prueba |
| Lambda `cloud-sec-checklist-api` (Etapa 4) | ✅ [CONVERSACIÓN] |
| HTTP API con throttling y CORS (Etapa 5) | ✅ [CONVERSACIÓN] |
| Tabla DynamoDB `cloud-sec-checklist-controls` (Etapa 6) | ✅ [CONVERSACIÓN] |
| `GET /controls`, `GET /controls/{id}`, `POST /controls` | ✅ código [CONFIRMADO-REPO] + pruebas con `curl` [CONVERSACIÓN] |
| `PATCH /controls/{id}` | ✅ código [CONFIRMADO-REPO] + 11 pruebas con `curl` [CONVERSACIÓN, 2026-10-13] |
| `DELETE /controls/{id}` | ✅ código [CONFIRMADO-REPO, sin commitear al 2026-10-13] + 6 pruebas con `curl` [CONVERSACIÓN] |
| Eliminar `POST /hello` (ruta de prueba) | [PENDIENTE] |
| Frontend real, Cognito, CloudWatch avanzado, checks + findings, CDK, CI, tests | [PENDIENTE] (Etapas 7–16) |

Detalle: [docs/ROADMAP.md](docs/ROADMAP.md).

## 5. Alcance de la V1 (Bloque A)

**Dentro:** CRUD de controles · frontend simple (HTML/CSS/JS) para ver, crear, editar, eliminar y cambiar estado · Cognito · CloudWatch · checks **read-only** con boto3 → findings → score → dashboard · CDK en Python · tests · documentación · demo.

**Fuera de la V1 (no implementar, no "preparar por las dudas"):** Ansible, Terraform, remediación de cualquier tipo, operaciones de escritura sobre recursos evaluados, EventBridge para remediación, workflows de aprobación, infraestructura vulnerable, Docker/ECS/ECR, SQS, FastAPI, OpenTelemetry, IA. **Nunca, salvo un problema real que lo justifique:** EC2, RDS, NAT Gateway, VPC compleja, load balancers, Kubernetes, Kafka, Redis, service mesh, CQRS, event sourcing, microservicios.

**Regla V1 → V2:** si dos opciones son igual de simples, elegir la que facilite la V2; si eso agrega complejidad real, elegir la simple. Mantener separados *Security Check → Finding → Report*. Al terminar la V1: checkpoint **"V1 → V2 Architecture Review"** (ver ROADMAP).

## 6. Tecnologías

| Ahora (V1, implementado) | V1, pendiente | Futuro (Bloque B, a evaluar) |
|---|---|---|
| Python 3.14 (arm64) · AWS Lambda · API Gateway HTTP API · DynamoDB · S3 · CloudFront (OAC) · IAM · CloudWatch Logs · boto3 (incluido en el runtime) | Cognito · CloudWatch métricas/alarmas · checks con boto3 · AWS CDK (Python) · GitHub Actions (alcance por decidir) · moto [PROPUESTA] | Docker · Terraform · ECR · ECS/Fargate · FastAPI · OIDC · OpenTelemetry/X-Ray · SQS · Ansible · Trivy/Bandit/Semgrep/Checkov/ansible-lint · IA para explicar findings · k6 |

## 7. Cómo desplegar y probar (solo lo verificado)

> ⚠️ Hoy **no hay IaC**: toda la infraestructura se creó a mano en la consola. El único despliegue que existe es el del **código** de la Lambda.

**Entorno del usuario:** Windows + PowerShell + VS Code. La CLI de AWS se usa **solo desde AWS CloudShell** (credenciales temporales de la sesión de consola). **El usuario no tiene access keys** (D4), así que **un agente local no puede ejecutar comandos de AWS**: se le proponen al usuario para que los corra en CloudShell.

**Deploy del backend** (la fuente de verdad es el repo; **no editar el código en la consola de Lambda**):

```powershell
# Desde la raíz del repo. Los .py tienen que quedar en la RAÍZ del zip.
Compress-Archive -Path backend\*.py -DestinationPath lambda.zip -Force
```

Después: consola → Lambda `cloud-sec-checklist-api` → **Code → Upload from → .zip file** → Save. Handler configurado: **`handler.lambda_handler`** (se configura una sola vez). Variable de entorno: `TABLE_NAME=cloud-sec-checklist-controls`.

**Pruebas** (desde CloudShell; reemplazar los marcadores, que en bash `<` y `>` son redirecciones):

```bash
API=https://<api-id>.execute-api.us-east-1.amazonaws.com
curl -i $API/controls
curl -i $API/controls/<id>
curl -i -X POST  $API/controls -H "Content-Type: application/json" -d '{"code":"X-1","title":"T","service":"S3","category":"Data protection","severity":"LOW"}'
curl -i -X PATCH $API/controls/<id> -H "Content-Type: application/json" -d '{"status":"FAIL"}'
```

**Logs** (todos los streams):

```bash
aws logs tail /aws/lambda/cloud-sec-checklist-api --since 10m --follow
aws logs tail /aws/lambda/cloud-sec-checklist-api --since 1h --filter-pattern ERROR
```

**Verificar el estado real de AWS (solo lectura, para que lo corra el usuario):**

```bash
aws dynamodb describe-table --table-name cloud-sec-checklist-controls
aws apigatewayv2 get-routes --api-id <api-id>
aws apigatewayv2 get-stage  --api-id <api-id> --stage-name '$default'
aws lambda get-function-configuration --function-name cloud-sec-checklist-api
aws lambda get-policy --function-name cloud-sec-checklist-api
```

No hay tests automatizados todavía (Etapa 14).

## 8. Reglas de seguridad y de trabajo (obligatorias)

1. **Git primero.** `git status` y leer el archivo **antes** de escribirlo. **No sobrescribir trabajo del usuario**: el usuario suele escribir código al mismo tiempo (ya hubo un incidente, ver LEARNING_LOG). Si un archivo cambió y no está commiteado, preguntar.
2. **No confundir planificado con implementado.** No inventar pruebas, despliegues, resultados ni decisiones. Usar las marcas de estado.
3. **No implementar funcionalidades durante una tarea de documentación**, y viceversa: no mezclar refactor con funcionalidad nueva en un mismo commit.
4. **AWS:** no desplegar, modificar ni destruir recursos, ni generar gastos, sin autorización explícita. **Advertir el costo antes** de crear cualquier recurso y **verificar precios y Free Tier en la documentación oficial**. Nunca asumir que algo es gratis.
5. ⚠️ **Free plan:** crear una **AWS Organization**, activar **IAM Identity Center** o **Control Tower**, o hacer clic en *upgrade plan* **pasa la cuenta al Paid plan y hace vencer los créditos**. Nunca sugerirlo sin advertirlo.
6. **Secretos e identificadores:** nunca escribir en el repo el ID de cuenta, el ID de la API, el dominio de CloudFront, el sufijo del bucket, el nombre del IAM user, IDs de distribución ni emails. Usar `<cuenta>`, `<api-id>`, `<distribucion>`, `<sufijo>`, `<admin-user>`, `<distribution-id>`. **Recordarle al usuario** que tape esos datos cuando pega salidas.
7. **Commits, pushes y cambios destructivos solo a pedido explícito.** Mensajes en español, estilo `tipo(ámbito): descripción` (ver `git log`), con la atribución que indique el entorno.
8. **Least privilege** en cada permiso nuevo: acciones concretas sobre ARNs concretos. Los checks de la V1 son **read-only**.
9. **Código:** Python simple, sin frameworks ni dependencias salvo que resuelvan un problema real. `validation.py` no importa AWS ni HTTP; `repository.py` es el único que importa boto3. Atrapar **solo** las excepciones que se saben manejar (nada de `except Exception`).

## 9. Cómo enseñar (el usuario lo exige)

El usuario pidió un **tutor técnico exigente, no un generador de código**. Responder en **español rioplatense (voseo)**.

1. **Explicación primero:** qué, por qué, servicio, alternativas, costo, riesgos y relación con seguridad. Analogías con backend/APIs/bases de datos (el usuario es desarrollador backend, nuevo en AWS).
2. **Varias opciones con una recomendación justificada**, y **pasos concretos** (dónde está cada opción en la consola, qué configura, cuál es segura, qué cuesta, cómo verificar, cómo eliminar).
3. **Después, preguntas**: solo sobre lo explicado, **una idea por pregunta**, con **escenarios concretos** (a veces con opciones a/b/c). Evitar preguntas abstractas o compuestas.
4. **Corrección:** si la respuesta está mal, primero una **pista** y otra oportunidad; si sigue mal, explicar. Si el usuario dice "no sé, decime", explicarlo directamente.
5. **Implementación incremental:** antes de cada archivo, qué es, para qué sirve, qué entra, qué sale y cómo se relaciona con AWS. Nada de archivos de 200 líneas sin que se entiendan. Dejarlo intentar primero.
6. **Comandos de CLI:** qué hace, qué servicio, qué permiso necesita, resultado esperado, cómo verificar, cómo revertir.
7. **Debugging con método:** qué esperábamos → qué pasó → hipótesis → evidencia (comando/log/configuración) → análisis → prueba → solución → por qué pasó. Nunca "cambiá X por Y".
8. **Checkpoint al final de cada etapa** (CONCEPTO / ARQUITECTURA / SEGURIDAD / COSTOS / PRÁCTICA / VERIFICACIÓN) + 3 a 5 preguntas.
9. Ante alternativas arquitectónicas: **presentarlas y preguntar**. Si dice "decime vos", recomendar con justificación. Si dice "hacelo vos" (docs, correcciones puntuales), hacerlo y explicar qué se hizo.
10. Le gustan las **tablas y los diagramas ASCII**. A menudo pide **reenviar la explicación de la etapa en curso** después de una desviación: hacerlo.
11. **Nunca priorizar terminar rápido sobre que entienda.** Principio de evolución: *problema → requisito → alternativas → trade-offs → decisión → implementación → testing → observación → documentación*.

## 10. Cómo documentar

- **Un doc por etapa** en `docs/NN-tema.md`, con la estructura de los existentes: objetivo, conceptos, decisiones (`D#`), configuración, verificación, debugging, costos, relación con Cloud Security, cómo revertir, cosas que NO hacer. Con marcadores en lugar de identificadores reales.
- **Cada decisión nueva** se agrega a [docs/DECISIONS.md](docs/DECISIONS.md) con el siguiente número libre (hoy: **D55**), y al doc de su etapa.
- **ADRs** (`docs/architecture-decisions/NNN-*.md`, formato *Context, Decision, Why, Alternatives considered, Advantages, Disadvantages, Security considerations, Cost considerations, Consequences, Future evolution*): acordados, **todavía no creados**. Antes de crear la carpeta, confirmar con el usuario cómo convive con `DECISIONS.md` (ver preguntas abiertas).
- **README:** contar la evolución, con ventajas **y desventajas**; **solo lo implementado**.
- Actualizar ROADMAP y ARCHITECTURE cuando algo cambie de estado.
