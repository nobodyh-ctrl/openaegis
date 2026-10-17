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
| D65 | Stack | React + Vite + TypeScript + Tailwind CSS + shadcn/ui; app bajo `/app` ([ADR-006](architecture-decisions/006-frontend-spa.md)) |
| D66 | Landing | Cuando el producto se pueda instalar (Etapa 16); hasta entonces `/` → `/app` |
| D67 | Rutas de la SPA | Error pages de CloudFront (403/404 → `/index.html`, 200) |
| D68 | Dependencias npm | Versiones exactas, ≥ 14 días de publicadas, `ignore-scripts`, lockfile; CLIs con `npx`, no como dependencia |
| D69 | Contrato de la API | `backend/openapi.yaml` (OpenAPI 3.1) + Swagger UI solo en desarrollo |
| D70 | Datos remotos | TanStack Query |
| D71 | Identidad visual | Oscuro por defecto, teal, colores semánticos con texto o ícono |

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

**Pendiente (paso 8.6):** lintear el contrato en el CI. Más adelante (Etapa 14): generar los tipos del frontend desde el contrato y verificar que el backend lo respeta.

## 5. Plan de la etapa

| Paso | Qué | Toca AWS | Estado |
|---|---|---|---|
| 8.1 | Proyecto Vite + React + TS, Tailwind y shadcn/ui | No | ✅ 2026-10-15 |
| 8.2 | Cliente de la API tipado + proxy de desarrollo | No | ✅ 2026-10-16 |
| 8.2b | Contrato OpenAPI + Swagger UI solo en desarrollo (D69) | No | ✅ 2026-10-16 |
| 8.3 | Layout, menú, modo claro/oscuro (D71); `/` → `/app` | No | Pendiente |
| 8.4 | Página Controles (tabla, filtros, CRUD, estados, notificaciones) | No | Pendiente |
| 8.5 | Dashboard | No | Pendiente |
| 8.6 | Job de frontend en el CI | No | Pendiente |
| 8.7 | CloudFront: error pages (D67) | Sí (configuración, sin costo) | Pendiente |
| 8.8 | Deploy desde CloudShell (build, `s3 sync` con caché, invalidación) | Sí (escritura en S3) | Pendiente |
| 8.9 | Verificación en el navegador, checkpoint y cierre de este doc | — | Pendiente |
