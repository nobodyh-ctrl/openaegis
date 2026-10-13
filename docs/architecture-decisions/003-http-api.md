# ADR-003: API Gateway HTTP API como punto de entrada del backend

- **Estado:** aceptada
- **Fecha:** 2026-10-07 (Etapa 5; rutas del CRUD en la Etapa 6)
- **Decisiones relacionadas:** D22, D26–D31, D41, D42 ([DECISIONS.md](../DECISIONS.md))

## Contexto

La Lambda (ADR-001) solo puede ser invocada por identidades de AWS con requests firmadas, y un navegador no tiene credenciales de AWS. Hace falta una **puerta de entrada HTTPS pública** que reciba requests normales, las enrute a la Lambda y, como la API todavía no tiene autenticación, **limite el abuso y el costo**. En la Etapa 9 se va a sumar autenticación con Cognito.

## Decisión

Una **HTTP API** de API Gateway (`cloud-sec-checklist-http-api`), stage `$default` con auto-deploy, integración Lambda proxy (payload 2.0), **throttling rate 10 / burst 20** y **CORS gestionado por API Gateway**, restringido al dominio de CloudFront. Las rutas son REST sobre un solo recurso:

```text
GET    /controls          POST   /controls
GET    /controls/{id}     PATCH  /controls/{id}     DELETE /controls/{id}
```

## Por qué

- **Autorizador JWT nativo**, que encaja con Cognito (Etapa 9).
- **CORS integrado:** API Gateway responde los preflight `OPTIONS` sin invocar la Lambda.
- **Throttling** como techo de costo (*denial of wallet*) mientras no hay autenticación.
- Más barata que una REST API y con menos piezas.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| **REST API** de API Gateway | Más cara por request; sus ventajas (API keys, usage plans, caché, WAF directo, transformaciones) no resuelven ningún requisito actual |
| Lambda Function URL | Sin throttling configurable por ruta ni autorizador JWT nativo; `AuthType: NONE` es un endpoint público directo (D22) |
| ALB → Lambda | Costo fijo por hora |
| API bajo CloudFront (`/api/*`) | Elimina CORS, pero agrega complejidad de comportamientos y caché; queda como mejora posible (D30) |

## Ventajas

- Una sola URL HTTPS administrada, con escalado automático.
- Las rutas que no existen las rechaza API Gateway (404) **sin invocar la Lambda**.
- Separación clara: el **router** de rutas existe dos veces a propósito, en API Gateway (qué se expone) y en `handler.py` (qué función atiende cada `routeKey`).

## Desventajas

- Menos funcionalidades que la REST API: sin WAF directo, sin API keys ni usage plans.
- La URL es pública y se va a ver en el JavaScript del frontend: **no es un secreto** y no protege nada.
- Hasta la Etapa 9, **cualquiera con la URL puede leer, crear, editar y borrar** controles. El throttling limita el abuso, pero no lo impide.
- El permiso de invocación (resource-based policy) quedó **por path y no por método**: el statement de `/controls/{id}` autoriza `GET`, `PATCH` y `DELETE`.

## Consideraciones de seguridad

- Solo **esta** API puede invocar la Lambda (`AWS:SourceArn` con el ID de la API y el path).
- CORS restringido al dominio de CloudFront. **CORS lo aplica el navegador: no es autenticación.** `curl` lo ignora.
- Los logs registran la ruta y los dos request IDs, nunca el event completo (headers, IP y, con Cognito, tokens).
- Los errores llegan al cliente como mensajes genéricos; el detalle queda en CloudWatch.

## Consideraciones de costo

HTTP API: USD 1,00 por millón de requests ([05-api-gateway.md](../05-api-gateway.md#7-costos), verificado en la Etapa 5). Con cientos de requests de prueba, fracciones de centavo. El throttling 10/20 acota el peor caso. Access logs no activados (tendrían costo de CloudWatch).

## Consecuencias

- El handler adopta el formato de payload 2.0: body como **string**, `routeKey`, `pathParameters`.
- Cada **path** nuevo agrega un statement a la resource-based policy; cada ruta nueva hay que crearla en API Gateway **y** en `ROUTES`.
- Con Cognito habrá que sumar `authorization` a los Allow-Headers de CORS.

## Evolución futura

- Etapa 9: autorizador JWT de Cognito en las rutas.
- Etapa 7 / CDK: restringir los statements también por método (`.../*/GET/controls`).
- Bloque B: si el backend se migra a contenedores, el punto de entrada podría pasar a ser un ALB. Es parte de la comparación Lambda vs. ECS, no una decisión tomada.
