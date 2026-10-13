# Roadmap

> Estado al 2026-10-12. **Regla absoluta: terminar la V1 (Bloque A) antes de empezar cualquier cosa del Bloque B.**
> El Bloque B es una **visión**, no un plan cerrado: cada tecnología se agrega solo si resuelve un problema real (*problema → requisito → alternativas → trade-offs → decisión → implementación → testing → observación → documentación*).

## Bloque A — V1: Cloud Security Checklist / Assessment (read-only)

```text
AWS Foundation → Application → Backend → Database → Security Checks → Findings → Dashboard → Testing → Security → Documentation → V1 COMPLETE
```

Funcionalidades objetivo de la V1: **Dashboard, Security Checks, Security Findings, Security Score, Security Scan, Finding Details**. El frontend tiene que permitir ver, crear, editar, eliminar y cambiar el estado de los controles, y ejecutar los checks.

### Etapas

Orden original 0–16. **Cambio acordado:** Lambda pasó a ser la Etapa 4 y API Gateway la 5, porque API Gateway necesita algo a quién invocar.

| Etapa | Contenido | Estado | Doc |
|---|---|---|---|
| 0 | Cuenta segura + control de costos | ✅ | [00-account-setup.md](00-account-setup.md) |
| 1 | Fundamentos Cloud/AWS | ✅ (conceptual) | [01-cloud-fundamentals.md](01-cloud-fundamentals.md) |
| 2 | S3 | ✅ | [02-s3.md](02-s3.md) |
| 3 | CloudFront | ✅ | [03-cloudfront.md](03-cloudfront.md) |
| 4 | Lambda + Python | ✅ | [04-lambda.md](04-lambda.md) |
| 5 | API Gateway (HTTP API) | ✅ | [05-api-gateway.md](05-api-gateway.md) |
| 6 | DynamoDB + CRUD de controles | ✅ (2026-10-13) | [06-dynamodb.md](06-dynamodb.md) |
| **7** | **IAM (least privilege real)** | ⏳ **SIGUIENTE** (parcial: se aplica en cada etapa) | — |
| 8 | Integración: frontend real contra la API | [PENDIENTE] | — |
| 9 | Cognito (autenticación; autorizador JWT del HTTP API) | [PENDIENTE] | — |
| 10 | CloudWatch: métricas, alarmas, debugging, manejo de errores centralizado | [PENDIENTE] | — |
| 11 | boto3 + Security Checks read-only → findings → score → dashboard | [PENDIENTE] | — |
| 12 | AWS CDK (Python): toda la infraestructura como código; habilita el modelo self-hosted | [PENDIENTE] | — |
| 13 | GitHub Actions / CI | [PENDIENTE] — **alcance por decidir** (ver abajo) | — |
| 14 | Testing | [PENDIENTE] | — |
| 15 | Documentación: README completo y ADRs | [PENDIENTE] (se avanza en cada etapa) | — |
| 16 | Demo + LinkedIn + GitHub | [PENDIENTE] | — |

### Tareas para cerrar la V1, en orden

**Etapa 6 ✅ (quedan los pendientes 7 y 8, que no bloquean la Etapa 7)**

