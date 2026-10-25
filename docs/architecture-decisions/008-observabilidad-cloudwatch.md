# ADR-008: Observabilidad con CloudWatch (logs JSON, access logs, alarmas por email)

- **Estado:** aceptada
- **Fecha:** 2026-10-24 → 2026-10-25 (Etapa 10)
- **Decisiones relacionadas:** D84, D85, D86, D87, D88 ([DECISIONS.md](../DECISIONS.md)) · se apoya en [ADR-001](001-serverless.md) (Lambda + API Gateway), [ADR-003](003-http-api.md) (HTTP API) y [ADR-007](007-autenticacion-cognito.md) (el `sub` del JWT) · detalle en [10-cloudwatch.md](../10-cloudwatch.md)

## Contexto

Al terminar la Etapa 9, la API estaba protegida, pero los problemas solo se veían si alguien los buscaba:

- la Lambda logueaba con `print` en texto plano, sin decir **quién** hizo cada cambio;
- los pedidos rechazados por el JWT authorizer (`401`/`403`) no llegaban a la Lambda y no dejaban rastro;
- nadie se enteraba de un error en producción.

Requisitos:

- saber quién cambió qué, y poder buscarlo;
- ver los intentos rechazados, con el motivo y el origen;
- enterarse de un error sin mirar la consola;
- sin dependencias nuevas, sin servidores y dentro del free tier.

## Decisión

- **Logs de la Lambda:** log format **JSON nativo** de Lambda + módulo `logging`, con una línea por pedido (`route`, `apigw_request_id`, `user_sub`) y una de auditoría por cambio. Sin `try/except` central: los errores inesperados llegan al runtime y a la métrica `Errors`.
- **Access logs de API Gateway** en JSON, con IP, `userAgent`, status, motivo del authorizer, latencias y `sub`; retención de 1 semana.
- **3 alarmas** (errores de la Lambda, `5xx` y pico de `4xx` de la API) → topic de **SNS** → **email**.
- **Dashboard** creado como JSON con `put-dashboard`.
- **Las alarmas se verifican con una falla real**, no solo forzando el estado.

## Por qué

- CloudWatch ya recibe las métricas y los logs de los tres servicios: no hay nada que instalar.
- El formato JSON nativo da campos consultables y el `requestId` sin agregar una librería (regla del proyecto: dependencias solo si resuelven un problema real).
- El access log es el único lugar donde quedan los pedidos que el authorizer rechaza.
- SNS por email es la notificación más simple, con 1.000 emails gratis por mes.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| AWS Lambda Powertools | Una dependencia nueva para algo que el runtime ya hace (JSON, `requestId`). Se puede revisar si se necesitan métricas custom (EMF) o trazas |
| `print(json.dumps(...))` a mano | Sin niveles, sin `requestId` automático, y con riesgo de inconsistencias entre líneas |
| `try/except Exception` central que devuelve 500 | Apaga la métrica `Errors` y su alarma, y esconde el traceback |
| X-Ray / OpenTelemetry | Trazas distribuidas para una sola Lambda: más piezas que problema. Queda para el Bloque B |
| Métricas detalladas de API Gateway (por ruta) | Se cobran como métricas custom; el access log da el detalle por pedido |
| Notificar por Slack (AWS Chatbot) | Más piezas y una integración externa para un solo usuario |
| Servicio externo (Datadog, Grafana Cloud) | Otra cuenta, datos fuera de AWS; el modelo self-hosted pide que todo viva en la cuenta del usuario (D48) |

## Ventajas

- Auditoría de cada cambio por usuario, y búsqueda por campo con Logs Insights.
- Los ataques contra las rutas reales quedan registrados con el motivo del rechazo.
- Email en menos de un minuto ante un error (verificado con un simulacro).
- USD 0 a esta escala.

## Desventajas

- HTTP API **no escribe access logs** de pedidos a rutas inexistentes: un escaneo de rutas solo se ve como un pico de `4xx`.
- Todo se configuró a mano en la consola y en CloudShell hasta la Etapa 12 (CDK). Configurar alarmas a mano resultó propenso a errores (3 correcciones, §4.7 del doc de la etapa).
- El valor que informa el email de una alarma puede ser parcial: el total se ve después.
- Los paneles de logs del dashboard escanean logs cada vez que se abren (costo bajo, pero no nulo fuera del free tier).

## Consideraciones de seguridad

- Minimización: se loguea el `sub`, no el email; nunca el body, el event completo ni tokens. El dashboard no muestra el `sub`.
- La IP es un dato personal: el access log tiene retención de 1 semana.
- El topic de SNS no se cifra: con la clave administrada por AWS, CloudWatch no podría publicar, y el contenido de una alarma no es secreto.
- Logs, alarmas y dashboard son controles **detectivos**: complementan, no reemplazan, al authorizer, IAM y el throttling.

## Consideraciones de costo

- Free tier de CloudWatch: 10 alarmas, 3 dashboards y 5 GB de logs (ingesta, almacenamiento y escaneo). Se usan 3, 1 y unos KB.
- SNS: 1.000 emails gratis por mes.
- Fuera del free tier: USD 0,10 por alarma por mes y USD 0,50 por GB ingerido. Verificar los precios vigentes antes de desplegar en otra cuenta.

## Consecuencias

- El backend usa `logging`, no `print`. Las claves de `extra` no pueden pisar atributos de `LogRecord`.
- Para buscar errores en el log de la Lambda: `ispresent(errorType)` (el runtime escribe `log_level`, no `level`).
- El `requestId` del access log se correlaciona con el `apigw_request_id` de la Lambda.
- La documentación tiene un marcador nuevo: `<email>` para la suscripción de SNS.

## Evolución futura

- **Etapa 12 (CDK):** log groups, access logs, alarmas, topic y dashboard como código.
- Alarma de `Duration` cerca del timeout; métricas custom de negocio (por ejemplo, findings por severidad en la Etapa 11).
- Ruta `$default` con authorizer si hace falta ver los escaneos de rutas.
- **Bloque B:** trazas (X-Ray u OpenTelemetry) si aparecen varios servicios encadenados.
