# AGENTS.md — Instrucciones para agentes que trabajen en OpenAegis

> Última actualización: 2026-10-24. Este archivo es la **puerta de entrada** para cualquier sesión nueva (Claude Code, Amazon Q u otro agente). Leelo completo antes de proponer cambios.

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

- Proyecto **educativo y de portfolio**. Empezó como **"Cloud Security Checklist"**; el nombre **OpenAegis** se adoptó el 2026-10-12. El **repo de GitHub se llama `openaegis`** y el remoto local ya apunta ahí (2026-10-15). Los recursos de AWS (`cloud-sec-checklist-*`) **siguen usando el nombre viejo**; el `frontend/index.html` ya muestra **OpenAegis**.
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
├── .gitignore                ← secretos, __pycache__, cdk.out/, *.zip, .claude/
├── .gitattributes            ← finales de línea LF en cualquier SO (D78)
├── architecture/
│   ├── architecture.drawio.png       ← diagrama editable (extensión draw.io de VS Code); actualizado al cierre de la Etapa 8
│   └── permissions-flow.drawio.png   ← "quién le pide permiso a quién" (flechas ① a ⑤)
├── backend/                  ← código de la Lambda (Python, sin dependencias externas)
│   ├── handler.py            ← punto de entrada: ROUTES + lambda_handler
│   ├── controls.py           ← lógica de cada ruta de /controls
│   ├── validation.py         ← reglas de un control válido (sin AWS ni HTTP)
│   ├── repository.py         ← ÚNICO módulo que usa boto3 / DynamoDB
│   ├── responses.py          ← formato de entrada/salida de API Gateway (payload 2.0)
│   └── openapi.yaml          ← CONTRATO de la API (OpenAPI 3.1, D69): actualizarlo si cambia el backend
├── docs/
│   ├── 00..09-*.md, 13a-ci-minimo.md  ← un doc por etapa
│   ├── architecture-decisions/  ← ADR-001 a ADR-007 (decisiones grandes)
│   ├── PROJECT_CONTEXT.md · ARCHITECTURE.md · ROADMAP.md · DECISIONS.md · LEARNING_LOG.md
├── frontend/                 ← SPA React + Vite + TS + Cloudscape Design System (D75, teal como acento D76; Etapa 8). Dependencias: D68
│   ├── .npmrc                ← save-exact, ignore-scripts
│   ├── .env.example          ← plantilla de .env.local (ignorado): API_PROXY_TARGET y VITE_COGNITO_* con marcadores
│   ├── vite.config.ts        ← alias @/, proxy de desarrollo /api/ (API_PROXY_TARGET en .env.local) y /openapi.yaml
│   ├── swagger.html          ← Swagger UI SOLO en desarrollo (http://localhost:5173/swagger.html)
│   ├── public/               ← se copia tal cual a dist/: favicon.svg, apple-touch-icon.png
│   └── src/                  ← main.tsx (providers), router.tsx, pages/, components/ (layout, controls), lib/ (api, auth, use-controls, control-rules, theme, brand-theme, notifications, navigation, query-client, config). `lib/auth.ts` es el único que usa `oidc-client-ts`
├── tests/                    ← tests unitarios con unittest (sin AWS): validation, responses, check_identifiers
├── scripts/
│   └── check_identifiers.py  ← falla si un archivo versionado tiene un ID real (cuenta, API, CloudFront, access key)
├── odd/tasks/                ← notas de tareas en formato ODD (Specs / Tasks / Log); su uso como metodología del proyecto está pendiente de decisión
└── .github/workflows/ci.yml  ← job `checks`: tests + chequeo de identificadores (Etapa 13a) + frontend (`npm ci`, typecheck, build, audit; paso 8.6), sin credenciales de AWS
```

Localmente existe `lambda.zip` (artefacto de deploy, ignorado por `.gitignore`). No hay `infra/` todavía (CDK, Etapa 12).

## 4. Qué está implementado y qué falta

| Parte | Estado |
|---|---|
| Cuenta AWS segura + control de costos (Etapa 0) | ✅ [CONVERSACIÓN] |
| S3 privado + CloudFront con OAC (Etapas 2–3) | ✅ [CONVERSACIÓN] — sirve el build de la SPA (paso 8.8, D79); error pages 403/404 → `/index.html` con 200 para las rutas de la SPA (paso 8.7, D67, 2026-10-21) |
| Lambda `cloud-sec-checklist-api` (Etapa 4) | ✅ [CONVERSACIÓN] |
| HTTP API con throttling y CORS (Etapa 5) | ✅ [CONVERSACIÓN] |
| Tabla DynamoDB `cloud-sec-checklist-controls` (Etapa 6) | ✅ [CONVERSACIÓN] |
| `GET /controls`, `GET /controls/{id}`, `POST /controls` | ✅ código [CONFIRMADO-REPO] + pruebas con `curl` [CONVERSACIÓN] |
| `PATCH /controls/{id}` | ✅ código [CONFIRMADO-REPO] + 11 pruebas con `curl` [CONVERSACIÓN, 2026-10-13] |
| `DELETE /controls/{id}` | ✅ código [CONFIRMADO-REPO] + 6 pruebas con `curl` [CONVERSACIÓN] |
| Eliminar `POST /hello` (ruta de prueba) | ✅ código, ruta y statement eliminados (verificado 2026-10-13) |
| IAM auditado (Etapa 7) | ✅ D56–D58 aplicados y verificados (2026-10-15) |
| CI mínimo (Etapa 13a): 42 tests + chequeo de identificadores | ✅ [CONFIRMADO-REPO] + run verde en GitHub (2026-10-15) |
| Job de frontend en el CI (paso 8.6): `npm ci`, typecheck, build, `npm audit` | ✅ [CONFIRMADO-REPO] + PR #5 mergeado con `checks` en verde (2026-10-21) |
| Frontend SPA (React + Vite + TS + Cloudscape, D75/D76) | ✅ código [CONFIRMADO-REPO] — implementado y verificado en local; **desplegado** en CloudFront el 2026-10-21 (paso 8.8, D79) y CRUD verificado en producción (8.9) [CONVERSACIÓN]. **Etapa 8 completa** |
| Cognito (Etapa 9): User Pool con MFA, login en la SPA, JWT authorizer en las 5 rutas | 🟡 casi completa [CONVERSACIÓN, 2026-10-24]: verificado en producción; falta el deploy del PR #13 (`401` → login) y el checkpoint. [docs/09-cognito.md](docs/09-cognito.md) |
| CloudWatch avanzado, checks + findings, CDK, `cdk synth` en CI, tests de `controls.py` | [PENDIENTE] (Etapas 10–16) |

Detalle: [docs/ROADMAP.md](docs/ROADMAP.md).

## 5. Alcance de la V1 (Bloque A)

**Dentro:** CRUD de controles · frontend SPA (React + Vite + TypeScript + Cloudscape, D75/D76; ADR-006) bajo `/app` para ver, crear, editar, eliminar y cambiar estado · landing en `/` recién cuando el producto se pueda instalar (D66) · Cognito · CloudWatch · checks **read-only** con boto3 → findings → score → dashboard · CDK en Python · tests · documentación · demo.

**Fuera de la V1 (no implementar, no "preparar por las dudas"):** Ansible, Terraform, remediación de cualquier tipo, operaciones de escritura sobre recursos evaluados, EventBridge para remediación, workflows de aprobación, infraestructura vulnerable, Docker/ECS/ECR, SQS, FastAPI, OpenTelemetry, IA. **Nunca, salvo un problema real que lo justifique:** EC2, RDS, NAT Gateway, VPC compleja, load balancers, Kubernetes, Kafka, Redis, service mesh, CQRS, event sourcing, microservicios.

**Regla V1 → V2:** si dos opciones son igual de simples, elegir la que facilite la V2; si eso agrega complejidad real, elegir la simple. Mantener separados *Security Check → Finding → Report*. Al terminar la V1: checkpoint **"V1 → V2 Architecture Review"** (ver ROADMAP).

## 6. Tecnologías

| Ahora (V1, implementado) | V1, pendiente | Futuro (Bloque B, a evaluar) |
|---|---|---|
| Python 3.14 (arm64) · AWS Lambda · API Gateway HTTP API (+ JWT authorizer) · DynamoDB · S3 · CloudFront (OAC) · IAM · CloudWatch Logs · boto3 (incluido en el runtime) · Cognito User Pool · SPA React + Vite + TypeScript + Cloudscape + `oidc-client-ts` | CloudWatch métricas/alarmas · checks con boto3 · AWS CDK (Python) · GitHub Actions (alcance por decidir) · moto [PROPUESTA] | Docker · Terraform · ECR · ECS/Fargate · FastAPI · OIDC · OpenTelemetry/X-Ray · SQS · Ansible · Trivy/Bandit/Semgrep/Checkov/ansible-lint · IA para explicar findings · k6 |

## 7. Cómo desplegar y probar (solo lo verificado)

> ⚠️ Hoy **no hay IaC**: toda la infraestructura se creó a mano en la consola. El único despliegue que existe es el del **código** de la Lambda.

**Entorno del usuario:** Windows + PowerShell + VS Code. La CLI de AWS se usa **solo desde AWS CloudShell** (credenciales temporales de la sesión de consola). **El usuario no tiene access keys** (D4), así que **un agente local no puede ejecutar comandos de AWS**: se le proponen al usuario para que los corra en CloudShell.

**Deploy del backend** (la fuente de verdad es el repo; **no editar el código en la consola de Lambda**):

```powershell
# Desde la raíz del repo. Los .py tienen que quedar en la RAÍZ del zip.
Compress-Archive -Path backend\*.py -DestinationPath lambda.zip -Force
```

Después: consola → Lambda `cloud-sec-checklist-api` → **Code → Upload from → .zip file** → Save. Handler configurado: **`handler.lambda_handler`** (se configura una sola vez). Variable de entorno: `TABLE_NAME=cloud-sec-checklist-controls`.

**Pruebas** (desde CloudShell). Desde la Etapa 9 la API exige un **access token** (sin token: `401`). Se copia de la SPA logueada (F12 → Console: `copy(JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(k => k.startsWith("oidc.user")))).access_token)`) y se carga con `read -rs`, para que no quede en pantalla ni en el historial. **Nunca pegar tokens en el chat.** Dura 1 hora.

```bash
APIID=$(aws apigatewayv2 get-apis --query "Items[?Name=='cloud-sec-checklist-http-api'].ApiId" --output text)
API=https://$APIID.execute-api.us-east-1.amazonaws.com
read -rs ACCESS && echo "cargado (${#ACCESS} caracteres)"
AUTH="Authorization: Bearer $ACCESS"
curl -i $API/controls                      # 401 sin token
curl -i $API/controls -H "$AUTH"
curl -i $API/controls/<id> -H "$AUTH"    # reemplazar <id> entero: en bash < y > son redirecciones
curl -i -X POST  $API/controls -H "$AUTH" -H "Content-Type: application/json" -d '{"code":"X-1","title":"T","service":"S3","category":"Data protection","severity":"LOW"}'
curl -i -X PATCH $API/controls/<id> -H "$AUTH" -H "Content-Type: application/json" -d '{"status":"FAIL"}'
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

