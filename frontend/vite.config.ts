import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // .env.local no llega solo a process.env dentro de este archivo: hay que cargarlo
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      // Proxy SOLO de desarrollo (npm run dev): /api/* → tu API, sin pasar por CORS del navegador.
      // No existe en el build de producción. Ver docs/08-frontend.md §2.4.
      proxy: env.API_PROXY_TARGET
        ? {
            "/api": {
              target: env.API_PROXY_TARGET,
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/api/, ""),
            },
          }
        : undefined,
    },
  };
});
