import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import type { FlashbarProps } from "@cloudscape-design/components/flashbar";

/** Notificaciones al estilo de la consola (Flashbar arriba del contenido). Las de éxito se cierran solas. */
type Notify = (type: "success" | "error", content: string) => void;

const NotificationsContext = createContext<{ items: FlashbarProps.MessageDefinition[]; notify: Notify } | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<FlashbarProps.MessageDefinition[]>([]);

  const notify = useCallback<Notify>((type, content) => {
    const id = crypto.randomUUID();
    const dismiss = () => setItems((list) => list.filter((m) => m.id !== id));
    setItems((list) => [...list, { id, type, content, dismissible: true, dismissLabel: "Cerrar", onDismiss: dismiss }]);
    if (type === "success") setTimeout(dismiss, 5000);
  }, []);

  return <NotificationsContext.Provider value={{ items, notify }}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications tiene que usarse dentro de <NotificationsProvider>");
  return ctx;
}
