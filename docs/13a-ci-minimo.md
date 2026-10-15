# Etapa 13a — CI mínimo con GitHub Actions

> **Estado:** ✅ completada (2026-10-15)
> **Costo de la etapa:** USD 0 (GitHub Actions es gratis para repos públicos con runners estándar; el CI no usa AWS)
> **Por qué "13a":** es una primera parte de la Etapa 13, **adelantada** antes del frontend (D60).

## 1. Objetivo

Que cada `git push` se verifique automáticamente, **sin darle al CI credenciales de AWS**:

- tests unitarios de los módulos que no dependen de AWS (`validation.py`, `responses.py`);
- un chequeo que falle si algún archivo versionado tiene un identificador real (ID de cuenta, de API, dominio de CloudFront, access key);
- aplicar al propio pipeline lo aprendido en la Etapa 7: least privilege y cuidado con el código de terceros.

## 2. Conceptos clave

### 2.1 CI

**Integración continua:** cada cambio que se sube se verifica automáticamente con los mismos chequeos, en una máquina limpia. Un problema se detecta minutos después del push, no después del deploy.

```text
git push ──► GitHub Actions: máquina Linux temporal ──► tests + chequeo ──► ✅ / ❌ en el commit
```

### 2.2 Vocabulario de GitHub Actions

| Concepto | Qué es | En el proyecto |
|---|---|---|
| **Workflow** | Archivo YAML en `.github/workflows/` | `ci.yml` |
| **Evento** (`on:`) | Lo que lo dispara | `push` y `pull_request` |
| **Job** | Conjunto de pasos que corre en una máquina | `checks` |
| **Runner** | La máquina. Las de GitHub son **efímeras**: se crean para el job y se destruyen | `ubuntu-latest` |
| **Step** | Un comando (`run:`) o una action (`uses:`) | 4 pasos |
| **Action** | Paso reutilizable publicado por terceros | `actions/checkout`, `actions/setup-python` |

Por defecto, si un paso falla, los siguientes del mismo job **no se ejecutan**.

### 2.3 Seguridad de un pipeline

| Riesgo | Mitigación |
|---|---|
| El `GITHUB_TOKEN` puede tener permisos de escritura sobre el repo | `permissions: contents: read` |
| `actions/checkout` deja el token guardado en la configuración de git del runner | `persist-credentials: false` |
| Una etiqueta (`v7`) se puede mover a otro código: *supply chain* | Actions fijadas por **commit SHA** |
| Un job colgado consume minutos | `timeout-minutes: 5` |
| Credenciales de la nube en el CI | **No hay**: el CI no toca AWS. El día que despliegue (Bloque B), con OIDC y credenciales temporales |
| Los logs de un repo público son públicos | El chequeo **enmascara** lo que encuentra (`1111...`) |

### 2.4 Detectivo vs. preventivo, otra vez

El CI corre **después** del push: **detecta** pero no impide. Si un ID real llega a `main`, queda en el historial aunque se corrija en otro commit. Para **impedir**, hacen falta controles previos:

| Control | Cuándo actúa | Estado |
|---|---|---|
| CI | Después del push | ✅ |
| Branch protection / rulesets (exigir CI en verde para *merge*) | Al mergear un pull request | Mejora posible |
| Pre-commit hook con el mismo script | Antes de crear el commit, en la PC | Mejora posible |

### 2.5 Qué se puede testear sin AWS (gracias al refactor de la Etapa 6)

| Módulo | ¿Depende de AWS al importarse? | ¿Se testea hoy? |
|---|---|---|
| `validation.py` | No | ✅ |
| `responses.py` | No | ✅ |
| `controls.py` | Sí, indirectamente: importa `repository.py`, que lee `TABLE_NAME` y crea el `boto3.resource` | Etapa 14 (repositorio falso o moto) |

### 2.6 `FAIL` vs. `ERROR` en `unittest`

| Resultado | Significa |
|---|---|
| `FAIL` | Una aserción no se cumplió: el test detectó lo que tenía que detectar, con un mensaje claro |
| `ERROR` | El test **explotó** con una excepción inesperada (por ejemplo, `TypeError`) |

Un test de regresión tiene que fallar con `FAIL` y un mensaje que explique qué se rompió (ver 7.1).

## 3. Decisiones técnicas

