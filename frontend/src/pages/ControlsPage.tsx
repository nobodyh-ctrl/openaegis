import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { Plus, RotateCw, Search } from "lucide-react";
import { ControlFormSheet } from "@/components/controls/ControlFormSheet";
import { ControlsTable } from "@/components/controls/ControlsTable";
import { DeleteControlDialog } from "@/components/controls/DeleteControlDialog";
import { SEVERITY_ORDER, severityLabel, statusLabel } from "@/components/controls/badges";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { SEVERITIES, STATUSES, type Control } from "@/lib/api";
import { useControls } from "@/lib/use-controls";

const ALL = "ALL"; // Radix Select no acepta "" como valor

/** Lista y administra controles con búsqueda y filtros inicializados desde valores válidos de la URL. */
export function ControlsPage() {
  const { data, isPending, error, refetch, isFetching } = useControls();
  // Filtros iniciales desde la URL (los links del Dashboard: ?estado=FAIL, ?severidad=HIGH)
  const [params] = useSearchParams();
  /** Devuelve el valor del parámetro si está permitido; si falta o es inválido, devuelve ALL. */
  const fromUrl = (key: string, allowed: readonly string[]) => (allowed.includes(params.get(key) ?? "") ? params.get(key)! : ALL);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState(() => fromUrl("severidad", SEVERITIES));
  const [status, setStatus] = useState(() => fromUrl("estado", STATUSES));
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Control | undefined>();
  const [deleting, setDeleting] = useState<Control | null>(null);

  // Filtros y orden en el cliente (D72): son decenas de controles y GET /controls trae todos
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.items ?? [])
      .filter((c) => severity === ALL || c.severity === severity)
      .filter((c) => status === ALL || c.status === status)
      .filter((c) => !q || [c.code, c.title, c.service, c.category].some((t) => t.toLowerCase().includes(q)))
      .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || a.code.localeCompare(b.code));
  }, [data, search, severity, status]);

  const filtered = search.trim() !== "" || severity !== ALL || status !== ALL;
  const openCreate = () => { setEditing(undefined); setFormOpen(true); };
  const openEdit = (c: Control) => { setEditing(c); setFormOpen(true); };

  return (
    <>
      <PageHeader
        title="Controles"
        description="Reglas de seguridad que se evalúan en la cuenta."
        actions={<Button onClick={openCreate}><Plus /> Nuevo control</Button>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por código, título, servicio…" className="pl-8" aria-label="Buscar controles" />
        </div>
        <Select value={severity} onValueChange={setSeverity}>
          <SelectTrigger className="w-40" aria-label="Filtrar por severidad"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toda severidad</SelectItem>
            {SEVERITIES.map((s) => <SelectItem key={s} value={s}>{severityLabel(s)}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40" aria-label="Filtrar por estado"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Todo estado</SelectItem>
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{statusLabel(s)}</SelectItem>)}
          </SelectContent>
        </Select>
        {data && (
          <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
            {visible.length} de {data.count} controles
          </p>
        )}
      </div>

      <div className="rounded-xl border bg-card">
        {isPending && (
          <div className="space-y-3 p-4" aria-label="Cargando controles">
            {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        )}

        {error && (
          <div role="alert" className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="font-medium">No se pudieron cargar los controles</p>
            <p className="text-sm text-muted-foreground">{error.message}</p>
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}><RotateCw /> Reintentar</Button>
          </div>
        )}

        {data && data.count === 0 && (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="font-medium">Todavía no hay controles</p>
            <p className="text-sm text-muted-foreground">Creá el primero para empezar a armar tu checklist.</p>
            <Button onClick={openCreate}><Plus /> Nuevo control</Button>
          </div>
        )}

        {data && data.count > 0 && visible.length === 0 && (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="font-medium">Ningún control coincide con los filtros</p>
            {filtered && (
              <Button variant="outline" onClick={() => { setSearch(""); setSeverity(ALL); setStatus(ALL); }}>Limpiar filtros</Button>
            )}
          </div>
        )}

        {visible.length > 0 && <ControlsTable controls={visible} onEdit={openEdit} onDelete={setDeleting} />}
      </div>

      <ControlFormSheet open={formOpen} onOpenChange={setFormOpen} control={editing} />
      <DeleteControlDialog control={deleting} onClose={() => setDeleting(null)} />
    </>
  );
}
