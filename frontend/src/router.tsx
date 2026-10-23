import { createBrowserRouter, Navigate } from "react-router";
import { AppLayout } from "@/components/layout/AppLayout";
import { requireSession } from "@/lib/auth";
import { NotFoundPage } from "@/pages/NotFoundPage";

// Las páginas se cargan bajo demanda (`lazy`): cada una queda en su propio archivo .js y el
// navegador la baja recién al entrar a esa ruta. El layout y la 404 van en el bundle inicial.
export const router = createBrowserRouter([
  // "/" queda reservada para la landing (D66); hasta entonces, redirige a la app.
  { path: "/", element: <Navigate to="/app" replace /> },
  // Vuelta del login de Cognito. Va AFUERA de /app: si estuviera adentro, el loader de /app
  // (que exige sesión) mandaría al login antes de canjear el code, en un bucle sin fin.
  { path: "/app/callback", lazy: async () => ({ Component: (await import("@/pages/CallbackPage")).CallbackPage }) },
  {
    path: "/app",
    // Sin sesión no se dibuja nada de /app: el loader manda al login de Cognito (Etapa 9).
    loader: requireSession,
    element: <AppLayout />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("@/pages/DashboardPage")).DashboardPage }) },
      { path: "controles", lazy: async () => ({ Component: (await import("@/pages/ControlsPage")).ControlsPage }) },
      { path: "controles/nuevo", lazy: async () => ({ Component: (await import("@/pages/ControlFormPage")).ControlFormPage }) },
      { path: "controles/:id/editar", lazy: async () => ({ Component: (await import("@/pages/ControlFormPage")).ControlFormPage }) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
