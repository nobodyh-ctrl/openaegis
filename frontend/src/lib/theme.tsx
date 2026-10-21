import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { applyMode, Mode } from "@cloudscape-design/global-styles";

/**
 * Tema claro/oscuro (oscuro por defecto). Con Cloudscape (D75), el modo se aplica con applyMode(),
 * que agrega la clase "awsui-dark-mode" en <body>. La elección se recuerda en localStorage
 * (puede no estar disponible: por eso el try/catch).
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
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    applyMode(theme === "dark" ? Mode.Dark : Mode.Light); // en <body>, donde Cloudscape define los colores
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Sin localStorage, el tema dura lo que la pestaña: no es un error.
    }
  }, [theme]);

  const toggleTheme = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);

  return <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme tiene que usarse dentro de <ThemeProvider>");
  return ctx;
}
