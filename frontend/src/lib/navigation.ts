import { useCallback } from "react";
import { useNavigate } from "react-router";

/**
 * Los links de Cloudscape son <a href> normales. Para navegar sin recargar la página (SPA),
 * se intercepta onFollow y se usa el router. Un clic con Ctrl/rueda sigue abriendo otra pestaña.
 */
export function useFollow() {
  const navigate = useNavigate();
  return useCallback(
    (event: CustomEvent<{ href?: string; external?: boolean }>) => {
      const href = event.detail.href;
      if (!href || event.detail.external) return;
      event.preventDefault();
      navigate(href);
    },
    [navigate],
  );
}
