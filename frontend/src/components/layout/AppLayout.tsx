import { useState } from "react";
import type { AppLayoutProps } from "@cloudscape-design/components/app-layout";
import AppLayoutToolbar from "@cloudscape-design/components/app-layout-toolbar";
import Badge from "@cloudscape-design/components/badge";
import Box from "@cloudscape-design/components/box";
import Link from "@cloudscape-design/components/link";
import BreadcrumbGroup, { type BreadcrumbGroupProps } from "@cloudscape-design/components/breadcrumb-group";
import Flashbar from "@cloudscape-design/components/flashbar";
import SideNavigation from "@cloudscape-design/components/side-navigation";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import type { User } from "oidc-client-ts";
import { matchPath, Outlet, useLoaderData, useLocation } from "react-router";
import { logout } from "@/lib/auth";
import { AWS_REGION, REPO_URL } from "@/lib/config";
import { useFollow } from "@/lib/navigation";
import { useNotifications } from "@/lib/notifications";
import { useTheme } from "@/lib/theme";
import { useControls } from "@/lib/use-controls";
import { SplitPanelProvider, useSplitPanelContent } from "./split-panel";

// Logo de GitHub ("mark-github" de Octicons, licencia MIT): Cloudscape no lo trae entre sus íconos.
const GITHUB_ICON = (
  <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true">
    <path
      fill="currentColor"
      stroke="none"
      d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"
    />
  </svg>
);

function breadcrumbsFor(pathname: string): BreadcrumbGroupProps.Item[] {
  const home = { text: "OpenAegis", href: "/app" };
  const controls = { text: "Controles", href: "/app/controles" };
  if (pathname === "/app/controles") return [home, controls];
  if (pathname === "/app/controles/nuevo") return [home, controls, { text: "Nuevo control", href: pathname }];
  if (matchPath("/app/controles/:id/editar", pathname)) return [home, controls, { text: "Editar", href: pathname }];
  return [home, { text: "Dashboard", href: "/app" }];
}

/** Estructura de la consola (D75): barra superior, menú por secciones, breadcrumbs, notificaciones y panel de detalle. */
export function AppLayout() {
  return (
    <SplitPanelProvider>
      <Shell />
    </SplitPanelProvider>
  );
}

function Shell() {
  const { pathname } = useLocation();
  // El loader de /app (requireSession) ya garantizó que hay sesión: acá solo leemos quién es.
  const user = useLoaderData() as User;
  const email = typeof user.profile.email === "string" ? user.profile.email : "Mi cuenta";
  const follow = useFollow();
  const { theme, setTheme } = useTheme();
  const { items } = useNotifications();
  const { data } = useControls();
  const splitPanel = useSplitPanelContent();
  const [splitOpen, setSplitOpen] = useState(true);
  const [splitPrefs, setSplitPrefs] = useState<AppLayoutProps.SplitPanelPreferences>({ position: "bottom" });
  const activeHref = pathname.startsWith("/app/controles") ? "/app/controles" : pathname;

  return (
    <>
      <div id="top-nav" style={{ position: "sticky", top: 0, zIndex: 1002 }}>
        <TopNavigation
          identity={{ href: "/app", title: "OpenAegis", logo: { src: "/logo.svg", alt: "" }, onFollow: follow }}
          utilities={[
            { type: "button", iconName: "globe", text: AWS_REGION, ariaLabel: `Región evaluada: ${AWS_REGION}`, disableUtilityCollapse: true },
            {
              type: "menu-dropdown",
              iconName: "settings",
              ariaLabel: "Preferencias",
              title: "Preferencias",
              items: [
                { id: "dark", text: "Tema oscuro", iconName: theme === "dark" ? "check" : undefined },
                { id: "light", text: "Tema claro", iconName: theme === "light" ? "check" : undefined },
              ],
              onItemClick: ({ detail }) => setTheme(detail.id === "light" ? "light" : "dark"),
            },
            { type: "button", iconSvg: GITHUB_ICON, ariaLabel: "Repositorio en GitHub (abre en otra pestaña)", title: "GitHub", href: REPO_URL, target: "_blank", rel: "noopener noreferrer" },
            {
              // El email sale del ID token (claim "email"): para esto existe el ID token.
              type: "menu-dropdown",
              iconName: "user-profile",
              text: email,
              ariaLabel: `Cuenta: ${email}`,
              items: [{ id: "logout", text: "Cerrar sesión" }],
              onItemClick: ({ detail }) => {
                if (detail.id === "logout") void logout();
              },
            },
          ]}
        />
      </div>
      <AppLayoutToolbar
        headerSelector="#top-nav"
        footerSelector="#app-footer"
        toolsHide
        ariaLabels={{ navigation: "Menú", navigationClose: "Cerrar menú", navigationToggle: "Abrir menú" }}
        notifications={<Flashbar items={items} stackItems />}
        breadcrumbs={<BreadcrumbGroup ariaLabel="Ruta" onFollow={follow} items={breadcrumbsFor(pathname)} />}
        navigation={
          // Dos menús en una columna: el principal arriba y "Ayuda" fijo al pie del panel, como en la consola.
          <div style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
            <SideNavigation
              activeHref={activeHref}
              onFollow={follow}
              items={[
                {
                  type: "section",
                  text: "General",
                  items: [{ type: "link", text: "Dashboard", href: "/app" }],
                },
                {
                  type: "section",
                  text: "Seguridad",
                  items: [
                    { type: "link", text: "Controles", href: "/app/controles", info: data ? <Badge>{data.count}</Badge> : undefined },
                  ],
                },
              ]}
            />
            <div style={{ marginTop: "auto" }}>
              <SideNavigation
                items={[
                  { type: "divider" },
                  { type: "link", text: "Documentación", href: `${REPO_URL}/tree/main/docs`, external: true },
                  { type: "link", text: "Reportar un problema", href: `${REPO_URL}/issues`, external: true },
                ]}
              />
            </div>
          </div>
        }
        splitPanel={splitPanel ?? undefined}
        splitPanelOpen={splitOpen}
        onSplitPanelToggle={({ detail }) => setSplitOpen(detail.open)}
        splitPanelPreferences={splitPrefs}
        onSplitPanelPreferencesChange={({ detail }) => setSplitPrefs(detail)}
        content={<Outlet />}
      />
      {/* Pie fijo como el de la consola. Las páginas legales todavía no existen: los links llevan a la 404 hasta que se armen. */}
      <footer
        id="app-footer"
        style={{
          position: "sticky",
          bottom: 0,
          zIndex: 1002,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "flex-end",
          alignItems: "center",
          gap: "8px 24px",
          padding: "6px 16px",
          background: "#0b1524",
          color: "#c6cbd2",
        }}
      >
        <Box fontSize="body-s" color="inherit">© {new Date().getFullYear()} OpenAegis</Box>
        <Link variant="secondary" color="inverted" fontSize="body-s" href="/app/privacidad" onFollow={follow}>Privacidad</Link>
        <Link variant="secondary" color="inverted" fontSize="body-s" href="/app/terminos" onFollow={follow}>Términos</Link>
      </footer>
    </>
  );
}
