import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useFollow } from "@/lib/navigation";

// Con las error pages de CloudFront (D67), cualquier ruta inexistente devuelve la app: esta página la resuelve React.
export function NotFoundPage() {
  const follow = useFollow();
  return (
    <Box textAlign="center" padding={{ vertical: "xxxl" }}>
      <SpaceBetween size="m">
        <Box variant="h1">Esta página no existe</Box>
        <Box variant="p" color="text-body-secondary">Revisá la dirección o volvé al inicio.</Box>
        <Button variant="primary" href="/app" onFollow={follow}>Ir al dashboard</Button>
      </SpaceBetween>
    </Box>
  );
}
