import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

// Sirve backend/openapi.yaml en /openapi.yaml para la página de Swagger UI (swagger.html).
// configureServer solo corre con `npm run dev`: en el build de producción este plugin no hace nada.
function openApiDevServer(): Plugin {
  const specPath = fileURLToPath(new URL("../backend/openapi.yaml", import.meta.url));
  return {
    name: "openaegis-openapi-dev-server",
    configureServer(server) {
      server.middlewares.use("/openapi.yaml", (_req, res) => {
        res.setHeader("Content-Type", "application/yaml; charset=utf-8");
        res.end(readFileSync(specPath, "utf8"));
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  // .env.local no llega solo a process.env dentro de este archivo: hay que cargarlo
  const env = loadEnv(mode, process.cwd(), "");

  if (mode === "production" && !env.VITE_API_URL?.trim()) {
    throw new Error("VITE_API_URL es obligatoria para compilar en modo production.");
  }

  return {
    plugins: [react(), openApiDevServer()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      // Proxy SOLO de desarrollo (npm run dev): /api/* → tu API, sin pasar por CORS del navegador.
      // No existe en el build de producción. Ver docs/08-frontend.md §2.4.
      proxy: env.API_PROXY_TARGET
        ? {
            "/api/": {
              target: env.API_PROXY_TARGET,
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/api/, ""),
            },
          }
        : undefined,
    },
  };
});
