import { Link } from "react-router";
import { Button } from "@/components/ui/button";

// Con las error pages de CloudFront (D67), cualquier ruta inexistente devuelve la app: esta página la resuelve React.
export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="font-mono text-sm text-primary">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">Esta página no existe</h1>
      <p className="text-sm text-muted-foreground">Revisá la dirección o volvé al inicio.</p>
      <Button asChild>
        <Link to="/app">Ir al dashboard</Link>
      </Button>
    </div>
  );
}
