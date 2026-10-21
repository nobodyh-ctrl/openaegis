# Contexto del proyecto

> Reconstruido el 2026-10-12 a partir del historial de trabajo (2026-09-29 a 2026-10-12), las especificaciones originales del usuario y el repositorio.

## 1. Origen

El proyecto nació el **2026-09-29** como **"Cloud Security Checklist"**: un proyecto **educativo y de portfolio** para aprender AWS, Cloud y Cloud Security construyendo una aplicación real, con un asistente en rol de **tutor técnico exigente** (no generador de código).

El nombre **OpenAegis** se adoptó el **2026-10-12**, al renombrar la sesión de trabajo y la carpeta local (`C:\AWS\aws-cloud-security-checklist` → `C:\AWS\openaegis`). Los recursos de AWS (`cloud-sec-checklist-*`) y el tag `Project` siguen con el nombre anterior; el remoto de GitHub (`openaegis`) y el `frontend/index.html` ya usan el nombre nuevo (remoto actualizado el 2026-10-15).

## 2. Qué problema busca resolver

Gestionar una lista de **controles de seguridad cloud** (qué debería cumplirse: S3 Block Public Access, cifrado, CloudTrail, MFA, permisos, logging…) y, en una etapa posterior, **evaluar automáticamente** la cuenta de AWS donde está desplegada con **checks de solo lectura**, generando **findings** comprensibles y accionables, un score y un dashboard.

Límites explícitos:

- **No** compite con Prowler, ScoutSuite, Wiz ni Prisma Cloud. No es un scanner completo.
- **No** garantiza la seguridad de una cuenta.
- La V1 **no modifica** recursos de AWS: solo observa y evalúa.

| Concepto | Qué es | Quién lo crea |
|---|---|---|
| **Control** | Una regla del checklist: *qué* se debería cumplir | El usuario, desde el frontend |
| **Finding** | El resultado de evaluar un control sobre **un recurso concreto** en **un momento** | La Lambda de checks (Etapa 11) |

## 3. Objetivos del usuario

1. Una aplicación funcionando en AWS.
2. Un repositorio público bien documentado.
3. Una arquitectura que pueda explicar en una entrevista.
4. Un proyecto para LinkedIn, con una publicación **factual y sin exagerar**.
5. Conocimiento real de cada servicio AWS usado.
6. Implementación principalmente en **Python**.
7. Infraestructura reproducible con IaC (**AWS CDK en Python**).
8. Comprensión clara de costos, Free Tier y eliminación de recursos (*Deploy → Test → Demo → Destroy → Verify*).

**Objetivo final de aprendizaje:** abrir la consola de AWS, GitHub y el código y poder explicar **qué hace cada componente, por qué existe, cómo se comunica, qué permisos tiene, cuánto cuesta, cómo se despliega y cómo se elimina**.

## 4. Perfil del usuario

