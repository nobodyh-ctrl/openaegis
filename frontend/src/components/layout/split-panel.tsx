import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/**
 * El panel de detalle (SplitPanel) vive en el AppLayout, pero su contenido lo decide cada página.
 * La página llama a useSplitPanel(contenido) y el layout lo dibuja; al salir de la página, se limpia.
 */
type SplitPanelState = { content: ReactNode | null; setContent: (c: ReactNode | null) => void };

const SplitPanelContext = createContext<SplitPanelState | null>(null);

export function SplitPanelProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode | null>(null);
  return <SplitPanelContext.Provider value={{ content, setContent }}>{children}</SplitPanelContext.Provider>;
}

export function useSplitPanelContent() {
  const ctx = useContext(SplitPanelContext);
  if (!ctx) throw new Error("Falta <SplitPanelProvider>");
  return ctx.content;
}

export function useSplitPanel(content: ReactNode | null) {
  const ctx = useContext(SplitPanelContext);
  if (!ctx) throw new Error("Falta <SplitPanelProvider>");
  const { setContent } = ctx;
  useEffect(() => {
    setContent(content);
  }, [content, setContent]);
  useEffect(() => () => setContent(null), [setContent]);
}
