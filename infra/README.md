# infra/ — OpenAegis como código (AWS CDK, Etapa 12)

Un solo stack, `OpenAegis`, escrito en Python. `cdk synth` lo traduce a una plantilla de CloudFormation, y `cdk deploy` la aplica en la cuenta.

| Archivo | Para qué |
|---|---|
| `app.py` | Punto de entrada: crea la app y el stack |
| `openaegis/stack.py` | El stack; cada área (datos, Lambdas, API, auth, frontend, observabilidad) es un módulo aparte |
| `openaegis/data.py` | Las 3 tablas de DynamoDB (controles, findings, scans) |
| `openaegis/compute.py` | Las Lambdas `openaegis-api` y `openaegis-scanner`, con sus roles (permisos escritos a mano, sin `grant_*`: D109) y sus log groups (D110) |
| `openaegis/auth.py` | Cognito: User Pool con MFA obligatorio y registro cerrado, app client de la SPA (PKCE, sin secret) y dominio del login, con un prefijo derivado del ID del stack |
| `openaegis/api.py` | HTTP API `openaegis-http-api`: JWT authorizer en las 8 rutas, throttling, access log y **un permiso de invocación por ruta con el método** (D57; la integración de CDK por defecto lo deshace) |
| `tests/` | Tests de la plantilla sin AWS: `test_stack.py` tiene las reglas que cumple cualquier recurso; `test_data.py`, `test_compute.py`, `test_auth.py` y `test_api.py`, las de cada construct (incluida la lista exacta de permisos de cada rol y de invocación de la Lambda). 46 tests al 12.4 |
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

### Primera vez (hecho el 2026-11-07, paso 12.3)

```bash
git clone https://github.com/nobodyh-ctrl/openaegis.git ~/openaegis
cd ~/openaegis/infra
python3 -m venv .venv && source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
npm ci
chmod go-w ~                                   # ver "Problemas conocidos"
npx cdk bootstrap --termination-protection     # una vez por cuenta y región
npx cdk diff                                   # leer la tabla de IAM ANTES de desplegar
npx cdk deploy
```

`cdk bootstrap` crea el stack `CDKToolkit`: un bucket para los assets (el zip de las Lambdas), roles para desplegar y el parámetro `/cdk-bootstrap/hnb659fds/version` en SSM. Costo ~USD 0 (centavos de S3 por los assets). `--termination-protection` impide borrarlo por error.

### Cada cambio

```text
PC: código + tests (PowerShell) → commit + PR → merge
CloudShell: cd ~/openaegis && git pull → cd infra && source .venv/bin/activate
            → npx cdk diff (leer la tabla de IAM) → npx cdk deploy → verificar
```

`cdk deploy` corre con `--require-approval broadening` (el valor por defecto): pide `y` cada vez que un cambio **amplía** permisos (IAM, resource-based policies, security groups).

### Verificación del 12.3 (2026-11-07, todo ✅)

```bash
# 1. Las dos Lambdas con el mismo código → mismo CodeSha256 y Successful
for f in openaegis-api openaegis-scanner; do
  aws lambda get-function-configuration --function-name $f --query "{f:FunctionName,sha:CodeSha256,estado:LastUpdateStatus}"
done

# 2. La API sin API Gateway → statusCode 200, body {"items": [], "count": 0}
aws lambda invoke --function-name openaegis-api --cli-binary-format raw-in-base64-out \
  --payload '{"routeKey":"GET /controls"}' /tmp/api.json && cat /tmp/api.json; echo

# 3. Un scan con la tabla vacía → StatusCode 200 sin FunctionError, log "scan terminado", un item en openaegis-scans
aws lambda invoke --function-name openaegis-scanner /tmp/scan.json && cat /tmp/scan.json; echo
aws logs tail /aws/lambda/openaegis-scanner --since 5m
aws dynamodb scan --table-name openaegis-scans --query "Items[0]"

# 4. Los roles sin managed policies → [] dos veces
for f in openaegis-api openaegis-scanner; do
  ROLE=$(aws lambda get-function-configuration --function-name $f --query "Role" --output text | cut -d/ -f2)
  aws iam list-attached-role-policies --role-name $ROLE --query "AttachedPolicies"
done
```

La prueba 2 da `200` sin token porque el JWT authorizer está en API Gateway, delante de la Lambda: un `lambda invoke` lo saltea y se autoriza solo por IAM (`lambda:InvokeFunction`). Por eso la resource-based policy de la Lambda tiene que dejar entrar solo a la API (12.4).

⚠️ La salida de `aws logs tail` trae el ID de la cuenta en los ARN (`functionArn`): taparlo al compartirla.

### Verificación del 12.4: API Gateway + Cognito (2026-11-07, todo ✅)

**En el `cdk diff`, antes de desplegar:** 8 filas `lambda:InvokeFunction` con principal `apigateway.amazonaws.com`, cada una con su método (`.../*/GET/controls`), y solo altas (`[+]`) en Resources. `cdk deploy` pidió `y` por los permisos nuevos (`broadening`).