1. ✅ **Pruebas del `PATCH /controls/{id}` completas** [CONVERSACIÓN, 2026-10-13]: `{"status":"FAIL"}` → 200 (`updated_at` cambia, `created_at` no) · `{"title":""}` y `{"title":"   "}` → 400 · id inexistente → 404 **sin crear item** (`count` siguió en 4) · `abc` → 400 · `{}`, `{"admin":true}`, `{"created_at":...}` → 400 · `code` de otro control → 409 · su propio `code` → 200 · varios campos → 200. La predicción del handler quedó respondida (ver LEARNING_LOG).
2. **Commit** de la documentación pendiente (el código del `PATCH` ya está en `e5dbabf`).
3. **Implementar `DELETE /controls/{id}`** (`DeleteItem`; como todavía no existen findings, borra directo; con findings será 409, D40). Ruta en API Gateway + verificar el statement en la resource-based policy. **Primera prueba: borrar uno de los dos `S3-002` duplicados** (dejados a propósito). Decidido: 404 si no existe y 200 + item borrado (D53, D54). ✅ Desplegado y verificado el 2026-10-13: borrar el duplicado → 200 con el item; GET y DELETE del mismo id → 404; `count` 4 → 3; `abc` → 400; id inexistente → 404; el log registra el `code` borrado.
4. ✅ **Eliminar `POST /hello`** (2026-10-13): código (`ROUTES` y `controls.hello`), ruta en API Gateway y statement de la resource-based policy. Verificado: `POST /hello` → 404 de API Gateway, `get-routes` muestra solo las 5 rutas del CRUD, `get-policy` muestra 2 statements. CORS verificado en la misma sesión.
5. ✅ **Checkpoint de la Etapa 6** (2026-10-13): 5/5 respuestas correctas.
6. ✅ **[`docs/06-dynamodb.md`](06-dynamodb.md)** escrito (decisiones D32–D54).
7. **Primeros ADRs** (serverless, S3 + CloudFront, HTTP API, DynamoDB, modelo de despliegue), después de acordar con el usuario cómo conviven con `DECISIONS.md`.
8. **Actualizar** [architecture/architecture.drawio.png](../architecture/architecture.drawio.png) (API Gateway y DynamoDB ya no son "planificados").

**Etapas 7 a 16**

9. Etapa 7 — revisar IAM de punta a punta (rol de la Lambda, resource-based policies, bucket policy) y cerrar lo que quedó amplio.
10. Etapa 8 — frontend real (HTML/CSS/JS simple) que consuma la API: listar, crear, editar, eliminar, cambiar estado.
11. Etapa 9 — Cognito User Pool + autorizador JWT en el HTTP API.
12. Etapa 10 — CloudWatch: métricas (*Errors*, *Throttles*, *Duration*), alarmas (verificar costo), manejo de errores centralizado, logs estructurados.
13. Etapa 11 — checks read-only con boto3 (empezar por S3 Block Public Access, S3 Encryption, CloudTrail habilitado) → tabla de findings → score → dashboard. Diseñar la tabla de findings (requisito: consultar por `control_id` de forma eficiente). Decidir `SecurityAudit` vs. policy propia. Decidir qué regiones evalúa cada check.
14. Etapa 12 — CDK en Python: recrear todo como código, borrar los recursos manuales (deletion protection de la tabla está desactivado para esto), `cdk synth / deploy / destroy`.
15. Etapa 13 — CI según la opción que elija el usuario.
16. Etapa 14 — tests (unitarios de `validation.py` sin AWS; `controls.py` con un repositorio falso; moto [PROPUESTA]).
17. Etapa 15 — README completo, ADRs, lecciones aprendidas.
18. Etapa 16 — demo (Deploy → Test → Demo/screenshots/video → Destroy → Verify), publicación de LinkedIn **factual**.

### Decisión pendiente: alcance de la Etapa 13

El prompt original pone GitHub Actions + CI/CD + OIDC **en la V1**; el documento de evolución pone CI/CD y OIDC **en el Bloque B**.

| Opción | Qué incluye la V1 |
|---|---|
| **A (recomendada)** | CI mínimo: tests + `cdk synth` en cada push, **sin deploy y sin credenciales de AWS**. OIDC y deploy automático, en el Bloque B |
| B | Todo al Bloque B; la V1 se despliega a mano con `cdk deploy` |

[INCIERTO] El usuario todavía no eligió. Hay que decidirlo antes de la Etapa 13.

### Checkpoint final: "V1 → V2 Architecture Review"

Al completar la V1, antes de cualquier trabajo del Bloque B: (1) arquitectura final de la V1, (2) qué se aprendió, (3) security checks existentes, (4) modelo de findings, (5) IAM, (6) CDK, (7) GitHub Actions, (8) costos, (9) documentación, (10) qué se reutiliza, (11) qué tiene que evolucionar, (12) diseño de la arquitectura V2. Temas a evaluar en esa revisión: **multi-cuenta** (cross-account roles con ExternalId; ⚠️ lo habitual es con AWS Organizations, que en el Free plan haría perder los créditos), **SaaS multi-tenant** (solo con un motivo real) y una **CLI** que reutilice los checks [PROPUESTA].

