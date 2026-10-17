import { createBrowserRouter, Navigate } from "react-router";
import { AppLayout } from "@/components/layout/AppLayout";
import { ControlsPage } from "@/pages/ControlsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const router = createBrowserRouter([
  // "/" queda reservada para la landing (D66); hasta entonces, redirige a la app.
  { path: "/", element: <Navigate to="/app" replace /> },
  {
    path: "/app",
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "controles", element: <ControlsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