| # | Decisión | Alternativas evaluadas | Motivo |
|---|---|---|---|
| D59 | Etapa 13 = **opción A**: CI sin credenciales de AWS en la V1; deploy automático y OIDC en el Bloque B | Opción B: todo al Bloque B | Resuelve la contradicción entre los documentos del usuario; la V1 queda probada sin que el CI toque la cuenta |
| D60 | Adelantar la **Etapa 13a** antes del frontend | Hacerlo en la Etapa 13; Bloque B | El código no se verificaba antes del deploy, y el riesgo de publicar IDs crece en la Etapa 8 (la URL de la API en el frontend) |
| D61 | Actions fijadas por **commit SHA**, con la versión en un comentario | Etiquetas (`@v7`) | Una etiqueta se puede mover; un SHA es inmutable |
| D62 | Chequeo de identificadores **propio** (`scripts/check_identifiers.py`, sin dependencias) | gitleaks, trufflehog | Sin *supply chain* extra; patrones a la medida del proyecto (distingue los marcadores `<cuenta>`), revisa el XML de los diagramas y enmascara lo que encuentra. Contra: hay que mantener los patrones a mano |
| D63 | Token con `contents: read`, `persist-credentials: false` y `timeout-minutes: 5` | Valores por defecto | Least privilege aplicado al pipeline |

> **Contexto para entrevistas:** agregué un CI mínimo con GitHub Actions que corre tests unitarios y un chequeo propio de identificadores en cada push, sin credenciales de AWS. El token del workflow tiene solo permiso de lectura, las actions están fijadas por commit SHA y el chequeo nunca imprime el valor completo de lo que encuentra, porque los logs de un repo público son públicos. Los tests son posibles sin AWS porque antes separé el backend en módulos: la validación no depende de boto3.

## 4. Configuración realizada

### 4.1 Archivos

| Archivo | Qué hace |
|---|---|
| [`tests/test_validation.py`](../tests/test_validation.py) | 21 tests: modo `POST` (obligatorios, tipos, largos, enums, allowlist), modo `PATCH` (solo lo que vino, sin defaults, regresión del `title` vacío) y `validate_control_id` |
| [`tests/test_responses.py`](../tests/test_responses.py) | 9 tests: formato de API Gateway, `Decimal`, `parse_json_body` (regresión de `[]` → 500) |
| [`tests/test_check_identifiers.py`](../tests/test_check_identifiers.py) | 9 tests: detecta lo real y deja pasar marcadores, UUIDs, fechas y SHAs. Los valores de ejemplo se arman concatenando para no dispararse a sí mismos |
| [`scripts/check_identifiers.py`](../scripts/check_identifiers.py) | Recorre `git ls-files` (y el XML embebido en los `.drawio.png`); `exit 1` si encuentra algo |
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | El workflow |

Los tests agregan `backend/` al `sys.path` para importar los módulos igual que la Lambda (`import validation`), sin convertir `backend/` en un paquete.

### 4.2 Patrones del chequeo

| Tipo | Patrón | Deja pasar |
|---|---|---|
| ID de cuenta | `(?<![\w-])\d{12}(?![\w-])` | `<cuenta>`, bloques de UUID, hashes |
| ID de API Gateway | `[a-z0-9]{10}\.execute-api\.<región>\.amazonaws\.com` | `<api-id>.execute-api…` |
| Dominio de CloudFront | `d[a-z0-9]{8,}\.cloudfront\.net` | `<distribucion>.cloudfront.net` |
| Access key | `(AKIA\|ASIA)[A-Z0-9]{16}` | `AKIA...` |

### 4.3 Workflow

```yaml
on: { push: , pull_request: }
permissions: { contents: read }
jobs.checks:
  runs-on: ubuntu-latest · timeout-minutes: 5
  steps:
    actions/checkout@<SHA> (v7.0.1)        persist-credentials: false
    actions/setup-python@<SHA> (v7.0.0)    python-version: "3.14"  (la misma que la Lambda)
    python -m unittest discover -s tests -v
    python scripts/check_identifiers.py
```

Los SHAs se verificaron con `gh` contra los releases oficiales (`v7.0.1` de `actions/checkout` y `v7.0.0` de `actions/setup-python`, ambos del 2026-07-20). `persist-credentials` se verificó en el `action.yml` de la action (por defecto vale `true`).

