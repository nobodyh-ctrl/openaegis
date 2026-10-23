/**
 * Login con Cognito (Etapa 9). Es el ÚNICO archivo que habla con oidc-client-ts:
 * el resto de la app le pide a este módulo el usuario o el token.
 */
import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";

/** Lee una variable VITE_ obligatoria. Si falta, la app falla al arrancar con un mensaje claro. */
function requireEnv(name: string, value: string | undefined): string {
  if (!value) throw new Error(`Falta ${name} en frontend/.env.local (ver .env.example).`);
  return value;
}

const AUTHORITY = requireEnv("VITE_COGNITO_AUTHORITY", import.meta.env.VITE_COGNITO_AUTHORITY);
const CLIENT_ID = requireEnv("VITE_COGNITO_CLIENT_ID", import.meta.env.VITE_COGNITO_CLIENT_ID);
const COGNITO_DOMAIN = requireEnv("VITE_COGNITO_DOMAIN", import.meta.env.VITE_COGNITO_DOMAIN).replace(/\/$/, "");

export const userManager = new UserManager({
  authority: AUTHORITY,
  client_id: CLIENT_ID,
  // Tiene que coincidir letra por letra con una de las "Callback URLs" del app client.
  // window.location.origin hace que el mismo build sirva en localhost y en CloudFront.
  redirect_uri: `${window.location.origin}/app/callback`,
  response_type: "code", // Authorization Code + PKCE (oidc-client-ts genera el verifier solo)
  scope: "openid email", // los mismos que permite el app client: pedir otro da invalid_scope
  userStore: new WebStorageStateStore({ store: window.sessionStorage }), // muere al cerrar la pestaña
  // Renueva el access token con el refresh token un rato antes de que venza.
  automaticSilentRenew: true,
  // Cognito no publica el endpoint de revocación en su configuración OIDC: se lo indicamos.
  metadataSeed: { revocation_endpoint: `${COGNITO_DOMAIN}/oauth2/revoke` },
});

/** Access token vigente para mandar a la API, o null si no hay sesión o venció. */
export async function getAccessToken(): Promise<string | null> {
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}

/**
 * Manda al login de Cognito. Al volver, Cognito redirige a /app/callback con el ?code=.
 * returnTo viaja en el "state" (guardado en sessionStorage) para volver a la página donde estabas.
 */
export function login(returnTo = "/app"): Promise<void> {
  return userManager.signinRedirect({ state: { returnTo } });
}

/**
 * A dónde ir después del callback. Solo se aceptan rutas internas de la app: nunca una URL
 * externa ("//sitio.com" o "https://..."), para no convertir el login en un open redirect.
 */
export function returnToFrom(state: unknown): string {
  const returnTo = (state as { returnTo?: unknown } | undefined)?.returnTo;
  return typeof returnTo === "string" && returnTo.startsWith("/app") ? returnTo : "/app";
}

/**
 * Loader de /app (React Router): corre ANTES de dibujar el layout.
 * - Hay sesión vigente → devuelve el usuario.
 * - El access token venció pero hay refresh token (por ejemplo, volviste después de 2 h) → renueva sin pedir login.
 * - No hay sesión, o la renovación falla (refresh token vencido o revocado) → manda al login.
 */
export async function requireSession({ request }: { request: Request }): Promise<User> {
  const user = await userManager.getUser();
  if (user && !user.expired) return user;
  if (user?.refresh_token) {
    const renewed = await userManager.signinSilent().catch(() => null);
    if (renewed) return renewed;
  }
  const { pathname, search } = new URL(request.url);
  await login(pathname + search);
  // signinRedirect ya cambió window.location: la página se va. Nunca resolvemos, así no se dibuja nada.
  return new Promise<never>(() => {});
}

/**
 * Cierra la sesión en tres pasos:
 * 1. Revoca el refresh token en Cognito: si alguien lo robó, ya no puede renovar.
 * 2. Borra los tokens del sessionStorage.
 * 3. Cierra la sesión del login de Cognito (su cookie) y vuelve a /app.
 *    Cognito usa su propio /logout con logout_uri, no el estándar de OIDC.
 */
export async function logout(): Promise<void> {
  try {
    await userManager.revokeTokens(["refresh_token"]);
  } catch (error) {
    // Si la revocación falla (por ejemplo, sin red), igual cerramos la sesión local:
    // dejar al usuario logueado sería peor. El refresh token vence solo a las 12 h.
    console.warn("No se pudo revocar el refresh token:", error);
  }
  await userManager.removeUser();
  const params = new URLSearchParams({ client_id: CLIENT_ID, logout_uri: `${window.location.origin}/app` });
  window.location.assign(`${COGNITO_DOMAIN}/logout?${params}`);
}
