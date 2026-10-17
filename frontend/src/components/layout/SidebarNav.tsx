import { LayoutDashboard, ListChecks, ShieldCheck, type LucideIcon } from "lucide-react";
import { NavLink } from "react-router";
import { REPO_URL } from "@/lib/config";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

// Solo lo que existe (regla del proyecto): Findings y Score aparecen en la Etapa 11.
const NAV_ITEMS: NavItem[] = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/controles", label: "Controles", icon: ListChecks },
];

export function Brand() {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
        <ShieldCheck className="size-5" aria-hidden="true" />
      </span>
      <span className="text-lg font-semibold tracking-tight">OpenAegis</span>
    </div>
  );
}

/** Navegación principal. onNavigate permite cerrar el menú móvil al elegir una opción. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6">
      <Brand />
      <nav aria-label="Principal" className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
              )
            }
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-3 text-xs text-muted-foreground">
        <p>V1 · self-hosted · read-only</p>
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="underline-offset-4 hover:text-foreground hover:underline">
          Código en GitHub
        </a>
      </div>
    </div>
  );
}