### 4.4 Correrlo localmente

```powershell
python -m unittest discover -s tests -v
python scripts/check_identifiers.py
```

## 5. Verificación

| Qué | Resultado |
|---|---|
| Tests locales | 39 OK |
| Chequeo local sobre el repo | OK |
| Chequeo local ante un ID falso (archivo temporal, después borrado) | `exit 1`, valor enmascarado |
| **Mutación local:** se reintrodujo el bug del `PATCH` en una **copia** de `backend/` | 2 `FAIL` en `test_obligatorio_vacio_se_rechaza_tambien_en_patch`: los tests lo detectan |
| Primer run en GitHub (commit `be39098`) | ✅ 4 pasos en verde, `Ran 39 tests ... OK`, 35 archivos sin identificadores |
| Ver fallar el CI **en GitHub** (branch descartable) | ⏭️ **Salteado** por decisión del usuario. La mutación local reemplaza la parte de los tests; que GitHub marque ❌ ante un `exit 1` no se verificó en la práctica |

## 6. Costos

| Concepto | Costo |
|---|---|
| GitHub Actions, repo público, runners estándar | USD 0 (verificado el 2026-10-15 en la documentación de facturación de GitHub) |
| AWS | USD 0: el CI no usa la cuenta |

Si el repo pasara a ser **privado**, el plan gratuito de GitHub incluye 2.000 minutos por mes; un run de este CI dura segundos.

## 7. Debugging

### 7.1 Un test de regresión que fallaba con `ERROR` en vez de `FAIL`

**Síntoma:** en la mutación, el test del `title` vacío reportaba `ERROR`.
**Causa:** con el bug, `err` vale `None`, y `assertIn("no puede estar vacío", None)` lanza `TypeError` antes de comparar nada.
**Solución:** `self.assertIsNotNone(err, "el PATCH aceptó un obligatorio vacío")` antes del `assertIn`. Ahora es un `FAIL` con un mensaje que dice qué se rompió.
**Lección:** un test también se prueba: hay que verlo fallar al menos una vez.

### 7.2 Caracteres raros en la terminal de Windows

`…` y las tildes se veían como `�` en la terminal de Windows (no en el runner Linux, que usa UTF-8). El script ahora imprime `...` en lugar de `…`. Es un detalle de presentación.

## 8. Relación con Cloud Security

| Control | Implementación |
|---|---|
| Prevención de fugas de identificadores (detectiva) | `check_identifiers.py` en cada push |
| Least privilege del pipeline | `contents: read`, `persist-credentials: false` |
| *Supply chain* | Actions por SHA; sin dependencias de Python; sin scanners de terceros |
| Sin credenciales de nube en el CI | El pipeline no tiene acceso a AWS |
| Sin fuga en los logs | El chequeo enmascara los valores |
| Regresiones de validación (mass assignment, campos vacíos, JSON no objeto) | Tests unitarios |

## 9. Cómo revertir esta etapa

| Paso | Acción |
|---|---|
| 1 | Borrar `.github/workflows/ci.yml` (el CI deja de correr) |
| 2 | Opcional: borrar `tests/` y `scripts/` |
| 3 | En GitHub, los runs anteriores quedan en la pestaña Actions; se pueden borrar desde ahí |

## 10. Pendientes y mejoras posibles

- **Etapa 12/13:** sumar `cdk synth` cuando exista la infraestructura como código.
- **Etapa 14:** tests de `controls.py` con un repositorio falso (o moto).
- **Mejoras posibles, no decididas:** pre-commit hook con el mismo script (preventivo); branch protection o rulesets que exijan el check en verde; ver fallar el CI en GitHub.

## 11. Cosas que NO se deben hacer

- ❌ Guardar access keys de AWS como *secrets* de GitHub para "facilitar" un deploy: se usa OIDC (Bloque B).
- ❌ Usar actions por etiqueta sin fijar el SHA.
- ❌ Dejar el `GITHUB_TOKEN` con permisos por defecto.
- ❌ Imprimir en los logs del CI el valor de un secreto o identificador que se detectó.
- ❌ Escribir en un test un valor que el propio chequeo marcaría (armarlo concatenando).
- ❌ Confiar en un test que nunca se vio fallar.
- ❌ Creer que el CI impide publicar un dato: corre después del push.
