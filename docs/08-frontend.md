# Etapa 8 — Frontend: SPA con React + Vite + TypeScript

> **Estado:** ⏳ en curso (iniciada el 2026-10-15). Este documento se completa a medida que avanza la etapa: hoy tiene los **conceptos** y las **decisiones**; configuración, verificación y debugging se agregan en cada paso.
> **Costo de la etapa:** USD 0 extra en AWS (mismo S3 + CloudFront; archivos estáticos dentro del Free Tier).

## 1. Objetivo

Reemplazar el `index.html` de prueba por una aplicación real bajo `/app`, que use la API de controles:

- dashboard con totales por estado y por severidad;
- tabla de controles con filtros y búsqueda; crear, editar, cambiar el estado y borrar;
- desarrollo local sin relajar el CORS de producción;
- despliegue en el mismo S3 + CloudFront, con rutas de SPA y una caché bien configurada;
- un job de frontend en el CI.

Decisión de stack y cambio de alcance: [ADR-006](architecture-decisions/006-frontend-spa.md).

## 2. Conceptos clave

### 2.1 SPA: dónde corre cada cosa

Una **SPA** (*single-page application*) es **una sola página HTML** que carga un JavaScript. Desde ahí, **el navegador** dibuja todas las pantallas y cambia la URL sin pedirle páginas nuevas al servidor.

```text
TU PC (al compilar)                AWS (solo guarda y entrega archivos)        NAVEGADOR DEL USUARIO (donde corre React)
┌──────────────────────┐ s3 sync  ┌────────────────────────────┐   HTTPS    ┌─────────────────────────────────┐
│ frontend/src/*.tsx   │ ───────► │ S3 privado                 │ ◄───────── │ 1. pide index.html               │
│   │ npm run build    │          │   index.html               │ CloudFront │ 2. pide assets/index-a1b2c3.js   │
│   ▼                  │          │   assets/index-a1b2c3.js   │  (caché)   │ 3. React dibuja /app/controles   │
│ dist/ (estáticos)    │          │   assets/index-d4e5f6.css  │            │ 4. fetch() ──► API Gateway       │
└──────────────────────┘          └────────────────────────────┘            └─────────────────────────────────┘
```

S3 y CloudFront **no ejecutan** nada del frontend: guardan y entregan archivos. React corre en el navegador de cada usuario.

### 2.2 Qué es Vite

**Vite** (en francés, "rápido") es la herramienta que usamos para **desarrollar** y para **compilar** el frontend. Tiene dos modos, y conviene no confundirlos:

| | `npm run dev` (desarrollo) | `npm run build` (producción) |
|---|---|---|
| **Qué hace** | Levanta un **servidor web local** (`http://localhost:5173`) que sirve el código fuente, lo transforma al vuelo (TypeScript → JavaScript) y recarga la página cuando guardás un archivo (*hot module replacement*) | **Compila**: transforma TypeScript y JSX, une los módulos en pocos archivos (*bundling*), los minifica y agrega un hash del contenido a cada nombre |
| **Dónde corre** | En tu PC, mientras programás | En tu PC, en el CI o en CloudShell, una vez por versión |
| **Resultado** | Nada que desplegar: es un servidor en memoria | La carpeta `dist/`: `index.html` + `assets/*.js` + `assets/*.css` |
| **¿Llega a AWS?** | **No** | **Sí**: `dist/` es lo que se sube a S3 |
| **¿Tiene proxy?** | **Sí** (sección 2.3) | **No**: en producción no hay servidor de Vite, solo archivos estáticos |

Analogía de backend: `npm run dev` es como `dotnet watch` o `uvicorn --reload`, un servidor de desarrollo que se reinicia solo. `npm run build` es como `dotnet publish`: produce el artefacto que se despliega.

### 2.3 Qué es un proxy

Un **proxy** es un intermediario: recibe una request, la **reenvía** a otro servidor y te devuelve la respuesta. Hay dos tipos:

| Tipo | A quién representa | Ejemplo |
|---|---|---|
| **Forward proxy** | Al **cliente**: el servidor ve el proxy, no a vos | El proxy corporativo por el que sale a internet una oficina |
| **Reverse proxy** | Al **servidor**: el cliente cree que habla con un solo servidor, pero el proxy reparte las requests | Nginx delante de una API; **CloudFront delante de S3**; **el proxy de desarrollo de Vite** |

**CloudFront ya es un reverse proxy** (Etapa 3): el navegador le habla a CloudFront, y CloudFront le pide los archivos a S3. El proxy de Vite es lo mismo, en chico y solo en tu PC.

### 2.4 El problema que resuelve el proxy de Vite: CORS en desarrollo

Recordatorio de la Etapa 5: el **origen** es protocolo + dominio + puerto, y el **navegador** bloquea que el JavaScript de un origen lea respuestas de otro, salvo que la API lo autorice con CORS. Tu API solo autoriza el dominio de CloudFront (D28).

**Sin proxy**, en tu PC:

```text
Página servida por Vite:  http://localhost:5173            ← origen A
fetch("https://<api-id>.execute-api.us-east-1.amazonaws.com/controls")   ← origen B

Navegador ──preflight OPTIONS (Origin: http://localhost:5173)──► API Gateway
API Gateway: "localhost:5173 no está en Allow-Origin" → no devuelve el header de permiso
Navegador: ❌ bloquea la request. El JavaScript nunca ve la respuesta
```

**La solución fácil y mala** sería agregar `http://localhost:5173` al CORS de **producción**. Cualquier página servida en `localhost:5173` en **cualquier** máquina (por ejemplo, la de un atacante que prueba algo) podría usar tu API desde un navegador. Es relajar un control de producción por comodidad de desarrollo.

**Con el proxy de Vite:**

```text
                 MISMO ORIGEN (localhost:5173)                  SERVIDOR A SERVIDOR (sin CORS)
Navegador ──fetch("/api/controls")──► Vite dev server ──GET https://<api-id>…/controls──► API Gateway ──► Lambda
          ◄──────── respuesta ───────            ◄────────────── respuesta ──────────────
```

1. El JavaScript pide `/api/controls`, una ruta **relativa**: va al **mismo origen** que sirvió la página (`localhost:5173`). Para el navegador, no hay ningún pedido a otro origen, así que **no hay preflight ni bloqueo**.
2. Vite ve que la ruta empieza con `/api` y, según su configuración, la **reenvía** a la API real, quitando el prefijo `/api`.
3. Esa segunda request la hace **un programa en tu PC (Node.js)**, no un navegador. **CORS lo aplica solo el navegador**: un servidor puede llamar a cualquier API, igual que `curl`.
4. Vite le devuelve la respuesta al navegador como si la hubiera generado él.

