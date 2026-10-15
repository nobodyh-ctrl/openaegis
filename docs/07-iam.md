# Etapa 7 — IAM: auditoría de permisos y least privilege

> **Estado:** ✅ completada (2026-10-15)
> **Costo de la etapa:** USD 0 (IAM no tiene costo; el analyzer de *external access* de IAM Access Analyzer es gratis)

## 1. Objetivo

Revisar **todos** los permisos del proyecto y ajustar lo que quedó más amplio de lo necesario:

- hacer un inventario de identidades y policies (identity-based, resource-based, trust);
- registrar cada problema como un **hallazgo con severidad**, como lo va a hacer OpenAegis en la Etapa 11;
- corregir con evidencia **antes** y **después** de cada cambio;
- sumar un control **detectivo** que vigile las resource-based policies de forma continua.

Esta etapa no agrega servicios a la aplicación.

## 2. Conceptos clave

### 2.1 Cómo decide IAM

```text
¿Hay un Deny explícito que aplique?   ──sí──►  explicitDeny  (gana siempre, aunque haya un Allow)
        │ no
¿Hay un Allow que aplique?            ──no──►  implicitDeny  (deny by default: nadie lo permitió)
        │ sí
     allowed
```

| Resultado | Significado | Consecuencia |
|---|---|---|
| `implicitDeny` | Nadie lo **permitió** | Un `Allow` nuevo, en cualquier policy, lo habilita |
| `explicitDeny` | Alguien lo **prohibió** | Ningún `Allow` lo puede reabrir: sirve para poner "techos" |

### 2.2 Tipos de policy

| Tipo | Dónde vive | Pregunta que responde | En el proyecto |
|---|---|---|---|
| Identity-based | Usuario, grupo o rol | *¿Qué puedo hacer?* | Policy de logs y `controls-table-crud` del rol de la Lambda; `AdministratorAccess` del grupo `Admins` |
| Resource-based | El recurso | *¿Quién me puede llamar?* | Bucket policy; resource-based policy de la Lambda |
| Trust policy | El rol | *¿Quién me puede asumir?* | Solo `lambda.amazonaws.com` asume el rol de la Lambda |

### 2.3 Managed policies: AWS vs. customer, y sus versiones

| | AWS managed | Customer managed |
|---|---|---|
| ARN | `arn:aws:iam::aws:policy/...` | `arn:aws:iam::<cuenta>:policy/...` |
| ¿Se puede editar? | No | Sí |
| Ejemplo | `AdministratorAccess` | `AWSLambdaBasicExecutionRole-…` (la creó la consola de Lambda **en tu cuenta**, copiando la de AWS) |

Una customer managed policy **no se edita en el lugar**: cada cambio crea una **versión** (`v1`, `v2`…, hasta 5) y una sola es la **default**. El rollback es volver a marcar la anterior como default.

### 2.4 El ARN de invocación de API Gateway

```text
arn:aws:execute-api:us-east-1:<cuenta>:<api-id> / <stage> / <MÉTODO> / <path>
                                                    *          GET      controls/{id}
```

Con `*` en el método, un statement autoriza **cualquier** método de ese path, incluso rutas que se agreguen después por error.

### 2.5 Controles preventivos vs. detectivos

| Tipo | Qué hace | Ejemplo en el proyecto |
|---|---|---|
| **Preventivo** | **Impide** la configuración insegura | Block Public Access en el bucket |
| **Detectivo** | **Detecta y avisa**, no modifica | IAM Access Analyzer |

Se complementan. OpenAegis V1 es **detectivo** (read-only); la remediación es tema de la V2.

### 2.6 IAM Access Analyzer

Analiza en forma continua las resource-based policies (buckets S3, funciones Lambda, trust policies de roles, KMS, SQS, Secrets Manager…) de la región donde se crea, y genera un finding si alguna da acceso **fuera de la zona de confianza** (la cuenta).

