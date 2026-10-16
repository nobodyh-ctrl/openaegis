/// <reference types="vite/client" />

// Variables que Vite expone al código del navegador (solo las que empiezan con VITE_).
interface ImportMetaEnv {
  /** URL de la API en producción. Si no está definida, se usa "/api" (el proxy de desarrollo). */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