> **Idea clave:** CORS **no** protege a la API de otros programas (Etapa 5: no es autenticación). Protege a los **usuarios** de que una página ajena use **su** navegador contra tu API. El proxy no "rompe" CORS: simplemente saca al navegador del medio en el tramo que cruza orígenes.

### 2.5 Cómo se configura (lo vamos a escribir en el paso 8.2)

```ts
// frontend/vite.config.ts (extracto)
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // .env.local no llega solo a process.env dentro de este archivo: hay que cargarlo
  const env = loadEnv(mode, process.cwd(), "");
  return {
    server: {
      proxy: {
        "/api": {
          target: env.API_PROXY_TARGET,                     // URL real de tu API, en frontend/.env.local
          changeOrigin: true,                               // ver abajo
          rewrite: (path) => path.replace(/^\/api/, ""),    // /api/controls → /controls
        },
      },
    },
  };
});
```

| Opción | Qué hace | Por qué la necesitamos |
|---|---|---|
| `loadEnv(...)` | Lee `.env`, `.env.local`, etc. | Dentro de `vite.config.ts`, esas variables no están cargadas automáticamente |
| `"/api"` | Solo se reenvían las rutas que empiezan con `/api`. El resto (la app) lo sigue sirviendo Vite | Separar "pedidos a la API" de "archivos de la app" |
| `target` | A dónde reenviar | La URL de **tu** API, sin escribirla en el código |
| `changeOrigin: true` | Cambia el header `Host` de la request reenviada por el host de la API | API Gateway usa el `Host` para saber **qué API** se está llamando. Si llegara `Host: localhost:5173`, no la encontraría |
| `rewrite` | Quita el prefijo `/api` | La API tiene rutas `/controls`, no `/api/controls` |

**Dos variables distintas, a propósito:**

| Variable | Dónde se usa | ¿Termina en el JavaScript del navegador? |
|---|---|---|
| `API_PROXY_TARGET` | Solo en `vite.config.ts`, para el proxy de desarrollo | **No.** Vite solo expone al código del navegador las variables que empiezan con `VITE_` |
| `VITE_API_URL` | En el código del frontend, al compilar para producción | **Sí**: queda dentro del `.js` compilado. Si no está definida, el frontend usa `/api` (el proxy) |

**Detalle de seguridad:** el `server.proxy` existe **solo** en el servidor de desarrollo. `npm run build` no lo incluye en `dist/`. En producción no hay ningún proxy de Vite.

### 2.6 Desarrollo vs. producción: de dónde sale la URL de la API

| | Desarrollo (`npm run dev`) | Producción (CloudFront) |
|---|---|---|
| El frontend llama a | `/api/controls` (relativo) | `https://<api-id>.execute-api…/controls` |
| ¿Hay proxy? | Sí, el de Vite | No |
| ¿Cruza orígenes en el navegador? | No | **Sí**: CloudFront → API Gateway, y CORS lo **permite** porque el origen es el dominio de CloudFront (D28) |
| La URL real de la API se toma de | `API_PROXY_TARGET` en `frontend/.env.local` (ignorado por git), solo para el proxy | `VITE_API_URL`, definida **al compilar** en CloudShell con el valor de `aws apigatewayv2 get-apis`. Nunca se versiona |

La URL de la API **no es un secreto**: en producción queda dentro del JavaScript compilado y cualquiera la ve con F12 (Etapa 5). La razón para no escribirla en el código es otra: **es configuración de cada despliegue**. En el modelo self-hosted (D48), cada usuario tiene **su propia** API. Y además, el chequeo de identificadores del CI (D62) frenaría el commit.

> **Relación con D30:** en la Etapa 5 quedó como mejora posible servir la API **bajo el mismo dominio de CloudFront** (`/api/*`). Sería el mismo patrón del proxy de Vite, pero en producción: CloudFront como reverse proxy hacia API Gateway, sin CORS. Por ahora seguimos con orígenes distintos y CORS restringido.

### 2.7 Rutas de la SPA en CloudFront

Al recargar `/app/controles`, CloudFront le pide a S3 la clave `app/controles`, que no existe. Como el bucket es privado y CloudFront no tiene `s3:ListBucket`, **S3 responde 403**, no 404 (Etapa 3). Solución (D67): *error pages* de CloudFront que, ante un 403 o 404, devuelven `/index.html` con **200**. React lee la URL y dibuja la pantalla. Consecuencia: cualquier ruta inexistente devuelve la app, y la página "No encontrado" la resuelve React.

### 2.8 Caché: nombres con hash

| Archivo | Nombre | `Cache-Control` | Por qué |
|---|---|---|---|
| `assets/*.js`, `assets/*.css` | Incluye un hash del contenido (`index-a1b2c3.js`) | `public, max-age=31536000, immutable` | Un archivo con ese nombre nunca cambia: se puede cachear un año |
| `index.html` | Siempre igual | `no-cache` | Indica qué `.js` cargar; tiene que ser siempre el vigente |

Con cada deploy, solo hay que invalidar `/index.html`. Resuelve por diseño el problema de caché de la Etapa 3.

### 2.9 Seguridad del frontend

| Riesgo | Mitigación |
|---|---|
| **XSS**: mostrar texto que escribió un usuario (por ejemplo, el `title` de un control) | React escapa el texto por defecto. Prohibido `dangerouslySetInnerHTML` con datos de la API |
| Secretos en el frontend | No hay: todo lo compilado es público. La seguridad está en la API (Cognito, Etapa 9; throttling) |
| Relajar CORS para desarrollar | Proxy de Vite (2.4) |
| Supply chain de npm | `package-lock.json`, `npm ci` y `npm audit` en el CI |
| ID de la cuenta en la UI sin autenticación | Se muestra recién con Cognito (Etapa 9) |

## 3. Decisiones técnicas

| # | Decisión | Detalle |
|---|---|---|
| D64 | Modelo de cuentas | V1 self-hosted: sin flujo de "conectar cuenta"; la UI muestra la región (y la cuenta, con login) |
| D65 | Stack | React + Vite + TypeScript + Tailwind CSS + shadcn/ui; app bajo `/app` ([ADR-006](architecture-decisions/006-frontend-spa.md)). **Superada por D75/D76: Cloudscape Design System.** |
| D66 | Landing | Cuando el producto se pueda instalar (Etapa 16); hasta entonces `/` → `/app` |
| D67 | Rutas de la SPA | Error pages de CloudFront (403/404 → `/index.html`, 200) |
| D68 | Dependencias npm | Versiones exactas, ≥ 14 días de publicadas, `ignore-scripts`, lockfile; CLIs con `npx`, no como dependencia |
| D69 | Contrato de la API | `backend/openapi.yaml` (OpenAPI 3.1) + Swagger UI solo en desarrollo |
| D70 | Datos remotos | TanStack Query |
| D71 | Identidad visual | Oscuro por defecto, teal, colores semánticos con texto o ícono. **Parcialmente superada por D76: el teal pasa al theming de Cloudscape; el modo oscuro y los colores semánticos siguen.** |
| D72 | Tabla | Table de shadcn; filtros, búsqueda y orden en el cliente. **Superada por D75: `Table` + `useCollection` de Cloudscape.** |
| D73 | Formulario | Estado y validación propios (espejo de `FIELD_RULES`); errores del backend en el campo |

