import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

// Pantalla temporal del paso 8.1: verifica React + Tailwind + shadcn/ui + alias "@/".
// Se reemplaza por el router y el layout en el paso 8.3.
export default function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background text-foreground">
      <div className="flex items-center gap-3">
        <ShieldCheck className="size-10" aria-hidden="true" />
        <h1 className="text-4xl font-semibold tracking-tight">OpenAegis</h1>
      </div>
      <p className="text-muted-foreground">Gestión de controles de seguridad para tu cuenta de AWS</p>
      <Button>Ir a la app</Button>
    </main>
  );
}
