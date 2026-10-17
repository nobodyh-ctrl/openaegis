import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";

/**
 * Configuración de TanStack Query (D70) para toda la app.
 * - No reintenta errores 4xx: un 400/404/409 no se arregla repitiendo, y un 429 es el throttling
 *   avisando que bajemos el ritmo. Sí reintenta (una vez) errores de red o 5xx.
 * - staleTime: durante 30 s los datos se consideran frescos y no se vuelven a pedir al navegar.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return failureCount < 1;
      },
    },
  },
});