## 4. Configuración realizada

### 4.1 Paso 8.1 — Proyecto base (2026-10-15)

Archivos escritos a mano, sin `npm create vite`, para controlar las versiones y no ejecutar un paquete generador más:

| Archivo | Para qué |
|---|---|
| `frontend/package.json` | Dependencias con versión exacta y scripts: `dev`, `typecheck` (`tsc --noEmit`), `build` (`tsc --noEmit && vite build`), `preview` |
| `frontend/.npmrc` | `save-exact=true` (sin `^`) e `ignore-scripts=true` (no ejecutar scripts de instalación de terceros) |
| `frontend/package-lock.json` | Árbol completo con hashes de integridad: `npm ci` instala exactamente esto |
| `frontend/tsconfig.json` | TypeScript estricto, `moduleResolution: bundler`, alias `@/* → src/*` |
| `frontend/vite.config.ts` | Plugins de React y Tailwind, alias `@`, proxy `/api` **solo si** existe `API_PROXY_TARGET` |
| `frontend/.env.example` | Plantilla versionada con el marcador `<api-id>`; la real es `.env.local` (ignorada) |
| `frontend/index.html`, `src/main.tsx`, `src/App.tsx`, `src/index.css` | Punto de entrada; pantalla temporal que se reemplaza en el paso 8.3 |
| `frontend/components.json`, `src/lib/utils.ts`, `src/components/ui/button.tsx` | Generados por `npx shadcn@4.21.1 init -t vite -b radix` |
| `frontend/src/styles/shadcn-tailwind.css` | CSS de shadcn (animaciones y variantes), **copiado** del paquete con nota de licencia MIT (D68) |

**Dependencias** (todas con ≥ 14 días de publicadas al 2026-10-15):

| Paquete | Versión | Tipo | Para qué |
|---|---|---|---|
| `react`, `react-dom` | 19.3.0 | runtime | UI |
| `react-router` | 8.4.0 | runtime | Rutas `/app/...` |
| `radix-ui` | 1.6.7 | runtime | Primitivas accesibles de los componentes |
| `class-variance-authority` | 0.7.1 | runtime | Variantes de componentes (tamaño, estilo) |
| `cn` | 0.4.0 | runtime | Combinar clases de Tailwind (reemplazo de `clsx` + `tailwind-merge`, publicado por shadcn; repo `shadcn-ui/cn`, creado en 2026-08: **joven, a vigilar**) |
| `lucide-react` | 1.49.0 | runtime | Íconos |
| `vite` | 8.3.2 | dev | Servidor de desarrollo y build |
| `@vitejs/plugin-react` | 6.1.1 | dev | JSX y recarga en caliente |
| `typescript` | 7.0.2 | dev | Tipos (`tsc`) |
| `tailwindcss`, `@tailwindcss/vite` | 4.3.3 | dev | Estilos |
| `tw-animate-css` | 1.4.0 | dev | Animaciones de los componentes |
| `@types/react`, `@types/react-dom` | 19.3.0 | dev | Tipos de React |
| `@types/node` | 24.19.1 | dev | Tipos de Node 24 (para `vite.config.ts`) |

`shadcn init` había agregado `lucide-react` 1.57.0, `radix-ui` 1.8.1 y `shadcn` 4.21.5, publicados hace 1 a 3 días. Se bajaron a las versiones de la tabla.

**Verificación:**

| Qué | Resultado |
|---|---|
| `npx tsc --version` | 7.0.2 |
| `npm run build` | OK: `index.html` 0,39 kB · CSS 18,5 kB · JS 255,5 kB (83 kB gzip) |
| Copiar el CSS de shadcn en vez de importarlo del paquete | Mismo hash del CSS compilado antes y después: resultado idéntico |
| `npm audit` | **0 vulnerabilidades** (antes de sacar el CLI de shadcn: 7 *high*, todas vía `braces`) |
| `npm run dev` | Sirve la app en `localhost`; inyecta `/@vite/client` y `/@react-refresh` (solo en desarrollo) |
| `scripts/check_identifiers.py` | OK sobre los archivos nuevos, incluido `package-lock.json` |

### 4.2 Paso 8.2 — Cliente de la API y proxy (2026-10-16)

| Archivo | Para qué |
|---|---|
| `frontend/src/lib/api.ts` | **Único** lugar del frontend que hace `fetch()`. Tipos del contrato (`Control`, `ControlInput`, `ControlPatch`, `Severity`, `Status`), clase `ApiError` con el status HTTP, y las 5 operaciones del CRUD |
| `frontend/src/vite-env.d.ts` | Tipa `import.meta.env.VITE_API_URL` |
| `frontend/.env.local` (no versionado) | `API_PROXY_TARGET` con la URL real de la API, creado por el usuario |

Decisiones de diseño del cliente:

| Detalle | Por qué |
|---|---|
| `BASE_URL = VITE_API_URL ?? "/api"` | Sin `VITE_API_URL` (desarrollo), las rutas son relativas y pasan por el proxy; en producción, la URL real |
| `Content-Type: application/json` **solo** si hay body | Un `GET` sin headers extra es una *simple request*: el navegador no hace preflight |
| Mensaje de error: `error` (backend) o `message` (API Gateway) | Los errores del backend son `{"error": ...}`; los de API Gateway (404 de ruta, 429, 500) son `{"message": ...}` |
| `ApiError(0, ...)` si `fetch()` lanza | `fetch()` solo lanza cuando **no hubo respuesta**: sin red, DNS o **un bloqueo de CORS del navegador**. Un 4xx/5xx **no** lanza: hay que mirar `response.ok` |
| `encodeURIComponent(id)` | Un id con caracteres raros no puede alterar la ruta |

**Verificación:**

