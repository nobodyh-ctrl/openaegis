import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import "@cloudscape-design/global-styles/index.css";
import "@/styles/overrides.css";
import { applyBrandTheme } from "@/lib/brand-theme";
import { NotificationsProvider } from "@/lib/notifications";
import { queryClient } from "@/lib/query-client";
import { ThemeProvider } from "@/lib/theme";
import { router } from "@/router";

applyBrandTheme(); // teal como acento sobre Cloudscape (D76)

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <NotificationsProvider>
          <RouterProvider router={router} />
        </NotificationsProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
