# ADR-001: Arquitectura serverless (Lambda + API Gateway) para la V1

- **Estado:** aceptada
- **Fecha:** 2026-10-01 (decidida en la Etapa 1; confirmada en las Etapas 4–6)
- **Decisiones relacionadas:** D6, D7, D8, D18–D23, D46 ([DECISIONS.md](../DECISIONS.md))

## Contexto

OpenAegis necesita un backend HTTP que reciba requests del frontend, aplique reglas de negocio sobre los controles y, más adelante, ejecute checks de solo lectura contra la cuenta de AWS. El tráfico esperado es **muy bajo e irregular**: un usuario (o unos pocos) que despliega la app en su propia cuenta. El proyecto es de aprendizaje y portfolio, corre en una cuenta con **Free plan**, y uno de sus objetivos es entender y poder explicar cada componente.

## Decisión

El backend es una **función AWS Lambda en Python** (3.14, arm64, 128 MB, timeout 3 s), expuesta **solo** a través de **API Gateway (HTTP API)**. Sin servidores, sin contenedores, sin VPC, en una sola región (`us-east-1`).

## Por qué

- Con tráfico bajo, **se paga por uso**: invocaciones y GB-segundo, no horas encendidas.
- No hay sistema operativo que parchar ni capacidad que planificar; la alta disponibilidad multi-AZ viene incluida.
- Escala automáticamente, incluso a cero.
- Reduce la infraestructura a operar, lo que permite concentrarse en IAM, seguridad y diseño.
- Es una arquitectura adecuada para aprender los fundamentos: event, handler, execution role, logs.

## Alternativas consideradas

| Alternativa | Por qué no (por ahora) |
|---|---|
| EC2 con Flask/FastAPI | Cobra por hora aunque no haya tráfico; hay que administrar el SO, parches y red |
| ECS/Fargate con contenedores | Cobra mientras la tarea corre; suele requerir ALB (costo fijo) y más piezas (cluster, task definition, service). Es un tema explícito del Bloque B |
| Lambda **Function URL** | Endpoint público sin throttling ni autorizador JWT nativo (D22) |
| FastAPI + Mangum dentro de Lambda | Empaquetar `pydantic-core` para Linux arm64 desde Windows, más cold start, más supply chain (D46) |

## Ventajas

- Costo proporcional al uso real; con el uso del proyecto, prácticamente cero.
- Sin servidores ni parches.
- Permisos explícitos y separados: quién puede **invocar** la función (resource-based policy) y qué puede **hacer** la función (execution role).
- Despliegue simple: un zip (y desde la Etapa 12, `cdk deploy`).

## Desventajas

- **Cold starts:** la primera invocación de un entorno nuevo tarda más, y el Init también se factura.
- **Límites de ejecución:** duración máxima, memoria, tamaño de payload. Un scan largo de muchos recursos podría no entrar en una sola invocación.
- **Debugging distinto:** no hay un servidor al que conectarse; los logs están repartidos en streams (un stream por entorno de ejecución).
- **Modelo stateless:** nada persiste entre invocaciones; todo estado va a DynamoDB.
- Con tráfico alto y constante, puede salir **más caro** que un contenedor siempre encendido.
- Empaquetar dependencias nativas (arm64) se complica sin Docker o CDK.

> **Serverless no significa automáticamente "más barato" ni "mejor".** Fue la opción adecuada para el tamaño, el tráfico y los objetivos de esta etapa.

## Consideraciones de seguridad

- **Sin credenciales en el código:** la Lambda usa credenciales temporales de STS, a través de su execution role.
- **Superficie de entrada única:** solo API Gateway puede invocarla, y solo desde esta API y sus paths (resource-based policy con `AWS:SourceArn`).
- **Sin VPC:** no hace falta red privada, y se evita el NAT Gateway (costo fijo).
- **Riesgo:** un rol excesivo amplifica cualquier bug. Mitigación: least privilege (ADR-004).

## Consideraciones de costo

Free Tier permanente de Lambda: 1 M de requests y 400.000 GB-segundos por mes ([04-lambda.md](../04-lambda.md#7-costos)). Con 128 MB y ejecuciones de milisegundos, el uso del proyecto es una fracción mínima. Los riesgos de costo (recursión, provisioned concurrency, timeouts largos) están mitigados: sin triggers recursivos, sin provisioned concurrency y con un timeout de 3 s.

## Consecuencias

- El código se organiza para un entorno sin estado: router + módulos (D46), sin estado global salvo el cliente de boto3 creado en el cold start.
- Toda persistencia va a DynamoDB (ADR-004) y toda la observabilidad, a CloudWatch.
- Los checks de la Etapa 11 tienen que diseñarse pensando en los límites de duración.

## Evolución futura

En el Bloque B hay una etapa explícita de comparación **Lambda vs. ECS/Fargate** (tráfico, costo, cold starts, duración, operación, observabilidad, seguridad, complejidad). **La migración no es obligatoria.** Si se hace, la separación en módulos permite cambiar solo `handler.py` por una app FastAPI y reutilizar `controls.py`, `validation.py` y `repository.py`.
