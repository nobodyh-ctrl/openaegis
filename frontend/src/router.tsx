import { createBrowserRouter, Navigate } from "react-router";
import { AppLayout } from "@/components/layout/AppLayout";
import { NotFoundPage } from "@/pages/NotFoundPage";

// Las páginas se cargan bajo demanda (`lazy`): cada una queda en su propio archivo .js y el
// navegador la baja recién al entrar a esa ruta. El layout y la 404 van en el bundle inicial.
export const router = createBrowserRouter([
  // "/" queda reservada para la landing (D66); hasta entonces, redirige a la app.
  { path: "/", element: <Navigate to="/app" replace /> },
  {
    path: "/app",
    element: <AppLayout />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("@/pages/DashboardPage")).DashboardPage }) },
      { path: "controles", lazy: async () => ({ Component: (await import("@/pages/ControlsPage")).ControlsPage }) },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
