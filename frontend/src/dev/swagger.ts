// Página de desarrollo: dibuja backend/openapi.yaml con Swagger UI. Ver swagger.html y D69.
import "swagger-ui-dist/swagger-ui.css";
import { SwaggerUIBundle } from "swagger-ui-dist";

SwaggerUIBundle({
  url: "/openapi.yaml", // lo sirve el plugin openApiDevServer de vite.config.ts, solo en desarrollo
  dom_id: "#swagger-ui",
  deepLinking: true,
  tryItOutEnabled: true,
});
