# ADR-007: Autenticación con Cognito (OIDC + PKCE) y JWT authorizer en API Gateway

- **Estado:** aceptada
- **Fecha:** 2026-10-22 → 2026-10-24 (Etapa 9)
- **Decisiones relacionadas:** D80, D81, D82, D83 ([DECISIONS.md](../DECISIONS.md)) · se apoya en [ADR-003](003-http-api.md) (HTTP API con autorizador JWT nativo) y [ADR-006](006-frontend-spa.md) (SPA estática) · detalle en [09-cognito.md](../09-cognito.md)

## Contexto

Hasta la Etapa 8, la API no tenía autenticación. Cualquiera con su URL (que no es un secreto: está en el `.js` de la SPA) podía listar, crear y borrar controles con `curl`. CORS no lo impedía, porque lo aplica el navegador. Lo único que limitaba el abuso era el throttling.

Requisitos:

- que solo el dueño del despliegue (modelo self-hosted, D48) use la app y la API;
- login fuerte: una contraseña filtrada no tiene que alcanzar;
- sin servidores nuevos ni costo fijo, y sin secretos en la SPA (todo lo compilado es público);
- que la Lambda no se ejecute para pedidos no autenticados.

## Decisión

- **Amazon Cognito User Pool** (plan *Essentials*) como proveedor de identidad: registro cerrado (solo el admin crea usuarios), **MFA obligatorio con TOTP**, deletion protection.
- **App client público** (sin secret) con **Authorization Code + PKCE**, scopes `openid email` y callbacks solo de localhost y CloudFront.
- En la SPA, **`oidc-client-ts`**: tokens en `sessionStorage`, renovación con un refresh token de 12 h, revocación en el logout, y el **access token** en `Authorization: Bearer`.
- En la API, el **JWT authorizer nativo de HTTP API** en todas las rutas, exigiendo el scope `openid` (así rechaza los ID tokens).
- Orden de implementación sin corte de servicio: CORS (lo que permite) → SPA (lo que usa) → authorizer (lo que exige).

## Por qué

- Cognito es el proveedor OIDC administrado de AWS: sin servidores, con MFA, login administrado y JWKS incluidos, y con 10.000 usuarios activos por mes gratis.
- Authorization Code + PKCE es el flujo recomendado para SPAs: un cliente público no puede guardar un secreto, y PKCE cumple ese rol en cada login.
- El JWT authorizer valida firma, emisor, audiencia, vencimiento y scope **antes** de la Lambda, sin código propio ni dependencias, y sin cargo aparte.
- `oidc-client-ts` es una librería OIDC estándar y chica (una dependencia): no ata la SPA a AWS y no esconde el protocolo.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| AWS Amplify (Auth) | Decenas de dependencias (contra D68), ata la SPA a AWS y esconde justo lo que el proyecto quiere enseñar |
| PKCE y canje de tokens escritos a mano | Código de seguridad casero: un error en `state` o en PKCE abre un agujero |
| Lambda authorizer | Para reglas a medida; para un JWT estándar es código y costo de más |
| Validar el JWT dentro de la Lambda | Una dependencia nueva en Python, y la Lambda se ejecuta igual ante cada ataque |
| API keys de API Gateway | No existen en HTTP API, y una key en la SPA sería pública |
| IAM (SigV4) con Cognito Identity Pool | Credenciales de AWS en el navegador y más piezas; no aporta nada para una API propia |
| Proveedor externo (Auth0, Okta, Entra ID) | Otra cuenta y otro proveedor que mantener; el modelo self-hosted pide que todo viva en la cuenta del usuario |

## Ventajas

- La API deja de estar abierta: sin token válido, `401`; con un token sin el scope, `403`.
- Ataques sin token no cuestan Lambda ni DynamoDB, ni llenan los logs (verificado: 5 pedidos con token falso, 0 ejecuciones).
- MFA obligatorio y registro cerrado.
- Ningún secreto en la SPA ni en el repo; el mismo build sirve en local y en producción.

## Desventajas

- El access token **no se puede revocar**: el authorizer lo valida sin consultar a Cognito. Mitigado con una duración de 1 h.
- Tokens en el navegador: un XSS podría leerlos. Mitigado con `sessionStorage`, refresh token de 12 h y React (que escapa el HTML).
- Más configuración manual en la consola (pool, app client, authorizer) hasta la Etapa 12 (CDK).
- Cognito tiene particularidades no estándar: no publica el `revocation_endpoint` ni el `end_session_endpoint`, y el logout usa su propio `/logout?logout_uri=`.
- Con el header `Authorization`, cada llamada hace preflight de CORS (con `MaxAge 0`).

## Consideraciones de seguridad

- Exigir un scope por ruta es lo que evita que se acepte un ID token (recomendación de la documentación de AWS).
- Callbacks, logout URLs y scopes son listas exactas: cualquier otro valor se rechaza (`redirect_mismatch`, `invalid_scope`).
- El logout cierra dos sesiones: la de la SPA y la cookie del login de Cognito.
- `returnTo` solo acepta rutas `/app` (sin open redirect).
- El reintento de login ante un `401` tiene un freno de 1 minuto, para no entrar en un bucle automático.

## Consideraciones de costo

- Cognito *Essentials*: 10.000 MAU por mes gratis, sin vencimiento. TOTP gratis; el MFA por SMS tendría costo (SNS) y no se usa.
- JWT authorizer: sin cargo aparte en HTTP API.
- Verificar los precios vigentes antes de desplegar en otra cuenta.

## Consecuencias

- Para probar la API con `curl` hace falta un access token (en las pruebas se copia de la SPA con `read -rs`).
- La SPA necesita tres variables de compilación nuevas (`VITE_COGNITO_*`), además de `VITE_API_URL`.
- Hay tres marcadores nuevos en la documentación: `<user-pool-id>`, `<client-id>`, `<dominio-cognito>`.

## Evolución futura

- **Etapa 12 (CDK):** pool, app client y authorizer como código.
- Auditoría por usuario con el claim `sub` en la Lambda.
- Scopes propios (*resource server*: `controls.read`, `controls.write`) si aparecen roles distintos.
- En una edición multi-tenant (Bloque B), el modelo de identidad se revisa entero (tenants, grupos, federación).
