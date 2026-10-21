# ADR-006: Frontend como SPA con React + Vite + TypeScript, servida desde S3 + CloudFront

- **Estado:** aceptada · **actualizada el 2026-10-17** (D75/D76): la librería de componentes pasó de shadcn/ui + Tailwind a **Cloudscape Design System**, con teal como acento. El resto de este ADR (SPA estática en S3 + CloudFront, React + Vite + TypeScript) sigue vigente. Ver [08-frontend.md §4.7](../08-frontend.md)
- **Fecha:** 2026-10-15 (inicio de la Etapa 8)
- **Decisiones relacionadas:** D64, D65, D66, D67, D75, D76 ([DECISIONS.md](../DECISIONS.md)) · cambia el alcance fijado en el prompt original · se apoya en [ADR-002](002-s3-cloudfront.md) y [ADR-005](005-deployment-model.md)

## Contexto

El prompt original pedía un frontend **deliberadamente simple** (HTML, CSS y JavaScript), para que el proyecto no se convirtiera en un proyecto de frontend. Al llegar a la Etapa 8 aparecieron requisitos nuevos:

- el producto va a evolucionar y va a tener **dos caras**: una **app** (dashboard, controles y, más adelante, findings, score y login con Cognito) y, cuando esté lista para usarse, una **landing** pública;
- es un proyecto de **portfolio**, y la UI es lo primero que ve quien entra;
- el usuario ya trabajó con **TypeScript y React/Next.js**.

La restricción que se mantiene: no sumar servicios ni costos de AWS solo por el frontend.

## Decisión

El frontend pasa a ser una **SPA** (*single-page application*) hecha con **React + Vite + TypeScript**, estilada con **Cloudscape Design System** y **teal como acento** (D75/D76; la elección original de Tailwind CSS + shadcn/ui, D65, quedó superada). Se compila a **archivos estáticos** y se sirve desde **el mismo bucket S3 privado detrás de CloudFront** (ADR-002). La app vive bajo la ruta `/app`; la raíz `/` queda reservada para la landing, que se construye **cuando el producto se pueda instalar y usar** (D66).

## Por qué

- Un frontend estático encaja con la arquitectura actual: **ningún servicio nuevo de AWS y ningún costo nuevo**.
- React resuelve bien lo que la app necesita: estado, formularios, tablas, filtros y diálogos. Hacerlo a mano en JavaScript crece mal.
- Vite compila rápido y genera archivos estáticos con nombres que incluyen un hash del contenido, lo que simplifica la caché en CloudFront.
- shadcn/ui **copia** los componentes al repo, en vez de agregar una librería de componentes como dependencia: el código queda a la vista y es modificable. *(Elección original de D65; reemplazada por Cloudscape en D75/D76.)*
- TypeScript tipa el contrato con la API (los campos de un control) y detecta errores al compilar.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| HTML, CSS y JavaScript sin framework (plan original) | Una UI cuidada, con estado, formularios y tablas, cuesta mucho más y escala mal |
| Next.js con *static export* | Mejor SEO para una landing, pero muchas funciones de Next (SSR, API routes, middleware) no funcionan exportadas, y usarlas de verdad requiere servidor (Lambda o Amplify): otro cambio de arquitectura |
| Next.js con SSR (Amplify Hosting o Lambda) | Suma servicios, costo y superficie de ataque para una app que no necesita renderizar en el servidor |
| Astro (landing) + React (app) | Bueno para landing + app, pero son dos paradigmas; se puede reevaluar cuando se construya la landing |

## Ventajas

- UI cuidada y mantenible.
- Sin cambios en AWS: sigue siendo S3 + CloudFront con OAC.
- Tipos compartidos con el contrato de la API.
- Separación clara: el frontend es un cliente más de la API (como `curl` o una futura CLI).

## Desventajas

- **Supply chain:** `npm` trae cientos de paquetes de terceros. Mitigación: `package-lock.json` versionado, `npm ci` y `npm audit` en el CI.
- **Paso de build:** ya no se sube el HTML tal cual. Hay que compilar, en el CI para verificar y en CloudShell para desplegar, hasta que llegue CDK.
- **Rutas del lado del cliente:** al recargar `/app/...`, S3 no tiene un objeto con esa clave. Hay que configurar CloudFront para que devuelva `index.html`, y eso también enmascara los 404 reales (los resuelve el router de la app).
- **SEO:** una SPA es peor para una landing que HTML generado. Se reevalúa cuando se construya la landing.
- Más conceptos para el usuario (React, bundler, Cloudscape), en un proyecto cuyo foco es AWS.

## Consideraciones de seguridad

- **XSS:** React escapa el texto por defecto; queda prohibido `dangerouslySetInnerHTML` con datos de la API.
- **La URL de la API** va en `.env.local` (ignorado por git), no en el código. El chequeo de identificadores del CI (D62) cubre también el frontend.
- **Sin secretos en el frontend:** todo lo que se compila es público (se ve con F12). La seguridad la dan la API, Cognito (Etapa 9) y el throttling.
- **CORS no se relaja para desarrollar:** en local se usa el proxy de desarrollo de Vite; `localhost` no se agrega al CORS de producción.
- **Datos de la cuenta en la UI:** mostrar el ID de la cuenta evaluada mientras la API no tenga autenticación lo expondría a cualquiera con la URL. Se muestra recién con Cognito (Etapa 9).

## Consideraciones de costo

Sin costo nuevo en AWS: el build es un conjunto pequeño de archivos estáticos dentro del Free Tier de CloudFront y S3 (ADR-002). El CI de GitHub Actions es gratis para el repo público. El build y el deploy desde CloudShell no tienen costo.

## Consecuencias

- `frontend/` pasa a ser un proyecto de Vite (con `package.json`); el `index.html` de prueba se reemplaza.
- CloudFront necesita una respuesta de error personalizada (o una alternativa equivalente) para las rutas de la SPA.
- El CI suma un job de frontend: instalar dependencias, verificar tipos, compilar y auditar dependencias.
- El despliegue del frontend es: build → `aws s3 sync` → invalidación de CloudFront (desde CloudShell hasta que llegue CDK).

## Evolución futura

- **Landing** en `/` cuando el producto se pueda instalar (con el comando de instalación y el link al repo, D66). Ahí se decide si va dentro de la SPA o como sitio estático aparte.
- **Gráficos** del score y de los findings en la Etapa 11.
- **Login** con Cognito en la Etapa 9.
- Si el producto evolucionara a SaaS (modelo B, revisión V1 → V2), la SPA suma una sección "Cuentas conectadas" sin cambiar de stack.