| Prueba | Resultado |
|---|---|
| Preflight simulado desde `Origin: http://localhost:5173` contra la API real | `204` **sin** `access-control-allow-origin`: un navegador bloquearía |
| `GET` desde un programa (Node) con el mismo `Origin` | `200`, `count: 3`: la API responde igual. **CORS no es un firewall** |
| `GET /api/controls` vía el proxy de Vite | `200`, `count: 3`, con `apigw-requestid` (respondió API Gateway) |
| `GET /api/controls/abc` vía el proxy | `400` con el mensaje del backend |
| `GET /app/controles` en el servidor de desarrollo | Devuelve `index.html`: el servidor de desarrollo de Vite ya hace el *fallback* de SPA. **En producción no**: S3 + CloudFront necesitan las error pages (D67) |
| `npm run typecheck` | OK |

### 4.3 Paso 8.2b — Contrato OpenAPI y Swagger UI de desarrollo (2026-10-16)

**Qué son:** **OpenAPI** es un archivo que describe la API (rutas, bodies, respuestas, errores). **Swagger UI** es una página que lo dibuja como documentación y permite probar cada endpoint ("Try it out"). El contrato pertenece a la **API** (backend); la página es solo una forma de verlo.

| Archivo | Para qué |
|---|---|
| `backend/openapi.yaml` | El contrato (OpenAPI 3.1): 5 operaciones, schemas `Control`, `ControlInput`, `ControlPatch`, errores del backend (`{"error"}`) y de API Gateway (`{"message"}`: 429, 500). Servidores: `/api` (proxy de desarrollo) y `https://{apiId}.execute-api…` con el marcador `<api-id>` |
| `frontend/swagger.html` + `src/dev/swagger.ts` | Página de Swagger UI. Vite la sirve en `http://localhost:5173/swagger.html` con `npm run dev`. **No entra al build**: el build solo incluye `index.html` |
| `frontend/vite.config.ts` → plugin `openApiDevServer` | Sirve `backend/openapi.yaml` en `/openapi.yaml`. `configureServer` solo corre en desarrollo |
| `frontend/src/dev/swagger-ui-dist.d.ts` | Tipos mínimos (el paquete no trae) |

**Decisiones del contrato:**

- `security: []` **explícito**: la API no tiene autenticación (hallazgo H4). Declararlo hace que sea una decisión visible y no un olvido. Con Cognito (Etapa 9) se agrega un esquema JWT.
- Los campos desconocidos se documentan como **ignorados** (allowlist, D49), y los textos obligatorios con `minLength: 1` (no vacíos tras el `strip`).
- `DELETE` documenta el 409 futuro por findings (D40).

**Un ajuste en el proxy:** la clave pasó de `"/api"` a `"/api/"`. Un prefijo sin barra también captura rutas como `/api-docs`, que se habrían reenviado a la API por error.

**Supply chain:** `swagger-ui-dist` 5.33.1 (devDependency) depende de `@scarf/scarf`, cuyo `postinstall` envía telemetría de instalación. Con `ignore-scripts=true` (D68) ese script **no se ejecuta**.

**Verificación:**

| Prueba | Resultado |
|---|---|
| `npx @redocly/cli@2.57.0 lint backend/openapi.yaml` | Primero: 5 errores `security-defined` (la API sin auth). Con `security: []` explícito: **válido, sin advertencias** |
| `npm run build` | Mismos hashes que antes: Swagger **no** entra al bundle; `dist/` sin rastros |
| Servidor de desarrollo: `/swagger.html`, `/openapi.yaml`, `/src/dev/swagger.ts`, `/api/controls` | 200 en todos (YAML con `application/yaml`; el proxy sigue funcionando con la clave `/api/`) |
| Chrome headless sobre `/swagger.html` | Swagger UI dibuja los 5 endpoints, los schemas y el servidor `/api` |
| `npm audit` / chequeo de identificadores | 0 vulnerabilidades / OK |

**Por qué el servidor de producción no funciona desde Swagger:** primero, su variable `apiId` vale el marcador `<api-id>` (el contrato es público). Pero aunque se ponga el ID real, la request la hace **el navegador** directo desde `localhost:5173` a la API, y CORS solo autoriza el dominio de CloudFront: el navegador la bloquea (*"Failed to fetch"*). El `curl` que muestra Swagger, en cambio, funciona en una terminal: quien llama es un programa. Para probar desde Swagger se usa el servidor `/api` (el proxy). La entrada de producción queda **solo como referencia**, y su descripción lo aclara.

**Pendiente:** lintear el contrato en el CI. Estaba previsto para el paso 8.6, pero **no se incluyó** (el 8.6 cubrió `npm ci`, `typecheck`, `build` y `audit`); queda [PENDIENTE], sin etapa asignada. Más adelante (Etapa 14): generar los tipos del frontend desde el contrato y verificar que el backend lo respeta.

### 4.4 Paso 8.3 — Layout, rutas y tema (2026-10-17)

> **Parcialmente reemplazado por §4.7 y §4.8 (D75/D76):** `SidebarNav.tsx`, `ThemeToggle.tsx`, `PageHeader.tsx`, `src/index.css` y los componentes `ui/*` de shadcn ya no existen. El layout actual está en `AppLayout.tsx` con `AppLayoutToolbar`, `SideNavigation` y `TopNavigation` de Cloudscape, más `split-panel.tsx` y `brand-theme.ts`. Lo que sigue se conserva como historial del paso 8.3.

```text
main.tsx:  <ThemeProvider> → <QueryClientProvider> → <RouterProvider router={router} />

router.tsx:  /                → <Navigate to="/app">   (la landing va acá, D66)
             /app             → <AppLayout> ─┬─ index      → DashboardPage   (placeholder hasta 8.5)
                                             ├─ controles  → ControlsPage    (placeholder hasta 8.4)
                                             └─ *          → NotFoundPage
             *                → NotFoundPage
```

| Archivo | Para qué |
|---|---|
| `src/router.tsx` | Rutas con React Router (`createBrowserRouter`) |
| `src/components/layout/AppLayout.tsx` | Menú lateral (escritorio) o en `Sheet` (móvil), barra superior con la región y el tema, `<Outlet />` para cada página, enlace "Saltar al contenido" |
| `src/components/layout/SidebarNav.tsx` | Marca y navegación (`NavLink` marca la página activa y pone `aria-current`). Solo lo que existe: Findings y Score aparecen en la Etapa 11 |
| `src/components/layout/ThemeToggle.tsx`, `src/lib/theme.tsx` | Tema claro/oscuro: desde D75, `applyMode` de Cloudscape agrega `awsui-dark-mode` en `<body>` (no una clase `dark` en `<html>`; ver §4.7), recordado en `localStorage` (con `try/catch`: puede no estar disponible) |
| `index.html` (script en `<head>`) | Aplica el tema **antes** de dibujar, para evitar el parpadeo claro → oscuro |
| `src/index.css` | Variables de color de D71: marca teal, fondo oscuro con leve tinte azulado |
| `src/lib/query-client.ts` | TanStack Query: datos frescos 30 s, sin recargar al volver a la pestaña, **sin reintentos en 4xx** (un 400/404/409 no se arregla repitiendo; un 429 es el throttling), 1 reintento en red o 5xx |
| `src/lib/config.ts` | `AWS_REGION` (de `VITE_AWS_REGION`, por defecto `us-east-1`) y el link al repo. El ID de cuenta **no** se muestra hasta Cognito (D64) |
| `src/pages/*.tsx` | Dashboard y Controles (por ahora, placeholders honestos) y la página 404 |
| `src/components/ui/sheet.tsx`, `badge.tsx` | `npx shadcn@4.21.1 add sheet badge`. No sumaron dependencias (usan Radix, que ya estaba) |