---

## Bloque B — Evolución Cloud / DevSecOps (NO implementar todavía)

Orden propuesto por el usuario (puede cambiar con justificación técnica):

```text
Docker → Terraform → ECR → ECS/Fargate → CI/CD → OIDC → Observability → SQS → Security Automation → Ansible → DevSecOps → AI → Performance → Final Architecture
```

| Tema | Notas |
|---|---|
| Docker | Dockerfile, imágenes, Compose, healthchecks, multi-stage. Objetivo: entender cómo cambia el modelo de despliegue de serverless a containers |
| Terraform | **No reemplazar CDK automáticamente.** Comparar CDK vs. Terraform primero. Hipótesis (no decidida): CDK para la app, Terraform para un *security lab* |
| ECR + ECS/Fargate (+ ALB) | Etapa explícita de comparación **Lambda vs. ECS** (tráfico, costo, cold starts, duración, escalabilidad, operación, deploy, observabilidad, seguridad, complejidad). **La migración no es obligatoria** |
| FastAPI | Si se migra a containers. Gracias a la separación en módulos, debería cambiar solo `handler.py` (D46) |
| CI/CD con GitHub Actions | Tests, security scans, build, deploy. Explicar cada paso; nada de workflows enormes sin explicar |
| OIDC | GitHub Actions → OIDC → STS → rol IAM → credenciales temporales. Explicar JWT, trust policy y least privilege antes |
| Observabilidad | CloudWatch → logs, métricas, trazas, OpenTelemetry, X-Ray, alertas. Primero el problema de observabilidad, después la herramienta |
| SQS | **Solo** si aparece una operación que necesite desacoplamiento. Retries, visibility timeout, DLQ, idempotencia |
| Eventos de seguridad | CloudTrail → EventBridge → evaluación → finding (→ remediación en V2) |
| V2: remediación | Detection → Classification → Remediation Policy (**SAFE** automático / **REVIEW** con aprobación / **MANUAL** solo recomendación) → Ansible → AWS → Re-scan → Validation → Monitoring/Audit. **Nunca "auto-fix everything".** Pasar de read-only a escritura es un cambio de seguridad mayor: least privilege, blast radius, credenciales temporales, aprobación, audit trail, idempotencia, rollback, dry-run, aislamiento de entornos, scoping de recursos, logging |
| DevSecOps | Trivy, Bandit, Semgrep, Checkov, ansible-lint, escaneo de imágenes: evaluar **una por una** (qué detecta, dónde corre, costo, alternativas) |
| IA | Pequeña: explicar findings. **La IA nunca es la fuente de verdad**: lo son las APIs de AWS y los checks deterministas |
| Performance | k6: throughput, latencia, tasa de error, comportamiento bajo carga |
| Testing de integración | Floci (emulador de AWS open source, alternativa a LocalStack) como candidato [PROPUESTA]. Ojo: no aplica IAM por defecto y requiere montar el socket de Docker |
| GuardDuty | [INCIERTO] No se discutió en el trabajo con el usuario; apareció recién en el pedido de transferencia de contexto. **Idea a evaluar** (costo y disponibilidad en el Free plan), no parte del plan |

Estructura de repo posible después de la V2 (**no implementarla ahora**; debe surgir de necesidades reales): `backend/checks/`, `backend/findings/`, `infrastructure/cdk/`, `terraform/security-lab/`, `ansible/`, `docs/v1/`, `docs/v2/`, `.github/workflows/`.

**Prohibido sumar por "parecer enterprise":** Kubernetes, Kafka, Redis, service mesh, CQRS, event sourcing, microservicios.

### Cómo debería contarse la evolución

> **V1:** construí una aplicación serverless de Cloud Security capaz de evaluar configuraciones de AWS mediante checks read-only y generar findings.
> **V2:** la evolucioné hacia un flujo DevSecOps capaz de detectar findings, evaluar políticas de remediación, ejecutar automatizaciones controladas, validar nuevamente el estado del recurso y registrar el resultado.

La evolución tiene que mostrar crecimiento técnico real, no cantidad de tecnologías.