**Usuario** (el registro está cerrado). `-s` oculta lo que se tipea: con `read -r` solo, el email queda en pantalla.

```bash
POOL=$(aws cloudformation describe-stacks --stack-name OpenAegis \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoAuthority'].OutputValue" --output text | awk -F/ '{print $NF}')
read -rs EMAIL && echo "email cargado"
aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$EMAIL" \
  --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL --query "User.UserStatus"        # → "FORCE_CHANGE_PASSWORD"
```

**SPA local contra el stack** (PowerShell, en `frontend/`): `.env.local` con los 4 outputs del deploy (`API_PROXY_TARGET` = `ApiUrl` **sin la barra final**, `VITE_COGNITO_AUTHORITY`, `VITE_COGNITO_CLIENT_ID`, `VITE_COGNITO_DOMAIN`). Las 4 tienen que ser **del mismo stack**: el authorizer valida el issuer (el pool) y la audience (el client). `npm run dev` y login en incógnito: contraseña temporal → nueva → TOTP nuevo. CRUD verificado.

**Pruebas de la API** (los tokens se copian de la SPA con el snippet de AGENTS.md §7 y se cargan con `read -rs`):

| Prueba | Esperado | Obtenido |
|---|---|---|
| Sin token / `Bearer falso` | `401` / `401` | ✅ `missing: token not provided` / `invalid_token: ... segments` |
| Access token | `200` | ✅ |
| ID token | `403` | ✅ `insufficient_scope`: los scopes solo vienen en el access token |
| `PUT /controls` (no existe) | `404` | ✅ y sin línea en el access log (limitación de D85, igual que en la API manual) |
| `POST /scans` → `GET /scans/latest` | `202` → `controls_evaluated: 0` | ✅ |
| `get-policy` de `openaegis-api` | 8 `SourceArn` con método | ✅ |
| Conteo de `openaegis-controls` / `cloud-sec-checklist-controls` | 1 → 0 tras el CRUD / sin cambios | ✅ |

```bash
# Permisos de invocación sin cuenta ni ID de la API
aws lambda get-policy --function-name openaegis-api --query Policy --output text \
  | jq -r '.Statement[].Condition.ArnLike."AWS:SourceArn"' | cut -d/ -f2- | sort
# Access log sin IP ni sub
aws logs tail /aws/vendedlogs/apigateway/openaegis-http-api --since 30m --format short \
  | cut -d' ' -f2- | jq -c '{method, routeKey, status, authorizerError, integrationStatus}'
```

En el access log, `integrationStatus: "-"` en los rechazos prueba que la Lambda **no se ejecutó**. `status: 201` con `integrationStatus: 200` no es una contradicción: el primero es lo que respondió la Lambda, el segundo, el resultado de invocarla.

⚠️ Datos sensibles de este paso: el bloque **Outputs** y el **Stack ARN** del `cdk deploy` (la URL de la API, el pool, el client, el dominio, la cuenta) y `GET /scans/latest`, que devuelve `requested_by` (el `sub` de quien lanzó el scan).

## Hallazgos del primer deploy

| Hallazgo | Qué se hizo / propuesta |
|---|---|
| El bootstrap le da `AdministratorAccess` al rol con el que CloudFormation ejecuta los cambios | Aceptado en la V1, como el hallazgo H3 de la Etapa 7: el único que despliega es el usuario, con MFA. Ajustarlo con `--cloudformation-execution-policies` cuando haya CD desde GitHub Actions |
| `Trusted accounts: (none)` en el bootstrap | Correcto: ninguna otra cuenta puede desplegar en esta |
| La "early validation" de CloudFormation detectó en el `cdk diff` los 4 choques de nombre con los recursos manuales de la Etapa 11 | El deploy habría fallado **antes** de crear nada. Se resolvió borrándolos a mano (D111) |
| CloudShell trae Node 20 (fin de vida: 2026-10-30) | Por ahora solo hay avisos. Desde enero de 2027 el SDK de AWS para JavaScript exige Node ≥ 22: revisarlo en la próxima revisión de dependencias |
| El body esperado de `GET /controls` era `[]` en las notas de traspaso | El correcto es `{"items": [...], "count": N}` (`backend/controls.py`). El error estaba en las notas, no en el deploy |

## Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| `cdk synth`/`deploy` falla en CloudShell con un error de jsii sobre permisos | El home de CloudShell tenía permisos `0777`, y jsii (el puente entre Python y el CDK en JavaScript) se niega a usar un caché que cualquiera puede escribir | `chmod go-w ~`. Si vuelve tras reiniciar CloudShell: `export JSII_RUNTIME_PACKAGE_CACHE=disabled` |
| Aviso "Newer version available" | El CLI está fijo a propósito (D107) | Ignorarlo; actualizar `package.json` y `requirements.txt` juntos, con versiones de ≥ 14 días |