Dependencia nueva: `@tanstack/react-query` **5.104.1** (publicada el 2026-10-02; depende solo de `@tanstack/query-core`; acepta React 18/19).

**Verificación:**

| Prueba | Resultado |
|---|---|
| `npm run build` (incluye `tsc`) | OK · JS 427 kB (137 kB gzip) · CSS 29 kB |
| Chrome headless: `/` | Redirige a `/app`, con "Dashboard" activo en el menú |
| Chrome headless: `/app/controles` | "La API respondió con 3 controles": TanStack Query → cliente → proxy → API |
| Chrome headless: `/app/no-existe` | Página 404 dentro del layout |
| Móvil (390 px) | Todo entra. La primera captura salió recortada porque **Chrome headless tiene un ancho mínimo de ventana** (~500 px); dibujando la app en un `<iframe>` de 390 px se confirmó que no era un problema de la app |
| Tema claro (`localStorage = "light"`) | Colores claros y el ícono de luna |
| `npm audit` / chequeo de identificadores | 0 vulnerabilidades / OK |
| **No verificado** | Abrir el menú móvil (`Sheet`) con un clic: requiere interacción |

**Ícono de la app (2026-10-17):** `frontend/public/favicon.svg` (escudo con check, la forma `shield-check` de Lucide, licencia ISC, en teal sobre el fondo de la marca `#0b1524`) y `frontend/public/apple-touch-icon.png` (180×180, opaco: iOS redondea los íconos y rellena de negro las esquinas transparentes), generado renderizando el SVG con Chrome headless. `index.html` los referencia y define `theme-color`. `public/` se copia tal cual a `dist/` (sin hash en el nombre: al desplegar, conviene invalidarlos si cambian). Verificado: legible a 16 px en barras claras y oscuras; servidos con `image/svg+xml` e `image/png`; presentes en `dist/`.

### 4.5 Paso 8.4 — Página de Controles (2026-10-17, rama `feat/pagina-controles`)

> **Reemplazado por §4.8 (D75):** `ControlsTable.tsx`, `ControlFormSheet.tsx`, `DeleteControlDialog.tsx` y los componentes `ui/*` de shadcn ya no existen. Hoy la pantalla usa `ControlsPage.tsx` + `ControlDetails.tsx` + `split-panel.tsx`, `ControlFormPage.tsx` y `DeleteControlModal.tsx` (Cloudscape). Lo que sigue se conserva como historial del paso 8.4.

| Archivo | Para qué |
|---|---|
| `src/lib/control-rules.ts` | Espejo de `FIELD_RULES` (D73): validación previa al envío y armado del body (`trim`, opcionales vacíos omitidos en el `POST`) |
| `src/lib/use-controls.ts` | Hooks de TanStack Query: listar, crear, editar (con **actualización optimista** y rollback si la API falla) y borrar; toda mutación refresca la lista |
| `src/components/controls/badges.tsx` | Severidad y estado con color **más texto e ícono** (D71); orden por severidad |
| `src/components/controls/ControlsTable.tsx` | Tabla (D72); estado editable desde la tabla; menú de acciones (editar, eliminar). En móvil, el código y la severidad pasan dentro de la celda del control |
| `src/components/controls/ControlFormSheet.tsx` | Crear y editar en un panel lateral. En edición, el `PATCH` lleva **solo los campos que cambiaron**. Un 409 se muestra en el campo Código; otros errores, arriba del botón |
| `src/components/controls/DeleteControlDialog.tsx` | Confirmación de borrado |
| `src/pages/ControlsPage.tsx` | Búsqueda y filtros en el cliente, contador, estados de carga (skeleton), error (con reintento), vacío y "sin coincidencias" |
| `src/components/ui/{table,input,label,textarea,select,alert-dialog,dropdown-menu,skeleton,sonner}.tsx` | `npx shadcn@4.21.1 add …`. Sumó `sonner` 2.0.8 (notificaciones, 2026-08-09) y `next-themes`; este último se **sacó**: `sonner.tsx` usa nuestro `useTheme` |

**Verificación:** build y tipos OK; `npm audit` 0; chequeo de identificadores OK; Chrome headless: tabla con los 3 controles, badges y filtros en escritorio y en móvil (390 px). El bundle pasó a 563 kB (175 kB gzip) y Vite avisa que supera 500 kB: se resuelve en el 8.5 con carga de páginas bajo demanda.

**No verificado automáticamente** (requiere interacción): crear, editar, cambiar el estado, borrar, el 409 en el campo y el rollback optimista. Prueba manual:

| # | Acción | Esperado |
|---|---|---|
| 1 | Crear un control `TEST-UI` válido | Notificación "creado" y aparece en la tabla |
| 2 | Crear otro con código `S3-001` | Error del backend (409) **debajo del campo Código** |
| 3 | Enviar el formulario vacío | Errores en los obligatorios, sin llamar a la API |
| 4 | Cambiar el estado desde la tabla | El badge cambia al instante y aparece la notificación |
| 5 | Editar el título de `TEST-UI` | Solo se envía `title` (DevTools → Network → body del `PATCH`) |
| 6 | Eliminar `TEST-UI` | Diálogo de confirmación; desaparece de la tabla |
| 7 | Buscar y filtrar | El contador "X de N" cambia; "Limpiar filtros" si no hay coincidencias |

### 4.6 Paso 8.5 — Dashboard y carga bajo demanda (2026-10-17, rama `feat/dashboard`)

