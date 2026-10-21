# Tarea: CI del frontend (8.6)

## Specs
S1: El usuario pidió implementar el paso 8.6 (job de CI del frontend, ver docs/08-frontend.md §5).
S2: El CI debe correr `npm ci`, `npm run typecheck` (`tsc --noEmit`), `npm run build` (`vite build`) y `npm audit`.
S3: Las actions deben fijarse por commit SHA (D61) con la versión en un comentario (`checkout` v7.0.1, `setup-node` v4.4.0).
S4: El workflow debe respetar `permissions: contents: read`, `timeout-minutes: 5` (D63) y no usar credenciales de AWS.
S5: El nombre del job debe ser `checks` si se extiende el existente (D74, ruleset) o `frontend-checks` si es independiente.

## Tasks
T1: Confirmar con el usuario: ¿extender `checks` (una sola marca) o job `frontend-checks` (separado)?
T2: Crear `.github/workflows/frontend-ci.yml` o modificar `.github/workflows/ci.yml`.
T3: Agregar steps: `npm ci`, `npm run typecheck`, `npm run build`, `npm audit`.
T4: Verificar que los SHAs de las actions coincidan con los de `ci.yml` (checkout v7.0.1, setup-python v7.0.0 para Python; setup-node v4.4.0 para Node si se agrega).
T5: Commit en rama `feat/ci-frontend-job`.

## Log
L1: Usuario autorizó implementar 8.6 (CI del frontend) con ODD.
