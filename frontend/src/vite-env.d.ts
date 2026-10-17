/// <reference types="vite/client" />

// Variables que Vite expone al código del navegador (solo las que empiezan con VITE_).
interface ImportMetaEnv {
  /** URL de la API en producción. Si no está definida, se usa "/api" (el proxy de desarrollo). */
  readonly VITE_API_URL?: string;
  /** Región evaluada, para mostrar en la UI. Por defecto "us-east-1". */
  readonly VITE_AWS_REGION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
