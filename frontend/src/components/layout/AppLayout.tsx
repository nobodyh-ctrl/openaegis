import { useState } from "react";
import { Globe, Menu } from "lucide-react";
import { Outlet } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AWS_REGION } from "@/lib/config";
import { Brand, SidebarNav } from "./SidebarNav";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Estructura común de /app: menú lateral (escritorio) o en panel deslizable (móvil),
 * barra superior con la región evaluada y el tema, y <Outlet /> donde React Router dibuja cada página.
 */
export function AppLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Saltar al contenido
      </a>

      <aside className="hidden w-60 shrink-0 border-r border-sidebar-border bg-sidebar px-3 py-5 md:block">
        <SidebarNav />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-3 border-b px-4 md:px-8">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Abrir menú">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 bg-sidebar px-3 py-5">
              <SheetTitle className="sr-only">Menú</SheetTitle>
              <SheetDescription className="sr-only">Navegación principal de OpenAegis</SheetDescription>
              <SidebarNav onNavigate={() => setMobileNavOpen(false)} />
            </SheetContent>
          </Sheet>
          <div className="md:hidden">
            <Brand />
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Badge variant="outline" className="gap-1.5 font-mono" title="Región de AWS evaluada">
              <Globe className="size-3" aria-hidden="true" />
              {AWS_REGION}
            </Badge>
            <ThemeToggle />
          </div>
        </header>

        <main id="contenido" className="flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
