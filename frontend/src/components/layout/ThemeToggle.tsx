import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const next = theme === "dark" ? "claro" : "oscuro";
  return (
    <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label={`Cambiar a tema ${next}`} title={`Tema ${next}`}>
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