- `src/pages/DashboardPage.tsx`: tarjetas (total y por estado), **cumplimiento declarado** (% de "Cumple", barra apilada con leyenda numérica), distribución **por severidad** con cuántos no cumplen, y "Para resolver primero" (los "No cumple", ordenados por severidad). Todo se calcula en el cliente con `GET /controls`, compartiendo la caché de TanStack Query con la página de Controles. Es el estado **declarado a mano**: el score real, basado en checks automáticos, llega en la Etapa 11.
- Las tarjetas y las severidades son **links con filtro** (`/app/controles?estado=FAIL`, `?severidad=HIGH`); `ControlsPage` toma los filtros iniciales de la URL (solo valores válidos).
- **Carga bajo demanda** (`lazy` de React Router): cada página es un archivo aparte que se baja al entrar a su ruta. Bundle inicial: 563 kB → **456 kB** (145 kB gzip); Dashboard 5,6 kB; Controles 95 kB. Desaparece el aviso de Vite de 500 kB.

**Ajuste del tema claro:** los bordes no se veían (`--border` con luminosidad 0,91 sobre un fondo de 0,985 y tarjetas blancas). Se oscurecieron `--border` y `--sidebar-border` a 0,86 e `--input` a 0,83, y el fondo bajó a 0,975, para que las tarjetas blancas se despeguen. El tema oscuro no cambió.

**Verificación:** build, tipos, `npm audit` 0 y chequeo de identificadores OK; Chrome headless: totales correctos con los datos reales (3 controles: 0/2/1) y `?estado=REVIEW` abre Controles filtrado ("2 de 3").

### 4.7 Migración a Cloudscape (2026-10-17, rama `feat/ui-cloudscape`, D75–D76)

**Por qué:** el usuario quiso la estética de la consola de AWS, a partir de la demo de Refraxion (una herramienta de *posture review* hecha con Cloudscape). Se adoptó **Cloudscape Design System**, el sistema de diseño open source de AWS (Apache-2.0), en lugar de imitarlo con shadcn. Se toman la librería y los patrones, no la marca ni los textos de Refraxion.

| Se conservó | Se reemplazó |
|---|---|
| `api.ts`, `use-controls.ts` (TanStack Query, optimista), `control-rules.ts`, `query-client.ts`, `config.ts`, `router.tsx` (carga bajo demanda), el proxy y el contrato | shadcn/ui, Tailwind, Radix, lucide, sonner → `AppLayout` + `TopNavigation` + `SideNavigation` + `BreadcrumbGroup`, `Table` + `useCollection` (búsqueda, orden, paginación, selección), `Modal` + `Form`, `Flashbar`, `Badge` de severidad, `StatusIndicator`, `ProgressBar`, `ContentLayout` |

**Versiones** (≥ 14 días, D68): `@cloudscape-design/components` 3.0.1391, `global-styles` 1.0.71, `collection-hooks` 1.0.110. `npm audit`: 0.

**Patrón de la consola en la tabla:** se **selecciona** un control y las acciones (Cambiar estado, Editar, Eliminar) se habilitan en el encabezado, como en la consola de AWS.

**Teal como acento (D76):** `src/lib/brand-theme.ts` usa `applyTheme` para cambiar solo los tokens de acento (botón primario, links, foco, progreso), con valores para claro y oscuro.

**Costo aceptado: el bundle.**

| | shadcn | Cloudscape |
|---|---|---|
| JS inicial | 456 kB (145 kB gzip) | 1.563 kB (367 kB gzip) |
| CSS inicial | 50 kB (9 kB gzip) | 849 kB (217 kB gzip: estilos de la consola y fuentes) |

Mitigación posible más adelante: separar Cloudscape en un chunk propio (se cachea entre versiones de la app). Con la caché de CloudFront y del navegador, se descarga una vez.

**Dos bugs encontrados al verificar:**

1. **El modo oscuro no se aplicaba.** La clase `awsui-dark-mode` estaba en `<html>`, pero Cloudscape define los colores en `<body>`: las variables del `<body>` ganaban. Se movió la clase a `<body>` (`applyMode` sin `target`, y el script anti-parpadeo al principio del `<body>`).
2. **El título "OpenAegis" se cortaba ("Open…").** `favicon.svg` no declaraba `width`/`height`: una imagen SVG solo con `viewBox` se trata como de 300×150 px y el logo aplastaba el título. Se agregaron `width="32" height="32"`.

**Verificación:** build y tipos OK, `npm audit` 0, 42 tests y chequeo de identificadores OK; Chrome headless: Controles y Dashboard en oscuro y claro, título completo, móvil a 390 px (menú en ☰, acciones en filas, tabla con desplazamiento horizontal). **No verificado automáticamente:** las interacciones (seleccionar, crear, editar, cambiar estado, borrar, notificaciones): requiere la prueba manual de §4.5.

### 4.8 Rediseño de la UI (2026-10-17, misma rama)

A partir de la revisión del usuario:

| Pedido | Cambio |
|---|---|
| Colores como antes | `brand-theme.ts` sobrescribe también **fondos, contenedores, inputs y bordes** con la paleta original (azul marino con tinte en oscuro, gris azulado en claro) y la barra superior con `#0b1524` en los dos temas (contexto `top-navigation`) |
| "OpenAegis" repetido, footer del menú | El menú lateral no tiene encabezado ni footer |
| Módulos del menú | Secciones: **Dashboard** · *Seguridad* → Controles (con contador) · *Ayuda* → Documentación, Reportar un problema |
| Ícono de GitHub doble, botón de tema | Un solo ícono; el tema pasa a un menú **Preferencias** (⚙) |
| Dashboard aburrido y con huecos | KPIs con íconos de estado, **torta** por estado (`PieChart`), **barras apiladas** severidad × estado (`BarChart`), "Para resolver primero" y "Actividad reciente" en una grilla de 6/6 |
| Listado | Columnas Servicio y Categoría, fechas relativas, código como link a la edición, menú **Acciones**, y un **panel de detalle** (`SplitPanel`) al seleccionar un control, con sus datos, descripción, remediación y acciones |
| Alta y edición | **Página completa** por secciones (Identificación, Evaluación, Detalle), severidad elegida en tarjetas (`Tiles`) con su explicación, estado con `SegmentedControl` y contador de caracteres. Rutas `/app/controles/nuevo` y `/app/controles/:id/editar`: la edición usa el dato de la caché o, si se entra por link directo, `GET /controls/{id}` (`useControl`) |

La tabla pasó de `variant="full-page"` (sin borde: "flotaba") a **`variant="container"`** dentro de un `ContentLayout` con el título de la página arriba, igual que la lista de buckets de la consola de S3.

