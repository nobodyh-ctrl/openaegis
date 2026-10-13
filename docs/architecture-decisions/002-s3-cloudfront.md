# ADR-002: Frontend estático en S3 privado detrás de CloudFront con OAC

- **Estado:** aceptada
- **Fecha:** 2026-10-02 (Etapas 2–3)
- **Decisiones relacionadas:** D9–D17 ([DECISIONS.md](../DECISIONS.md))

## Contexto

La V1 necesita un frontend **deliberadamente simple** (HTML, CSS y JavaScript) para ver, crear, editar y borrar controles. No hay renderizado del lado del servidor: son archivos estáticos que el navegador descarga y que después llaman a la API. Tiene que servirse por **HTTPS**, sin exponer públicamente el almacenamiento, y con un costo cercano a cero.

## Decisión

Los archivos del frontend viven en un **bucket S3 privado** (Block Public Access 4/4, ACLs desactivadas, SSE-S3). Se sirven **únicamente** a través de una distribución de **CloudFront** que accede al bucket con **Origin Access Control (OAC)**. HTTP redirige a HTTPS, el dominio es `*.cloudfront.net`, sin WAF y sin logging.

## Por qué

- El bucket nunca es público: solo CloudFront puede leerlo, y la bucket policy lo restringe a **esta** distribución (`AWS:SourceArn`).
- HTTPS incluido, sin comprar un dominio ni gestionar certificados.
- Caché en el edge: menos requests a S3 y respuestas más rápidas.
- Es el patrón recomendado por AWS para sitios estáticos.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| S3 **static website hosting** público | Obliga a desactivar Block Public Access y a escribir una bucket policy pública; el endpoint `s3-website` no tiene HTTPS |
| **OAI** (Origin Access Identity) | Mecanismo legacy; OAC es el recomendado (D13) |
| AWS Amplify Hosting | Abstrae lo que el proyecto quiere aprender (S3, CloudFront, policies) |
| GitHub Pages / Netlify | Saca el frontend de AWS; no ejercita IAM ni resource-based policies |
| Flat-rate plan de CloudFront | Las cuentas con Free plan **no son elegibles** (D14) |

## Ventajas

- Defensa en profundidad: deny by default + Block Public Access + bucket policy condicionada a la distribución.
- Costo prácticamente nulo con el uso del proyecto.
- Sin servidores para el frontend.

## Desventajas

- **Caché:** después de subir archivos nuevos hay que **invalidar** la caché, o los usuarios ven la versión vieja (pasó durante la Etapa 3).
- Frontend y API quedan en **orígenes distintos**: hace falta CORS (D30).
- Dos servicios que entender y configurar en lugar de uno.
- Sin WAF: aceptable para un sitio estático de solo lectura; hay que reevaluarlo si cambia el riesgo.

## Consideraciones de seguridad

- Es la mitigación directa del error de configuración más común en AWS: **buckets S3 públicos**.
- Cifrado en tránsito obligatorio (redirect a HTTPS) y en reposo (SSE-S3; SSE-C bloqueado).
- CloudFront responde **403** en lugar de 404 para objetos inexistentes, lo que dificulta enumerar el contenido.
- Es justamente el tipo de configuración que los checks de la Etapa 11 van a evaluar (Block Public Access, cifrado).

## Consideraciones de costo

CloudFront pay-as-you-go con Free Tier permanente ([03-cloudfront.md](../03-cloudfront.md#7-costos)); almacenamiento y requests de S3 en el orden de KB y decenas ([02-s3.md](../02-s3.md#6-costos)). Se evitaron a propósito las opciones con costo fijo: WAF, logging y versioning. En una cuenta con Free plan, el consumo se descuenta de los créditos.

## Consecuencias

- La API necesita CORS restringido al dominio de CloudFront (ADR-003).
- El despliegue del frontend es: subir archivos a S3 + invalidar la caché (con CDK, automatizable).
- El bucket y la distribución se crearon a mano y se van a recrear con CDK en la Etapa 12.

## Evolución futura

- Servir la API bajo el mismo dominio (`/api/*` en CloudFront) eliminaría CORS (mejora posible, D30).
- Dominio propio con ACM, WAF o logging se evalúan solo si aparece una necesidad concreta, y con su costo.
