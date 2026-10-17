import { PageHeader } from "@/components/layout/PageHeader";

// Contenido real en el paso 8.5 (totales por estado y por severidad).
export function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Resumen de los controles de seguridad de la cuenta." />
      <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
        Los totales por estado y por severidad llegan en el paso 8.5.
      </div>
    </>
  );
}