El layout pasó de `AppLayout` a **`AppLayoutToolbar`** (el de la consola actual): la barra superior ocupa todo el ancho, debajo va una franja con el botón del menú y los breadcrumbs, y el menú lateral empieza recién ahí. La barra superior muestra el logo y el nombre. **Logo nuevo:** un escudo que también se lee como una "A". Su fuente es `brand/op-logo.svg` en la raíz del repo, vectorizado (negro sobre blanco). Está fuera de `frontend/public/` porque todo lo que hay ahí se publica con el sitio. De ahí salen tres archivos: `logo.svg` (solo el escudo en teal, sin fondo ni margen, para alinearlo con el botón del menú), `favicon.svg` (sobre fondo azul marino con esquinas redondeadas) y `apple-touch-icon.png` (180×180 con fondo completo, porque iOS redondea solo). El espacio a la izquierda del logo era el `padding` interno de 32 px de `TopNavigation`, que ningún token controla: se pisa en `src/styles/overrides.css` con un selector sobre una clase interna (`awsui_padding-box_*`). Es frágil: hay que revisarlo después de cada actualización de Cloudscape.

**Pie de página** fijo, como el de la consola: `© <año> OpenAegis`, Privacidad y Términos (`footerSelector` del layout para que el contenido no quede tapado). Las páginas legales están [PENDIENTE]: hasta que existan, sus links llevan a la 404. No hay "Preferencias de cookies" porque la app no usa cookies (solo `localStorage` para el tema). El menú lateral no repite el nombre: secciones desplegables "General" (Dashboard) y "Seguridad" (Controles). Los links de ayuda quedan fijos al pie del menú. Las preferencias del panel de detalle (abajo o al costado) ahora se guardan en estado: antes la posición estaba fija en `"bottom"` sin handler y el diálogo no tenía efecto.

Detalles de la verificación: la grilla de Cloudscape usa puntos de corte sobre el **ancho del contenido** (no de la ventana): con `m` los gráficos quedaban apilados y se pasó a `s`. Se ocultaron las etiquetas de la torta (se cortaban) y el eje Y del gráfico de barras muestra solo enteros.

**Verificación:** build y tipos OK, `npm audit` 0, 42 tests y chequeo de identificadores OK; Chrome headless: Dashboard en oscuro y claro, Controles y el formulario de alta. **No verificado automáticamente:** el panel de detalle (requiere seleccionar una fila) y el flujo completo de alta, edición y borrado.

### 4.9 Paso 8.6 — Job de frontend en el CI (2026-10-21, rama `feat/ci-frontend-job`, PR #5)

El job `checks` (el que exige el ruleset de `main`, D74) suma `npm ci`, `npm run typecheck`, `npm run build` y `npm audit` (bloqueante). Para que el `audit` pasara se subió `vite` 8.3.2 → 8.3.5, publicado ese mismo día: excepción a D68 registrada como **D77**. Configuración y motivos: [13a-ci-minimo.md §4.6](13a-ci-minimo.md).

### 4.10 Paso 8.7 — Error pages de CloudFront (2026-10-21, D67)

**Problema:** las rutas de la SPA (`/app/controles`, `/app/controles/<id>/editar`) solo existen en React Router. Al recargar o entrar por un link directo, CloudFront le pide a S3 una clave que no existe y, como CloudFront tiene `s3:GetObject` pero **no** `s3:ListBucket` (Etapa 3), S3 responde **403** en lugar de 404 para no permitir la enumeración. Resultado: la SPA nunca carga.

**Configuración** [CONVERSACIÓN] (consola → CloudFront → `cloud-sec-checklist-frontend` → *Error pages* → *Create custom error response*), dos respuestas iguales:

| HTTP error code | Response page path | HTTP Response code | Error caching minimum TTL | Por qué |
|---|---|---|---|---|
| 403 | `/index.html` | 200 | 10 s | Es lo que S3 devuelve hoy ante un objeto inexistente |
| 404 | `/index.html` | 200 | 10 s | Defensa en profundidad: si CloudFront tuviera `ListBucket`, S3 pasaría a responder 404 |

El código de respuesta tiene que ser **200**: con 403 el navegador recibe la app junto con un error.

**Evidencia** (CloudShell, `curl -sI` y `aws cloudfront get-distribution-config --id <distribution-id> --query 'DistributionConfig.CustomErrorResponses'`):

| Prueba | Antes | Después |
|---|---|---|
| `GET /` | `HTTP/2 200` | `HTTP/2 200` |
| `GET /app/controles` | `HTTP/2 403` | `HTTP/2 200`, con el `index.html` de prueba en el body (el build real llega en la 8.8) |
| `GET /no-existe.js` → `content-type` | — | `text/html`: la desventaja aceptada en ADR-006 |
| `CustomErrorResponses` | `Quantity: 0` | `Quantity: 2` (403 y 404 → `/index.html`, 200, TTL 10) |

**Consecuencias:** para CloudFront ya no hay 404. Cualquier ruta inexistente devuelve la app con 200; "No encontrado" lo resuelve React (`NotFoundPage`), y un control inexistente lo resuelve la API (404 de `GET /controls/{id}`). Sigue sin poder enumerarse el contenido del bucket. **Costo:** USD 0 (configuración gratuita; cada respuesta es una request normal de CloudFront).

**Cómo revertir:** *Error pages* → seleccionar cada respuesta → *Delete*. Verificación: `curl -sI <distribucion>/app/controles` vuelve a dar 403.

**Debugging en el camino:** en CloudShell, los marcadores `<distribucion>` y `<distribution-id>` hay que reemplazarlos enteros (bash lee `<` como redirección). El **ID** de la distribución (`E...`, va en `--id`) y el **dominio** (`d....cloudfront.net`, va en `curl`) son datos distintos: el ID en el `curl` no resuelve DNS y, con `-s`, curl no muestra el error (usar `-sS`); el dominio en `--id` da `Id format is invalid`. Para no confundirlos: `DIST=<distribution-id>` y `CF=https://$(aws cloudfront get-distribution --id $DIST --query 'Distribution.DomainName' --output text)`.

### 4.11 Paso 8.8 — Deploy de la SPA (2026-10-21, D79)

**Flujo** [CONVERSACIÓN]: build en la PC del usuario → `dist.zip` subido a CloudShell (*Actions → Upload file*) → `s3 sync`/`s3 cp` con `Cache-Control` por tipo de archivo → invalidación de `/` y `/index.html`.

**Por qué el build no se hace en CloudShell (D79):** `npm ci` y `vite build` ejecutan código de ~200 MB de dependencias de terceros. En CloudShell correrían con las credenciales de `AdministratorAccess` de la sesión; en la PC corren **sin credenciales de AWS** (D4). CloudShell solo ejecuta la CLI de AWS. Es la misma lógica que D59 (CI sin credenciales). Desventaja: un paso manual más (subir el zip), que desaparece con CDK (Etapa 12).

**1. Build (PowerShell, en `main` limpio):**

