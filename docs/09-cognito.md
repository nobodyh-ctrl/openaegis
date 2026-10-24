# Etapa 9 — Cognito: login en la SPA y API con JWT authorizer

> **Estado:** 🟡 casi completa (2026-10-22 → 2026-10-24). Login con MFA, token en cada llamada y API cerrada con un JWT authorizer, verificados en producción (§4.5). Falta desplegar y probar el manejo del `401` en la SPA (PR #13, ya mergeado) y el checkpoint de la etapa (§12).
> **Costo de la etapa:** USD 0 extra. Cognito *Essentials* incluye 10.000 usuarios activos por mes gratis, sin vencimiento; el JWT authorizer de HTTP API no tiene cargo aparte (§7).

## 1. Objetivo

Hasta la Etapa 8, **cualquiera** con la URL de la API podía leer, crear y borrar controles con `curl`: CORS solo protege a los usuarios del navegador. Esta etapa agrega:

- un **User Pool** de Cognito con registro cerrado y **MFA obligatorio**;
- **login en la SPA** (Authorization Code + PKCE) con renovación y logout;
- el **access token** en cada llamada a la API;
- un **JWT authorizer** en API Gateway que rechaza todo pedido sin un token válido **antes** de invocar la Lambda.

Decisión grande: [ADR-007](architecture-decisions/007-autenticacion-cognito.md).

## 2. Conceptos clave

### 2.1 Autenticación vs. autorización

| | Pregunta | Quién la responde en OpenAegis |
|---|---|---|
| **Autenticación** | ¿Quién sos? | Cognito: contraseña + código TOTP |
| **Autorización** | ¿Qué podés hacer? | API Gateway (JWT authorizer): ¿el token es válido y tiene el scope de la ruta? |

### 2.2 El flujo completo (Authorization Code + PKCE)

```text
 VOS              SPA (CloudFront)                COGNITO                    API GATEWAY
  │  entrás a /app    │                              │                            │
  │──────────────────►│ ¿hay sesión? NO              │                            │
  │                   │ ① genera un secreto (PKCE)   │                            │
  │                   │──── redirect a /authorize ──►│                            │
  │                   │                              │ ② login: contraseña + MFA  │
  │                   │◄── redirect /app/callback ───│ ③ ?code=abc (un solo uso)  │
  │                   │ ④ POST /oauth2/token         │                            │
  │                   │    code + secreto PKCE ─────►│ valida → emite TOKENS      │
  │                   │◄──── id, access, refresh ────│                            │
  │                   │ ⑤ GET /controls                                           │
  │                   │    Authorization: Bearer <access token> ─────────────────►│ valida firma, iss,
  │◄── dashboard ─────│◄────────────────────────────────────────────── 200 ───────│ client_id, exp, scope
```

**PKCE** (analogía del guardarropas): antes del login la SPA inventa un secreto (*code verifier*) y a Cognito le manda solo su hash (*code challenge*). Para canjear el `code` tiene que mostrar el secreto original. Si alguien roba el `code` (de un log o del historial), no le sirve sin el secreto, que nunca salió del navegador. Por eso una SPA puede ser un **cliente público, sin client secret**.

### 2.3 Los tres tokens

| Token | Dice | Analogía | Uso en OpenAegis |
|---|---|---|---|
| **ID token** | Quién sos (`email`, `sub`) | El DNI | Mostrar el email en la barra superior |
| **Access token** | Qué podés hacer (`client_id`, `scope`) | La pulsera de un recital | **Se manda a la API** en `Authorization: Bearer` |
| **Refresh token** | — (es opaco para la app) | Un vale para renovar la pulsera | Renovar los otros dos sin pedir login (12 h) |

A la API se le manda el **access token**, nunca el ID token: el ID token es para la app que te logueó, trae datos personales y **no tiene `scope`**.

### 2.4 Listas de permitidos del app client

Cognito trata el pedido de login como un contrato: si un parámetro no está permitido por el app client, **rechaza todo** antes de mostrar el login.

| La SPA pide | El app client permite | Resultado |
|---|---|---|
| `redirect_uri` = localhost | Solo CloudFront | `redirect_mismatch` |
| `scope` = `openid email phone` | `openid email` | `invalid_scope` (vuelve al callback con `?error=`) |
| `scope` = `openid email` | `openid email` | Pantalla de login |

La lista de callbacks impide que un link armado por un atacante mande tu `code` a su sitio.

### 2.5 Revocar: qué se puede cortar y qué no

```text
Cerrar sesión ──► Cognito revoca el REFRESH token  → ya no se pueden sacar tokens nuevos ✅
                  el ACCESS token que ya existe…   → API Gateway lo valida POR SU CUENTA
                                                     (firma + exp, sin preguntarle a Cognito)
                                                     → sirve hasta que vence (máx. 1 h) ⚠️
```

Por eso el access token dura **1 hora**: es el daño que no se puede revocar. Verificado en vivo en la prueba 7 (§4.5).

**Dos sesiones:** la de la SPA (tokens en `sessionStorage`) y la de Cognito (una cookie en su dominio). Si el logout borrara solo la primera, al tocar "Iniciar sesión" Cognito te dejaría pasar **sin contraseña ni MFA**. El logout cierra las dos.

### 2.6 JWT authorizer

Un guardia que API Gateway pone **antes** de la Lambda. Verifica la firma con las claves públicas del JWKS del User Pool (cacheadas hasta 2 h), el `kid`, `iss`, `client_id` (o `aud`), `exp`, `nbf`, `iat` y el scope de la ruta. Si algo falla, responde él: **la Lambda no se ejecuta** (sin costo de Lambda ni de DynamoDB ante un ataque).

| Código | Significa | Cuándo |
|---|---|---|
| **401** Unauthorized | "No sé quién sos" | Sin token, token inventado, firma adulterada o vencido |
| **403** Forbidden | "Sé quién sos, pero no podés entrar acá" | Token válido sin el scope que exige la ruta (por ejemplo, un ID token) |

El `401` trae `www-authenticate: Bearer` (RFC 6750) y, si el pedido trae un `Origin` permitido, también `access-control-allow-origin`: la SPA **puede leerlo**.

## 3. Decisiones técnicas

| # | Decisión | Detalle |
|---|---|---|
| D80 | User Pool y app client | Plan *Essentials*, solo el admin crea usuarios, MFA obligatorio (TOTP), deletion protection; app client público sin secret, Authorization Code + PKCE, scopes `openid email`, callbacks y logout solo de localhost y CloudFront (§4.1) |
| D81 | Login en la SPA | `oidc-client-ts` 3.5.0; tokens en `sessionStorage`; renovación con refresh token de **12 h** y revocación en el logout; access token a la API; `returnTo` solo a rutas `/app` (§4.3) |
| D82 | Autorización en la API | JWT authorizer nativo de HTTP API en las 5 rutas, con scope `openid`; `authorization` en el CORS; orden "lo que permite → lo que usa → lo que exige" (§4.2, §4.4) |
| D83 | SPA ante `401` y `403` | `401` → login de nuevo, con freno de 1 minuto contra el bucle; `403` → mensaje en español (§4.5) |

Alternativas y motivos: [DECISIONS.md](DECISIONS.md) y [ADR-007](architecture-decisions/007-autenticacion-cognito.md).

## 4. Configuración realizada

### 4.1 Paso 9.1 — User Pool, app client y usuario (2026-10-22) [CONVERSACIÓN]

Creado a mano en la consola. Verificado con `describe-user-pool` y `describe-user-pool-client`:

| Campo | Valor |
|---|---|
| Plan | `ESSENTIALS` |
| MFA | `ON` (obligatorio), TOTP con app autenticadora |
| Registro | `AllowAdminCreateUserOnly = true`: nadie se registra solo |
| Deletion protection | `ACTIVE` |
| App client | `openaegis-spa`, **sin secret** |
| Flujos OAuth | `code` |
| Scopes | `openid`, `email` (la consola agregó `phone` por defecto; se sacó por least privilege) |
| Callback URLs | `http://localhost:5173/app/callback` · `https://<distribucion>.cloudfront.net/app/callback` |
| Logout URLs | `http://localhost:5173/app` · `https://<distribucion>.cloudfront.net/app` |
| Duración de tokens | Access e ID: 60 min · Refresh: **720 min (12 h)** (primero quedó en 12 *días* por la unidad del combo; corregido) |
| Revocación de tokens | `EnableTokenRevocation = true` |
| Dominio del login | `https://<dominio-cognito>` |

Un usuario (el del dueño) con MFA. El primer login de prueba devolvió `/app/callback?code=...`: el flujo funcionaba antes de escribir código.

Marcadores nuevos para el repo: `<user-pool-id>`, `<client-id>`, `<dominio-cognito>`.

### 4.2 Paso 9.2 — CORS: permitir el header del token (2026-10-22) [CONVERSACIÓN]

Con el header `Authorization`, hasta un `GET` dispara preflight. Si el CORS no lo permite, el navegador corta en la preflight y la Lambda **no deja logs** (el error solo se ve con F12).

API Gateway → CORS → **Allow-Headers: `content-type`, `authorization`**. Origins y métodos sin cambios.

| Verificación | Resultado |
|---|---|
| `get-apis --query 'Items[].CorsConfiguration'` | `AllowHeaders` = `content-type`, `authorization` |
| Preflight desde el origen de CloudFront | `204` · `access-control-allow-headers: authorization,content-type` |
| Preflight desde `https://sitio-ajeno.example` | `204` **sin** `access-control-allow-origin` |
| SPA en producción | Sin cambios |

### 4.3 Paso 9.3 — Login en la SPA (2026-10-23, PR #12)

| Archivo | Qué hace |
|---|---|
| `frontend/src/lib/auth.ts` *(nuevo)* | Único archivo que usa `oidc-client-ts`. `userManager` (`redirect_uri` armada con `window.location.origin`, `response_type: "code"`, `scope: "openid email"`, `sessionStorage`, `automaticSilentRenew`, `metadataSeed` con el `revocation_endpoint`, que Cognito no publica). `getAccessToken()`, `login(returnTo)`, `returnToFrom()`, `requireSession()` y `logout()` |
| `frontend/src/pages/CallbackPage.tsx` *(nuevo)* | `/app/callback`: canjea el `code` **una sola vez** (la promesa se guarda fuera del componente porque `StrictMode` ejecuta los efectos dos veces y el `code` es de un solo uso) y vuelve con `navigate(..., { replace: true })` |
| `frontend/src/router.tsx` | `/app/callback` **afuera** de `/app` (adentro sería un bucle); `loader: requireSession` en `/app`: sin sesión no se dibuja nada |
| `frontend/src/components/layout/AppLayout.tsx` | Email del ID token y "Cerrar sesión" en la barra superior |
| `frontend/src/lib/api.ts` | `Authorization: Bearer <access token>` |
| `frontend/.env.example` · `vite-env.d.ts` | `VITE_COGNITO_AUTHORITY`, `VITE_COGNITO_CLIENT_ID`, `VITE_COGNITO_DOMAIN` con marcadores. Los valores reales van en `.env.local` (ignorado). No son secretos: quedan visibles en el `.js` |

`requireSession()`: con sesión vigente sigue; con el access token vencido y refresh token, renueva sin pedir login; si no, manda al login recordando la página.

`logout()`: (1) revoca el refresh token en `/oauth2/revoke`; (2) borra los tokens locales; (3) va al `/logout` de Cognito con `client_id` y `logout_uri` (Cognito no usa el `end_session_endpoint` estándar). Si la revocación falla, igual cierra la sesión local.

**Dependencia (D68):** `oidc-client-ts@3.5.0`, publicada el 2026-03-13, Apache-2.0, una sola dependencia (`jwt-decode@4.0.0`, MIT). `npm audit`: 0 vulnerabilidades.

**Deploy:** el mismo de la 8.8 (D79). Vite lee `.env.local` también en `npm run build`, así que solo hay que definir `VITE_API_URL`. Se agregó una verificación: `Select-String ... -Pattern "cognito-idp"` sobre el bundle.

Prueba local y en producción [CONVERSACIÓN]: login con contraseña + MFA, dashboard con datos y email arriba, header `Authorization` en *Network*, la sesión sobrevive al F5, el logout vuelve al login y el `returnTo` lleva a `/app/controles`. En producción, CRUD completo.

### 4.4 Paso 9.4 — JWT authorizer (2026-10-24) [CONVERSACIÓN]

API Gateway → **Authorization** → *Manage authorizers*:

| Campo | Valor |
|---|---|
| Tipo | JWT |
| Nombre | `cognito-openaegis` |
| Identity source | `$request.header.Authorization` |
| Issuer | `https://cognito-idp.us-east-1.amazonaws.com/<user-pool-id>` |
| Audience | `<client-id>` |

Asociado a las **5 rutas** con **authorization scope `openid`**. Sin el scope, un ID token pasaría: la documentación de AWS avisa que el authorizer no distingue access token de ID token y recomienda exigir scopes. El stage `$default` tiene auto-deploy: aplica en segundos.

```bash
export AWS_PAGER=""
APIID=$(aws apigatewayv2 get-apis --query "Items[?Name=='cloud-sec-checklist-http-api'].ApiId" --output text)
API=https://$APIID.execute-api.us-east-1.amazonaws.com
aws apigatewayv2 get-authorizers --api-id $APIID
aws apigatewayv2 get-routes --api-id $APIID --query 'Items[].{Ruta:RouteKey,Auth:AuthorizationType,Scopes:AuthorizationScopes}' --output table
curl -sS -i $API/controls      # sin token
```

Resultado: las 5 rutas con `JWT` + `openid`; sin token, `401 {"message":"Unauthorized"}` con `www-authenticate: Bearer`. La SPA siguió andando, porque ya mandaba el token.

### 4.5 Paso 9.5 — Verificación de punta a punta (2026-10-24) [CONVERSACIÓN]

Los tokens se copiaron de la SPA (F12 → Console → `copy(...)` desde `sessionStorage`) y se cargaron en CloudShell con `read -rs`, para que no queden en pantalla ni en el historial.

| # | Prueba | Resultado |
|---|---|---|
| 1 | Token inventado (`abc.def.ghi`) | `401` |
| 2 | Access token válido | `200` |
| 3 | ID token | **`403`**: válido, pero sin el scope `openid` (la predicción era `401`; ver §2.6) |
| 4 | Access token con la firma adulterada | `401` |
| 5 | `401` con `Origin` de CloudFront | Trae `access-control-allow-origin`: la SPA puede leer el `401` |
| 6 | 5 pedidos con token falso, sin tocar la SPA, y `aws logs tail --since 1m \| grep -c START` | `401 ×5` y **0** ejecuciones de la Lambda |
| 7 | Access token **después de cerrar sesión** | `200`: el access token no se revoca (§2.5) |

La primera versión de la prueba 6 contó 5 `START` porque en esa ventana también se usó la SPA: hay que aislar la ventana de logs.

**Manejo del `401` en la SPA (PR #13, mergeado el 2026-10-24; deploy pendiente):** como el `401` es legible, `api.ts` llama a `reloginAfter401()`, que borra la sesión local y manda al login. Caso real: cerrar sesión en otra pestaña revoca el refresh token compartido; una hora después, esta pestaña no puede renovar y recibe `401`. **Freno de 1 minuto:** si el `401` sigue después de un login nuevo (por ejemplo, un authorizer con otro client ID), se muestra el error. Sin el freno, la cookie de Cognito haría un bucle login → `401` → login automático e infinito. El `403` muestra "No tenés permiso para esta acción."

## 5. Plan de la etapa

| Paso | Qué | Toca AWS | Estado |
|---|---|---|---|
| 9.1 | User Pool, app client, usuario con MFA | Sí (Cognito, sin costo) | ✅ 2026-10-22 (§4.1) |
| 9.2 | CORS: `authorization` en Allow-Headers | Sí (configuración) | ✅ 2026-10-22 (§4.2) |
| 9.3 | Login en la SPA + token en las llamadas + deploy | Sí (S3) | ✅ 2026-10-23, PR #12 (§4.3) |
| 9.4 | JWT authorizer en las 5 rutas con scope `openid` | Sí (configuración) | ✅ 2026-10-24 (§4.4) |
| 9.5 | Verificación de punta a punta + manejo del `401` en la SPA | Sí (S3, para el deploy) | 🟡 Pruebas ✅; PR #13 mergeado, sin desplegar (§4.5) |
| 9.6 | Documentación, diagramas, checkpoint y nota de Obsidian | No | 🟡 Docs y diagramas ✅ (2026-10-24); checkpoint [PENDIENTE] |

## 6. Verificación (resumen de la etapa)

| Qué | Cómo | Resultado |
|---|---|---|
| Configuración de Cognito | `describe-user-pool` y `describe-user-pool-client` | ✅ (§4.1) |
| CORS | Preflight con `curl -X OPTIONS` desde dos orígenes | ✅ (§4.2) |
| Login y token | Navegador: *Network* y *Application* | ✅ (§4.3) |
| Authorizer | `get-routes`, y `curl` con 5 tipos de token | ✅ (§4.4, §4.5) |
| La Lambda no corre ante un `401` | `aws logs tail` en una ventana aislada | ✅ 0 ejecuciones |
| Código | CI `checks` en los PR #12 y #13 | ✅ (los dos mergeados) |

## 7. Costos

USD 0 extra (verificado en la página de precios de Cognito y en la de API Gateway):

- **Cognito *Essentials*:** 10.000 MAU por mes gratis, **sin vencimiento**. *Plus* no tiene free tier. SMS (vía SNS) tendría costo: se usa **TOTP**, que es gratis. Cognito está incluido en el Free plan de la cuenta.
- **JWT authorizer:** sin cargo aparte; en HTTP API se paga por llamada y por transferencia. Los `401` no invocan la Lambda ni DynamoDB.
- **Preflight:** con el header `Authorization` (y `MaxAge 0`), cada llamada de la SPA hace un `OPTIONS` además del pedido real. A esta escala no cambia nada (§10).

## 8. Relación con Cloud Security

| Tema | Qué se aplicó |
|---|---|
| Autenticación fuerte | MFA obligatorio (algo que sabés + algo que tenés). Una contraseña filtrada no alcanza |
| Superficie de ataque | Registro cerrado (`AllowAdminCreateUserOnly`): con registro abierto, cualquiera obtendría un token válido |
| Least privilege | Scopes mínimos (`openid email`, sin `phone`); scope `openid` exigido por ruta |
| Robo del `code` | PKCE + `code` de un solo uso + lista exacta de callbacks |
| Robo de tokens (XSS) | `sessionStorage` (muere con la pestaña), refresh token de 12 h, revocación en el logout; access token de 1 h (lo que no se puede revocar) |
| Open redirect | `returnTo` solo a rutas `/app` |
| Defensa antes del cómputo | El authorizer rechaza antes de la Lambda: sin costo ni logs ante bots (*denial of wallet*) |
| Seguridad por oscuridad | Un UUID difícil de adivinar no reemplaza la autorización: antes de la 9.4, conocer un `id` alcanzaba para borrarlo con `curl` |
| CORS ≠ autenticación | CORS lo aplica el navegador; el authorizer, API Gateway |

## 9. Cómo revertir esta etapa

En orden inverso, para no dejar la SPA rota en el medio:

1. **Authorizer:** API Gateway → *Authorization* → desasociarlo de las 5 rutas y borrarlo. La API vuelve a estar abierta.
2. **SPA:** revertir los PR #13 y #12 y redesplegar (D79).
3. **CORS:** sacar `authorization` de Allow-Headers.
4. **Cognito:** desactivar la deletion protection y borrar el User Pool (borra el app client, el dominio y los usuarios). ⚠️ Irreversible.

## 10. Pendientes y mejoras posibles

- Desplegar y probar en producción el PR #13, ya mergeado (`401` → login) [PENDIENTE].
- Checkpoint de la etapa [PENDIENTE].
- `check_identifiers.py`: detectar IDs de Cognito (User Pool ID `us-east-1_...`, dominio `*.auth.us-east-1.amazoncognito.com`) [PENDIENTE].
- `MaxAge` del CORS en 0: cada llamada hace preflight. Subirlo (por ejemplo, a 300 s) [PROPUESTA].
- Usar el `sub` del token en la Lambda (`requestContext.authorizer.jwt.claims`) para auditar quién crea o borra cada control [PROPUESTA].
- Scopes propios con un *resource server* (`controls.read`, `controls.write`) para roles de solo lectura [PROPUESTA, V2].
- Mostrar el ID de la cuenta en la UI (D64) [PENDIENTE].

## 11. Cosas que NO se deben hacer

- Mandar el **ID token** a la API, o quitar el scope `openid` de las rutas.
- Asociar el authorizer **antes** de que la SPA mande el token, o a menos rutas que todas.
- Guardar tokens en `localStorage`, o en la URL (`?token=`): quedan en logs, historial y `Referer`.
- Abrir el registro de usuarios, o desactivar el MFA.
- Pedir en el código un scope que el app client no permite (rompe el login de todos con `invalid_scope`).
- Hacer el logout borrando solo los tokens locales (la cookie de Cognito te dejaría entrar sin contraseña).
- Pegar tokens en un chat, un ticket o un commit. Para pruebas: `read -rs`.
- Correr `npm` desde WSL sobre un `node_modules` instalado en Windows (binarios nativos por plataforma).

## 12. Checkpoint

[PENDIENTE] Se completa al cerrar la etapa, después del deploy del PR #13.

Respuestas del usuario durante la etapa: [LEARNING_LOG.md §3](LEARNING_LOG.md#3-predicciones-del-patch).
