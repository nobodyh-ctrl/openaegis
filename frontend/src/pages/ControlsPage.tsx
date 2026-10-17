import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// Paso 8.3: solo verifica la conexión (TanStack Query → cliente → proxy → API).
// La tabla, los filtros y el CRUD llegan en el paso 8.4.
export function ControlsPage() {
  const { data, isPending, error } = useQuery({ queryKey: ["controls"], queryFn: api.listControls });

  return (
    <>
      <PageHeader title="Controles" description="Reglas de seguridad que se evalúan en la cuenta." />
      <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
        {isPending && "Cargando controles…"}
        {error && <span className="text-destructive">No se pudieron cargar los controles: {error.message}</span>}
        {data && `La API respondió con ${data.count} controles. La tabla llega en el paso 8.4.`}
      </div>
    </>
  );
}