```powershell
cd frontend
$env:VITE_API_URL = "https://<api-id>.execute-api.us-east-1.amazonaws.com"   # mismo valor que API_PROXY_TARGET de .env.local
npm ci
npm run build
Remove-Item Env:VITE_API_URL
Select-String -Path dist\assets\index-*.js -Pattern "execute-api" -List   # verifica que la URL quedó en el build
tar.exe -a -c -f dist.zip -C dist .                                          # zip con rutas compatibles con Linux
```

`VITE_API_URL` se escribe **dentro del `.js` al compilar** (`src/lib/api.ts`). Sin ella, la app pediría `/api/...` a CloudFront y, por la regla de la 8.7, recibiría `index.html`.

**2. Subida (CloudShell):**

```bash
DIST=<distribution-id>
BUCKET=$(aws s3api list-buckets --query "Buckets[?starts_with(Name,'cloud-sec-checklist-frontend')].Name" --output text)
CF=https://$(aws cloudfront get-distribution --id $DIST --query 'Distribution.DomainName' --output text)

aws s3 ls s3://$BUCKET/ --recursive                                          # antes: solo index.html (de prueba)
aws apigatewayv2 get-apis --query 'Items[].CorsConfiguration.AllowOrigins'   # tiene que incluir $CF
aws s3 cp s3://$BUCKET/index.html ~/index-prueba.html                        # backup: no hay versioning (D10)
rm -rf ~/dist && mkdir ~/dist && unzip -q ~/dist.zip -d ~/dist

# Orden: assets → public/ → index.html
aws s3 sync ~/dist/assets s3://$BUCKET/assets --cache-control "public, max-age=31536000, immutable"
aws s3 sync ~/dist s3://$BUCKET --exclude "assets/*" --exclude "index.html" --cache-control "public, max-age=86400"
aws s3 cp   ~/dist/index.html s3://$BUCKET/index.html --cache-control "no-cache"

INV=$(aws cloudfront create-invalidation --distribution-id $DIST --paths "/" "/index.html" --query 'Invalidation.Id' --output text)
aws cloudfront wait invalidation-completed --distribution-id $DIST --id $INV
```

| Decisión (D79) | Por qué |
|---|---|
| `assets/*`: `public, max-age=31536000, immutable` | El nombre lleva el hash del contenido: un nombre dado nunca cambia |
| `index.html`: `no-cache` | Dice qué `.js` cargar; tiene que ser siempre el vigente |
| `favicon.svg`, `logo.svg`, `apple-touch-icon.png`: `public, max-age=86400` | Vienen de `public/` y **no tienen hash**: con `immutable` un logo nuevo no se vería nunca. Hueco del plan original de §2.8 |
| Orden assets → `index.html` | Si `index.html` llegara primero, podría apuntar a un `.js` que todavía no existe: S3 da 403, la regla de la 8.7 devuelve HTML y la pantalla queda en blanco (error de *MIME type*) |
| Sin `--delete` | Una pestaña abierta con el `index.html` anterior sigue pidiendo sus chunks bajo demanda (`ControlsPage-<hash-viejo>.js`, paso 8.5). Si se borraran, recibiría HTML y la página no cargaría. Costo: unos KB en S3 |
| Invalidar `/` y `/index.html` | Son dos claves de caché distintas: `/` se sirve por el *default root object* |

**Verificación** [CONVERSACIÓN]:

| Prueba | Resultado |
|---|---|
| CORS de la API | `AllowOrigins` incluye el dominio de CloudFront |
| `curl -sSI $CF/` | `content-type: text/html`, `cache-control: no-cache` |
| `<title>` | `OpenAegis` (antes: la página de prueba) |
| `curl -sSI $CF/assets/index-<hash>.js` | `content-type: text/javascript`, `cache-control: public, max-age=31536000, immutable` |
| `curl -sSI $CF/app/controles` | `HTTP/2 200` |
| Navegador | Dashboard con datos, requests a la API con 200 y sin errores de CORS, recarga en `/app/controles` OK, edición de un control OK |

El UUID del control en la URL de edición (`/app/controles/<uuid>/editar`) es esperable: identifica el recurso, no es un secreto. `uuid4` evita la enumeración, pero **no** es control de acceso: eso llega con Cognito (Etapa 9).

**Costo:** ≈ USD 0 (~20 `PUT` a S3; invalidación de 2 paths dentro de las 1.000 gratis por mes).

**Cómo revertir:**

```bash
aws s3 cp ~/index-prueba.html s3://$BUCKET/index.html
aws s3 rm s3://$BUCKET/assets --recursive        # ⚠️ permanente (sin versioning)
aws s3 rm s3://$BUCKET/favicon.svg; aws s3 rm s3://$BUCKET/logo.svg; aws s3 rm s3://$BUCKET/apple-touch-icon.png
aws cloudfront create-invalidation --distribution-id $DIST --paths "/*"
```

## 5. Plan de la etapa

| Paso | Qué | Toca AWS | Estado |
|---|---|---|---|
| 8.1 | Proyecto Vite + React + TS (en 8.1 se usaron Tailwind y shadcn/ui; reemplazados por Cloudscape en 8.5b) | No | ✅ 2026-10-15 |
| 8.2 | Cliente de la API tipado + proxy de desarrollo | No | ✅ 2026-10-16 |
| 8.2b | Contrato OpenAPI + Swagger UI solo en desarrollo (D69) | No | ✅ 2026-10-16 |
| 8.3 | Layout, menú, modo claro/oscuro (D71); `/` → `/app` | No | ✅ 2026-10-17 |
| 8.4 | Página Controles (tabla, filtros, CRUD, estados, notificaciones) | No | ✅ 2026-10-17 (interacciones: verificación manual pendiente) |
| 8.5 | Dashboard + carga de páginas bajo demanda | No | ✅ 2026-10-17 |
| 8.5b | Migración a Cloudscape y rediseño de la UI (D75/D76) | No | ✅ 2026-10-17 |
| 8.6 | Job de frontend en el CI (`npm ci`, `typecheck`, `build`, `audit`) | No | ✅ 2026-10-21 (PR #5): extiende el job `checks`; `vite` 8.3.2 → 8.3.5 por un fix HIGH (excepción D77). Detalle en [13a §4.6](13a-ci-minimo.md) |
| 8.7 | CloudFront: error pages (D67) | Sí (configuración, sin costo) | ✅ 2026-10-21: 403 y 404 → `/index.html` con 200; `/app/controles` pasó de 403 a 200. Detalle en §4.10 |
| 8.8 | Deploy (build local, `s3 sync` con caché desde CloudShell, invalidación) | Sí (escritura en S3) | ✅ 2026-10-21: SPA desplegada; build en la PC sin credenciales de AWS (D79). Detalle en §4.11 |
| 8.9 | Verificación en el navegador, checkpoint y cierre de este doc | — | Pendiente |
