import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import { useNavigate } from "react-router";
import type { User } from "oidc-client-ts";
import { login, returnToFrom, userManager } from "@/lib/auth";

// El ?code= es de UN SOLO USO. En desarrollo, StrictMode ejecuta los efectos dos veces:
// sin esto, el segundo canje fallaría con invalid_grant. Guardamos la promesa para canjear una sola vez.
// No hace falta "resetearla": login y logout recargan la página entera, y con eso el módulo arranca de cero.
let exchange: Promise<User> | null = null;

/**
 * /app/callback: Cognito vuelve acá después del login con ?code=...&state=...
 * oidc-client-ts valida el state, canjea el code + el verifier PKCE por los tokens y los guarda.
 */
export function CallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    exchange ??= userManager.signinRedirectCallback();
    exchange
      // Vuelve a la página donde estabas antes del login. replace: el callback (con el code ya usado
      // en la URL) no queda en el historial del botón "Atrás".
      .then((user) => navigate(returnToFrom(user.state), { replace: true }))
      // Cognito también vuelve acá con ?error=... (por ejemplo, invalid_scope): se lo mostramos al usuario.
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [navigate]);

  if (error) {
    return (
      <Box padding={{ vertical: "xxxl", horizontal: "l" }}>
        <SpaceBetween size="m">
          <Alert type="error" header="No se pudo iniciar sesión">{error}</Alert>
          <Button variant="primary" onClick={() => void login()}>Volver a intentar</Button>
        </SpaceBetween>
      </Box>
    );
  }

  return (
    <Box textAlign="center" padding={{ vertical: "xxxl" }}>
      <Spinner size="large" />
      <Box variant="p" color="text-body-secondary">Iniciando sesión…</Box>
    </Box>
  );
}
