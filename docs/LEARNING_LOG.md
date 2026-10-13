# Learning log

> Qué se aprendió en cada etapa y qué errores aparecieron, con la lección de cada uno. Sirve para no re-enseñar desde cero en sesiones nuevas, para reforzar lo que costó y como material para el README ("Lessons learned") y las entrevistas.
> Fuente: historial de trabajo con el usuario (2026-09-29 a 2026-10-10) y docs de cada etapa.

## 1. Conceptos enseñados

| Etapa | Conceptos | Dónde se explican |
|---|---|---|
| 0 | Identidad vs. credenciales · deny by default · root vs. IAM user · MFA vs. least privilege (**probabilidad vs. impacto**) · blast radius · credenciales de largo plazo vs. temporales (`AKIA`/`ASIA`/`AIDA`) · responsabilidad compartida · Budgets (excluir créditos), alertas de Free Tier | [00](00-account-setup.md) |
| 1 | Todo en AWS es una API · regiones, AZ y edge locations · multi-AZ vs. multi-región · IaaS/PaaS/serverless · modelos de cobro (por hora, por request, por GB) · costos ocultos · *denial of wallet* | [01](01-cloud-fundamentals.md) |
| 2 | Object storage · bucket/objeto/key · Block Public Access · identity-based vs. resource-based policies · defensa en profundidad · anatomía de un ARN | [02](02-s3.md) |
| 3 | CDN, caché, TTL e invalidaciones · OAC · flujo de una request por CloudFront · **403 en vez de 404 para evitar enumeración** · HTTPS · WAF y su costo | [03](03-cloudfront.md) |
| 4 | Handler, event y context · cold start / warm start (el Init se factura) · **stateless** · permisos en dos direcciones (quién invoca a Lambda vs. qué puede hacer Lambda) · trust policy vs. permissions policy · línea `REPORT` · datos sensibles en logs | [04](04-lambda.md) |
| 5 | HTTP API vs. REST API · rutas, integraciones, stages · payload 2.0 (el body llega como **string**) · el viaje de una request · **CORS lo aplica el navegador; no es autenticación** · preflight `OPTIONS` · throttling (rate vs. burst) · la URL de la API no es un secreto (*security through obscurity*) · log streams | [05](05-api-gateway.md) |
| 6 | NoSQL · tabla/item/atributo · partition key (HASH) y sort key (RANGE) · GetItem vs. Query vs. Scan · **diseñar por access patterns** · `Count` vs. `ScannedCount` · paginación (`LastEvaluatedKey`, 1 MB por llamada) · consistencia eventual · conditional writes · **`UpdateItem` es un upsert** · palabras reservadas y marcadores `#nombre` / `:valor` (como consultas parametrizadas) · clave sustituta vs. natural · no hay foreign keys · on-demand vs. provisioned · *mass assignment* y allowlist · validar tipos antes que contenido · idempotencia (`PATCH` vs. `POST`) · *fail fast* · traducir errores en el borde · separación de responsabilidades | [06](06-dynamodb.md) |
| Transversal | Diagrama **"quién le pide permiso a quién"** (flechas ① a ⑤) | [architecture/permissions-flow.drawio.png](../architecture/permissions-flow.drawio.png), [ARCHITECTURE.md](ARCHITECTURE.md#5-iam-quién-le-pide-permiso-a-quién) |
| Transversal | Modelos de despliegue de herramientas de seguridad: CLI local, self-hosted, SaaS multi-tenant (cross-account roles + ExternalId, *confused deputy*), híbrido | [DECISIONS.md](DECISIONS.md) D48 |
| Transversal | Emuladores de AWS (moto, LocalStack, Floci): qué sirven para probar y qué no (IAM) | [DECISIONS.md](DECISIONS.md#propuestas-no-decididas) |

## 2. Errores y problemas encontrados

| # | Problema | Evidencia / cómo se detectó | Solución | Lección |
|---|---|---|---|---|
| 1 | Email del autor con un typo en el primer commit | Revisión del historial de Git | Reescritura del primer commit (`--force-with-lease`) | Configurar `user.email` antes del primer commit; reescribir historia solo si nadie más la usa |
| 2 | Un `.drawio` no se ve como imagen en GitHub; después, fondo negro en el modo oscuro | Vista del repo en GitHub | Formato `.drawio.png` (imagen editable) con fondo blanco explícito | Verificar cómo se ve en el destino real |
| 3 | CloudFront seguía sirviendo el contenido viejo después de subir un archivo nuevo | Comparación del contenido + headers de caché | Invalidación (`/index.html` o `/*`) | El CDN cachea según el TTL; subir a S3 no invalida nada. Ver [03](03-cloudfront.md#6-caché-e-invalidation-debugging) |
| 4 | `event.get("nombre", "Mundo")` ocultaba el caso vacío; un test pasaba porque usaba otro input | Prueba con body sin el campo | Validar explícitamente ausente/vacío | Un valor por defecto puede esconder un error. Ver [04](04-lambda.md#6-debugging-el-valor-por-defecto-que-ocultaba-un-error) |
| 5 | El body de API Gateway llega como **string** | `event["body"]` no era un dict | `json.loads` | Leer el formato real del event (payload 2.0) |
| 6 | JSON válido que no es un objeto (`[]`) → `AttributeError` → 500 | Traceback en CloudWatch | `isinstance(body, dict)` → 400 | JSON válido ≠ forma esperada. Ver [05](05-api-gateway.md#62-json-válido-que-no-es-un-objeto) |
| 7 | "No aparecen los logs" | Estaban en **otro log stream** | `aws logs tail --since --filter-pattern` (lee todos los streams) | Un stream por entorno de ejecución |
| 8 | **Throttling invertido** (rate 20 / burst 10) | No se veía en las métricas por minuto; se encontró **leyendo la configuración** con `aws apigatewayv2 get-stage` | Corregido a rate 10 / burst 20 → prueba de 60 requests: `50 × 200`, `10 × 429` | Verificar la configuración, no inferirla de métricas agregadas |
| 9 | `AccessDenied` en `dynamodb:Scan` (provocado a propósito) | Traceback en CloudWatch; el cliente veía 500 | Inline policy `controls-table-crud` | El cliente ve un 500 aunque quien no tiene permiso es el **rol**; la verdad está en los logs |
| 10 | `uuid.UUID()` fuera del `try` en `get_control` → 500 con un id inválido | Prueba con `abc` | Mover al `try` → 400; además normalizar a la forma canónica | Validar la entrada antes de usarla |
| 11 | **`Limit=1` en un Scan con filtro**: el chequeo de `code` duplicado no funcionaba y se crearon **dos `S3-002`** | `aws dynamodb scan --limit 1`: `Count 0 / ScannedCount 1 / LastEvaluatedKey` | Scan paginado **sin `Limit`** | `Limit` acota los items **leídos**, no los devueltos. Los duplicados se dejaron para la primera prueba de `DELETE` |
| 12 | Sin validación de tipos: `"title": 123` → `TypeError` → 500; `"severity": ["HIGH"]` → `unhashable type` | Pruebas con `curl` | `isinstance(value, str)` primero, con `FIELD_RULES` | El cliente manda cualquier tipo que permita JSON |
| 13 | `except Exception` amplio | Revisión de código | Eliminado | Oculta errores de la métrica *Errors*; atrapar solo lo que se sabe manejar |
| 14 | `PATCH` parcial permitía `title` vacío (`not partial` en la línea equivocada) | Revisión de código antes del deploy | "Obligatorio" en `PATCH` = "no hace falta que venga, pero si viene no puede estar vacío" | Probar también `"   "` (por el `strip`) |
| 15 | Riesgo de upsert de `UpdateItem` | Explicado antes de implementar | `ConditionExpression="attribute_exists(id)"` → 404 | Sin la condición, el `PATCH` crea items sin `code`/`title`/`created_at` y devuelve 200 |
| 16 | **Incidente:** durante el refactor el asistente **sobrescribió archivos que el usuario estaba creando al mismo tiempo**, sin commitear; esa versión no se pudo recuperar | El asistente lo detectó y lo avisó | — | Siempre `git status` y leer el archivo antes de escribirlo. Regla en [AGENTS.md](../AGENTS.md) |
| 17 | El usuario a veces pega **IDs de cuenta y de API sin tapar** | Salidas pegadas en la conversación | Recordatorio | Tapar identificadores antes de compartir; en el repo, siempre marcadores |
| 18 | `bash: id: No such file or directory` al copiar un ejemplo con `<id>` | Salida de CloudShell | Reemplazar el marcador | En bash, `<` y `>` son redirecciones |
| 19 | Se documentó "un statement por ruta" en la resource-based policy de la Lambda, pero `PATCH` y `DELETE` funcionaron sin statements nuevos | `aws lambda get-policy`: 3 statements, `SourceArn` `.../*/*/<path>` | Docs corregidos | El segundo `*` del `SourceArn` es el **método**: el permiso es por **path**. Verificar la configuración real en lugar de suponerla |

## 3. Predicciones del `PATCH`

- *Si no se cambia el handler a `handler.lambda_handler` después de subir el zip, ¿qué error aparece?* Respuesta del usuario (2026-10-13): "no se encuentra el archivo del handler, un 404". **Idea central correcta**; corregido el detalle: no es un 404 HTTP sino `Runtime.ImportModuleError` (Lambda no encuentra el módulo `lambda_function`), la invocación falla antes de ejecutar el código y el cliente recibe un **500**.
- Predicción del upsert: el usuario pidió la explicación ("no sé, decime") y se le dio (ver error 15).
- Unicidad del `code` al editar: el usuario respondió bien que `S3-001` → `{"code": "S3-004"}` da **409** (encuentra a **otro** control).
- *Sin statement en la resource-based policy, ¿quién responde?* El usuario eligió bien: API Gateway responde 500 y la Lambda no deja logs.
- *¿Un `POST` a una ruta borrada de API Gateway deja log en la Lambda?* El usuario predijo que sí; **no**: el 404 `{"message":"Not Found"}` lo genera API Gateway sin invocar la Lambda. Hay dos 404 distintos: el de API Gateway (la ruta no existe en la API) y el del router de `handler.py` (la ruta existe en la API pero no en `ROUTES`).