- Desarrollador con experiencia en **backend, APIs, bases de datos, Docker y Git**; **empezando** en AWS, Cloud y Cloud Security. No asumir conocimiento de AWS.
- Trabaja en **Windows + PowerShell + VS Code**; usa **AWS CloudShell** para la CLI (sin access keys). La consola de AWS a veces aparece en español y a veces en inglés.
- Idioma: **español rioplatense**.
- Estilo de aprendizaje: ver [AGENTS.md §9](../AGENTS.md#9-cómo-enseñar-el-usuario-lo-exige). Resumen: más explicación, varias opciones con una recomendación, pasos concretos primero y después preguntas concretas de una idea; tablas y diagramas ASCII.

## 5. Documentos fundacionales del usuario

| Documento | Fecha | Qué define |
|---|---|---|
| **Prompt original de tutoría** | 2026-09-29 | Rol de tutor, método (explicación → preguntas → corrección → implementación incremental), uso de consola y CLI, CDK, backend sin frameworks innecesarios, DynamoDB diseñado en conjunto, frontend deliberadamente simple, IAM y least privilege, Cognito solo cuando la base funcione, CloudWatch, checks read-only con boto3, costos y Free Tier (advertir siempre), servicios prohibidos de entrada, estructura del repo, GitHub Actions + OIDC, LinkedIn factual, etapas 0–16, checkpoints, debugging con método, documentación oficial de AWS |
| **"Evolución futura del proyecto — V1 → V2"** | 2026-10-07 | V1 read-only (Detection → Assessment → Findings → Report); V2 de remediación (SAFE/REVIEW/MANUAL, Ansible, re-scan) en el **mismo repo**; no sobrearquitecturar la V1; findings estructurados; checkpoint "V1 → V2 Architecture Review" |
| **"Dirección futura y evolución del proyecto"** | 2026-10-08 | Terminar primero la V1 (Bloque A); Bloque B (Docker → Terraform → ECR → ECS/Fargate → CI/CD → OIDC → Observability → SQS → Ansible → DevSecOps → IA → Performance); documentar el **porqué**, alternativas, ventajas y desventajas de cada decisión; ADRs; el README cuenta la evolución y solo documenta lo que existe; principio *problema → tecnología* |

Su contenido está reflejado en [ROADMAP.md](ROADMAP.md), [DECISIONS.md](DECISIONS.md) y [AGENTS.md](../AGENTS.md).

## 6. Cambios de alcance y de plan

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-09-29 | Usuario con poco conocimiento de cloud pide más explicación y pasos concretos antes de las preguntas | Las preguntas abstractas lo confundían |
| ~2026-10-03 | **Lambda pasa a ser la Etapa 4 y API Gateway la 5** | API Gateway necesita algo a quién invocar |
| 2026-10-07 | Se define la **V2** (remediación) como evolución del mismo repo; la V1 queda estrictamente read-only | Documento "V1 → V2" |
| 2026-10-08 | Se define el **Bloque B** y la regla "terminar la V1 primero". Aparece la contradicción sobre la Etapa 13 (CI/CD en V1 vs. Bloque B) | Documento "Dirección futura" |
| 2026-10-08 | Funcionalidades objetivo de la V1: Dashboard, Security Checks, Findings, Score, Scan, Finding Details | Mismo documento |
| 2026-10-10 | El usuario propone **FastAPI**; se decide **no** usarlo en la V1 (opción A: refactor en módulos) | Empaquetado arm64, cold start, desvío del roadmap (D46) |
| 2026-10-10 | Se define el **modelo de despliegue self-hosted single-account** | Pregunta del usuario sobre cómo lo usarían otros (D48) |
| 2026-10-12 | Nombre **OpenAegis**; carpeta renombrada; transferencia de contexto a una sesión nueva de VS Code | — |

## 7. Cronología resumida

Fechas aproximadas (los timestamps del historial están en UTC).

| Fecha | Hito |
|---|---|
| 2026-09-29/30 | Etapa 0: root con MFA, IAM user en grupo `Admins`, sin access keys, Budget `monthly-credits-guard` (USD 5, excluye créditos), alertas de Free Tier, `us-east-1`. Etapa 1 (conceptos) |
| 2026-10-01 | Etapa 2: bucket S3 privado |
| 2026-10-02 | Etapa 3: CloudFront con OAC, pay-as-you-go |
| 2026-10-03/05 | Etapa 4: Lambda. Repo público con docs 00–04 y licencia MIT (`6c35796`, `ce27643`) |
| 2026-10-06/07 | Diagramas de arquitectura; Etapa 5: HTTP API, throttling, CORS (`f1b38d4`) |
| 2026-10-08 | Diseño del modelo de datos con el usuario; tabla DynamoDB creada; item `S3-001` cargado a mano |
| 2026-10-08/10 | `GET /controls`, `GET /controls/{id}`, `POST /controls` verificados; refactor en 5 módulos (`6953537`); `PATCH` (`e5dbabf`) con pruebas parciales |
| 2026-10-12 | Renombre a OpenAegis y esta documentación |

## 8. Estado actual de la cuenta AWS [CONVERSACIÓN]

- **AWS Free plan** (cuenta creada después de julio de 2025). Al 2026-09-30: USD 100 en créditos + hasta USD 100 por actividades; el acceso gratuito termina el **2027-03-29** o al agotarse los créditos. En el Free plan no se cobra a la tarjeta: **el riesgo es agotar los créditos y perder el acceso**.
- ⚠️ Crear una **AWS Organization**, activar **IAM Identity Center** o **Control Tower**, o hacer clic en *upgrade plan* pasa la cuenta al **Paid plan** y hace vencer los créditos de inmediato.
- Las cuentas en Free plan **no son elegibles** para los flat-rate plans de CloudFront.
- Root: MFA, sin access keys, sin uso diario. IAM user `<admin-user>` con contraseña + MFA, sin access keys, en el grupo `Admins` (`AdministratorAccess`). Acceso de IAM a Billing activado.
- Budget `monthly-credits-guard`: USD 5/mes, filtro *Charge type excludes Credit*, Unblended, alertas al 50 % real, 100 % real y 100 % pronosticado, sin acciones automáticas.

Recursos creados y datos en la tabla: ver [ARCHITECTURE.md](ARCHITECTURE.md). Datos de prueba en la tabla al 2026-10-10: `S3-001` (cargado a mano, quedó con `status: FAIL` por una prueba del `PATCH`), **dos `S3-002` duplicados** (bug del error 11 del [LEARNING_LOG](LEARNING_LOG.md); uno se borró el 2026-10-13 como primera prueba del `DELETE`, quedan 3 controles) y `S3-004` (creado para probar mass assignment; desde las pruebas del `PATCH` del 2026-10-13 tiene título "IAM Password Policy" y severidad `CRITICAL`).

## 9. Fuentes del historial

- Conversación principal: `%USERPROFILE%\.claude\projects\c--AWS-aws-cloud-security-checklist\6a39046d-2c47-4442-83d4-de68040efb86.jsonl` (sesión "OpenAegis - desarrollo V1").
- Memorias de esa sesión: `%USERPROFILE%\.claude\projects\c--AWS-aws-cloud-security-checklist\memory\`.
- ⚠️ El historial contiene el ID de la cuenta y el ID de la API **sin tapar**. No copiarlos a ningún archivo del repo.