| Tipo de analyzer | Valor de `--type` | Costo (verificado el 2026-10-13 en la [página oficial](https://aws.amazon.com/iam/access-analyzer/pricing/)) |
|---|---|---|
| **External access** ✅ | `ACCOUNT` | Gratis |
| Unused access | `ACCOUNT_UNUSED_ACCESS` | USD 0,20 por rol o usuario por mes |
| Internal access | `ACCOUNT_INTERNAL_ACCESS` | USD 9,00 por recurso por región por mes |

### 2.7 Service-linked roles

Algunos servicios de AWS crean roles en tu cuenta para funcionar. Tienen `Path` `/aws-service-role/`, no se pueden modificar libremente y solo el servicio dueño puede asumirlos. Por eso Access Analyzer encontró 6 roles, aunque el proyecto creó uno solo.

## 3. Hallazgos

| # | Hallazgo | Severidad | Resolución |
|---|---|---|---|
| H1 | `logs:CreateLogGroup` sobre `arn:aws:logs:us-east-1:<cuenta>:*` (valor por defecto de la consola) | LOW | ✅ Restringido al log group de la función (D56) |
| H2 | Statements de invocación con método comodín (`.../*/*/<path>`) | LOW | ✅ Un statement por ruta, con el método (D57) |
| H3 | IAM user con `AdministratorAccess` | MEDIUM | Aceptado (D3): mitigado con MFA y sin access keys; necesario para crear roles y policies |
| H4 | La API no tiene autenticación | HIGH | Planificado: Cognito en la Etapa 9 |
| H5 | Bucket policy con `"Version": "2008-10-17"` (generada por la consola de CloudFront) | INFORMATIVO | Aceptado: sin variables de policy, funciona igual. CDK la regenera con `2012-10-17` |
| — | Root, trust policy, `controls-table-crud`, contenido de la bucket policy | — | Correctos (verificados) |

> La escala de severidad de los controles no tiene un nivel "informativo". Es un dato a considerar al diseñar los findings de la Etapa 11.

## 4. Decisiones técnicas

| # | Decisión | Alternativas evaluadas | Motivo |
|---|---|---|---|
| D56 | Restringir `logs:CreateLogGroup` al log group de la función (versión `v2`) | Quitar la acción; dejarlo | Si se borra el log group, la Lambda lo puede recrear; quitarla convertiría ese borrado en una falla silenciosa |
| D57 | Un statement por ruta con el método explícito; agregar antes de borrar | Dejar el comodín hasta CDK | Una ruta con otro método no puede invocar la Lambda; sin corte de servicio durante el cambio |
| D58 | IAM Access Analyzer solo de *external access* | *Unused* e *internal access* | Gratis; verifica con una herramienta lo revisado a mano |

> **Contexto para entrevistas:** audité los permisos del proyecto y registré cada problema como un hallazgo con severidad. Restringí la policy de logs que había creado la consola, verificándolo con el IAM Policy Simulator antes y después, y reemplacé los permisos de invocación por path por uno por ruta, agregando los nuevos antes de borrar los viejos para no cortar el servicio. Además, dejé un analyzer de IAM Access Analyzer de external access, gratis, que confirmó que ninguna resource-based policy da acceso fuera de la cuenta.

## 5. Configuración realizada

### 5.1 Policy de logs (customer managed, `v2` default)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "logs:CreateLogGroup",
      "Resource": [
        "arn:aws:logs:us-east-1:<cuenta>:log-group:/aws/lambda/cloud-sec-checklist-api",
        "arn:aws:logs:us-east-1:<cuenta>:log-group:/aws/lambda/cloud-sec-checklist-api:*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:<cuenta>:log-group:/aws/lambda/cloud-sec-checklist-api:*"
    }
  ]
}
```

Creada con `aws iam create-policy-version --policy-arn <policy-arn> --policy-document file://logs-policy-v2.json --set-as-default`. `v1` queda guardada para rollback.

### 5.2 Resource-based policy de la Lambda

| Sid | `SourceArn` |
|---|---|
| `apigw-get-controls` | `arn:aws:execute-api:us-east-1:<cuenta>:<api-id>/*/GET/controls` |
| `apigw-post-controls` | `.../*/POST/controls` |
| `apigw-get-controls-id` | `.../*/GET/controls/{id}` |
| `apigw-patch-controls-id` | `.../*/PATCH/controls/{id}` |
| `apigw-delete-controls-id` | `.../*/DELETE/controls/{id}` |

Todos con Principal `apigateway.amazonaws.com` y Action `lambda:InvokeFunction`, creados con `aws lambda add-permission`. Los 2 statements anteriores, por path y creados por la consola, se borraron con `aws lambda remove-permission`.

### 5.3 IAM Access Analyzer

```text
aws accessanalyzer create-analyzer --analyzer-name openaegis-external-access --type ACCOUNT --tags Project=cloud-security-checklist
```

Se creó por CLI para fijar explícitamente el tipo gratuito: el asistente de la consola ofrece también los tipos pagos.

## 6. Verificación

| Qué | Cómo | Resultado (2026-10-15) |
|---|---|---|
| Root | `aws iam get-account-summary` | `AccountMFAEnabled: 1`, `AccountAccessKeysPresent: 0` |
| Policies del rol | `list-attached-role-policies`, `list-role-policies` | 1 customer managed (logs) + 1 inline (`controls-table-crud`) |
| H1 antes | `simulate-principal-policy` | Los dos log groups `allowed` |
| H1 después | Ídem, con el detalle por recurso | Propio `allowed`; otro `implicitDeny` |
| La Lambda sigue logueando | `curl` + `aws logs tail` | 200 y línea nueva en los logs |
| H2 | Las 5 rutas con 7 statements y después con los 5 nuevos | 200 en todas, las dos veces (con un control `TEST-IAM` creado y borrado) |
| Policy final | `get-policy` + `jq` | 5 statements con el método explícito |
| Access Analyzer | `list-analyzers`, `list-analyzed-resources`, `list-findings` | `ACCOUNT` / `ACTIVE`; 1 bucket, 1 Lambda, 1 tabla, 6 roles; **0 findings activos** |

