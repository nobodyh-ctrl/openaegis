# infra/ — OpenAegis como código (AWS CDK, Etapa 12)

Un solo stack, `OpenAegis`, escrito en Python. `cdk synth` lo traduce a una plantilla de CloudFormation, y `cdk deploy` la aplica en la cuenta.

| Archivo | Para qué |
|---|---|
| `app.py` | Punto de entrada: crea la app y el stack |
| `openaegis/stack.py` | El stack; cada área (datos, Lambdas, API, auth, frontend, observabilidad) es un módulo aparte |
| `tests/` | Tests de la plantilla sin AWS: reglas de seguridad que tiene que cumplir cualquier recurso |
| `cdk.json` | Cómo correr la app + feature flags de CDK (los recomendados al crear el proyecto) |
| `requirements.txt` | Librería de CDK (Python), versión exacta |
| `package.json` | CLI de CDK (Node), versión exacta: se usa con `npx cdk`. Se actualiza junto con `requirements.txt` |

## Sintetizar y testear (sin credenciales)

PowerShell, desde `infra/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm ci
python -m unittest discover -s tests -v
npx cdk synth          # genera cdk.out/ (ignorado por git)
```

## Desplegar (CloudShell)

El usuario no tiene access keys (D4): `cdk diff` y `cdk deploy` se corren en CloudShell, con las credenciales temporales de la sesión de consola. Es lo mismo que arriba, pero activando el entorno con `source .venv/bin/activate` e instalando con `pip install --no-cache-dir -r requirements.txt`. CloudShell tiene 1 GB persistente en el home, y el entorno de Python ocupa unos 460 MB.

Los pasos de deploy se documentan a medida que se agregan recursos (12.3 en adelante).