**Frontend** (los comandos de `npm` se corren en **PowerShell**, nunca en WSL: `node_modules` tiene binarios nativos de Windows y desde WSL falla con `typescript-linux-x64`; y **dentro de `frontend/`**, donde está el `package.json`; desde la raíz dan `ENOENT`, o se usa `npm --prefix frontend run dev`):

```powershell
cd frontend
npm run dev        # http://localhost:5173 (la app) y /swagger.html (contrato); requiere frontend/.env.local con API_PROXY_TARGET y las 3 VITE_COGNITO_* (ver .env.example)
npm run build      # verifica tipos y compila a frontend/dist/
```

**Tests y chequeos locales** (desde la **raíz**; son los mismos que corre el CI en cada push):

```powershell
python -m unittest discover -s tests -v
python scripts/check_identifiers.py
```

Cubren `validation.py`, `responses.py` y el propio chequeo. `controls.py` todavía no se testea: importar `repository.py` requiere `TABLE_NAME` y boto3 (Etapa 14).

## 8. Reglas de seguridad y de trabajo (obligatorias)

1. **Git primero.** `git status` y leer el archivo **antes** de escribirlo. **No sobrescribir trabajo del usuario**: el usuario suele escribir código al mismo tiempo (ya hubo un incidente, ver LEARNING_LOG). Si un archivo cambió y no está commiteado, preguntar.
2. **No confundir planificado con implementado.** No inventar pruebas, despliegues, resultados ni decisiones. Usar las marcas de estado.
3. **No implementar funcionalidades durante una tarea de documentación**, y viceversa: no mezclar refactor con funcionalidad nueva en un mismo commit.
4. **AWS:** no desplegar, modificar ni destruir recursos, ni generar gastos, sin autorización explícita. **Advertir el costo antes** de crear cualquier recurso y **verificar precios y Free Tier en la documentación oficial**. Nunca asumir que algo es gratis.
5. ⚠️ **Free plan:** crear una **AWS Organization**, activar **IAM Identity Center** o **Control Tower**, o hacer clic en *upgrade plan* **pasa la cuenta al Paid plan y hace vencer los créditos**. Nunca sugerirlo sin advertirlo.
6. **Secretos e identificadores:** nunca escribir en el repo el ID de cuenta, el ID de la API, el dominio de CloudFront, el sufijo del bucket, el nombre del IAM user, IDs de distribución ni emails. Usar `<cuenta>`, `<api-id>`, `<distribucion>`, `<sufijo>`, `<admin-user>`, `<distribution-id>` y, desde la Etapa 9, `<user-pool-id>`, `<client-id>`, `<dominio-cognito>`. **Nunca** pedir ni aceptar tokens de Cognito o un `code` en el chat: para probar, `read -rs`. **Recordarle al usuario** que tape esos datos cuando pega salidas.
7. **`main` está protegida (D74): todo cambio va en una rama `tipo/descripcion` y entra por PR con el check `checks` en verde.** Antes de escribir, `git switch -c <rama>` desde `main` actualizada. **Commits, pushes y cambios destructivos solo a pedido explícito.** Mensajes en español, estilo `tipo(ámbito): descripción` (ver `git log`), con la atribución que indique el entorno.
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
- **Cada decisión nueva** se agrega a [docs/DECISIONS.md](docs/DECISIONS.md) con el siguiente número libre (hoy: **D84**), y al doc de su etapa.
- **ADRs** (`docs/architecture-decisions/NNN-tema.md`, D55): solo para decisiones **grandes**; `DECISIONS.md` es el índice de todas. Formato: Contexto, Decisión, Por qué, Alternativas consideradas, Ventajas, Desventajas, Consideraciones de seguridad, Consideraciones de costo, Consecuencias, Evolución futura (más estado, fecha y decisiones relacionadas). Existen ADR-001 a ADR-007; el siguiente es **008**. Al crear uno, agregarlo a la tabla de `DECISIONS.md`.
- **README:** contar la evolución, con ventajas **y desventajas**; **solo lo implementado**.
- Actualizar ROADMAP y ARCHITECTURE cuando algo cambie de estado.

## 11. Memoria y forma de trabajo (tenet)

- **Memoria persistente: Engram** (decidido el 2026-10-14). Proyecto en Engram: **`openaegis`**, fijado en `.engram/config.json` (2026-10-15). Las memorias anteriores siguen bajo `aws-cloud-security-checklist` (no se borran ni se unifican sin aprobación). Al empezar una sesión: `mem_current_project` + `mem_search` del tema. Se guardan **solo** hechos que no están en el repo (preferencias de enseñanza, restricciones de la cuenta, resumen de cada sesión). Las decisiones técnicas viven en `docs/DECISIONS.md`, que es la fuente de verdad.
- **OpenSpec: no se usa por ahora**; se reevalúa en la revisión V1 → V2. Cada cambio declara igual su alcance y sus criterios de aceptación (el "Esperado" de cada paso).
- Excepciones a los valores por defecto de tenet, con motivo: docs en **español** (convención del proyecto) e IaC con **AWS CDK** en la V1 (la comparación con Terraform es parte del Bloque B).
