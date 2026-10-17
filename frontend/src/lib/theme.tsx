import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

/**
 * Tema claro/oscuro (D71: oscuro por defecto). El tema activo es la clase "dark" en <html>:
 * todas las variables de color de index.css cambian juntas. La elección se recuerda en
 * localStorage, que puede no estar disponible (modo privado, bloqueos): por eso el try/catch.
 */
export type Theme = "dark" | "light";

const STORAGE_KEY = "openaegis-theme";

function readStoredTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Sin localStorage, el tema dura lo que la pestaña: no es un error.
    }
  }, [theme]);

  const toggleTheme = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme tiene que usarse dentro de <ThemeProvider>");
  return ctx;
}