**Comandos útiles:**

```text
ROLE=cloud-sec-checklist-api-role-<sufijo>
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN=$(aws iam get-role --role-name $ROLE --query Role.Arn --output text)

# Simulador con detalle por recurso
aws iam simulate-principal-policy --policy-source-arn $ROLE_ARN --action-names logs:CreateLogGroup \
  --resource-arns "arn:aws:logs:us-east-1:${ACCOUNT}:log-group:/aws/lambda/cloud-sec-checklist-api" \
                  "arn:aws:logs:us-east-1:${ACCOUNT}:log-group:cualquier-otro" \
  --query 'EvaluationResults[0].ResourceSpecificResults[].{Recurso:EvalResourceName,Decision:EvalResourceDecision}'

# Statements de invocación, uno por línea
aws lambda get-policy --function-name cloud-sec-checklist-api --query Policy --output text \
  | jq -r '.Statement[] | [.Sid, .Condition.ArnLike["AWS:SourceArn"]] | @tsv'

# Findings activos
ANALYZER_ARN=$(aws accessanalyzer list-analyzers --query "analyzers[?name=='openaegis-external-access'].arn" --output text)
aws accessanalyzer list-findings --analyzer-arn $ANALYZER_ARN --filter '{"status": {"eq": ["ACTIVE"]}}'
```

## 7. Debugging

### 7.1 `<sufijo>` literal en bash

**Síntoma:** `bash: syntax error near unexpected token 'newline'`, y después `argument --role-name: expected one argument`.
**Causa:** en bash, `<` es una redirección. La asignación falló, la variable quedó vacía, y los comandos siguientes recibieron el parámetro sin valor.
**Lección:** una variable vacía rompe todo lo que viene después, en cadena. Reemplazar los marcadores antes de ejecutar.

### 7.2 El simulador devolvió una fila para dos recursos

**Síntoma:** una sola fila, con `"Recurso": "arn:aws:logs:${Region}:${Account}:.+"`.
**Causa:** con varios recursos, `EvaluationResults` trae un resultado general por **acción**; el detalle por recurso está en `ResourceSpecificResults`. El `--query` leía solo el nivel general.
**Solución:** `--query 'EvaluationResults[0].ResourceSpecificResults[]...'`.
**Lección:** un filtro mal hecho puede ocultar justo el dato que importa. El resultado general `implicitDeny` no decía si el log group propio seguía permitido.

### 7.3 Más memoria de la esperada (observación)

En un cold start, `REPORT` mostró **97 MB usados de 128 MB** (en la Etapa 4, con el handler de prueba, eran ~38 MB). Importar boto3 y crear el `resource` de DynamoDB sube el consumo. No es un error, pero queda poco margen: se monitorea en la Etapa 10.

## 8. Costos

| Concepto | Costo |
|---|---|
| IAM (usuarios, roles, policies, simulador) | USD 0: *"IAM is offered at no additional charge"* ([FAQ de IAM](https://aws.amazon.com/iam/faqs/)) |
| Access Analyzer, external access | USD 0 |
| Access Analyzer, unused / internal access | ⚠️ Con costo. No usados |

## 9. Relación con Cloud Security

| Control | Implementación |
|---|---|
| Least privilege en identity-based | Logs solo sobre el log group propio; CRUD sobre 1 tabla |
| Least privilege en resource-based | Invocación solo desde 5 rutas exactas |
| Protección de la identidad más poderosa | Root con MFA, sin access keys, sin uso diario |
| Detección continua de acceso externo | IAM Access Analyzer |
| Cambios reversibles | Versiones de policy (`v1` guardada); agregar antes de borrar |
| Evidencia | Simulador y pruebas antes y después de cada cambio |
| Pendiente | Autenticación de la API (Etapa 9) |

## 10. Cómo revertir esta etapa

| Cambio | Revertir |
|---|---|
| D56 | `aws iam set-default-policy-version --policy-arn <policy-arn> --version-id v1` |
| D57 | `add-permission` con `--source-arn ".../*/*/controls"` y `".../*/*/controls/{id}"`, y después `remove-permission` de los 5 `apigw-*` |
| D58 | `aws accessanalyzer delete-analyzer --analyzer-name openaegis-external-access` |

## 11. Cosas que NO se deben hacer

- ❌ Dejar los permisos que crea la consola sin revisarlos: suelen ser más amplios de lo necesario.
- ❌ Borrar un permiso antes de crear su reemplazo.
- ❌ Confiar en un resultado del simulador sin mirar el detalle por recurso.
- ❌ Usar `*` en el método de un `SourceArn` cuando se conocen las rutas.
- ❌ Crear un analyzer de Access Analyzer sin fijar el tipo: los de *unused* e *internal access* cobran.
- ❌ Confundir `implicitDeny` con una prohibición: cualquier `Allow` nuevo lo habilita.
- ❌ Pegar salidas de la CLI sin tapar el ID de cuenta, el ID de la API y los sufijos: aparecen en los ARNs aunque los comandos usen variables.
