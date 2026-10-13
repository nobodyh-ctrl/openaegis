# ADR-005: Modelo de despliegue self-hosted y single-account

- **Estado:** aceptada
- **Fecha:** 2026-10-10 (Etapa 6)
- **Decisiones relacionadas:** D48, D2 ([DECISIONS.md](../DECISIONS.md))

## Contexto

Surgió la pregunta de **cómo usaría OpenAegis otra persona**: ¿una CLI, una web? ¿Sus datos quedan en la nube de quien desarrolló la app, o cada uno tiene la suya? La respuesta define dónde viven los datos, quién paga, qué permisos hacen falta y cuánta complejidad tiene la V1. Los **findings** son datos muy sensibles: un finding dice, por ejemplo, *"el bucket X de esta cuenta es público"*. Una tabla de findings es un **mapa de las debilidades** de la cuenta.

## Decisión

En la V1, OpenAegis es **self-hosted y single-account**: cada usuario despliega su **propia copia** en **su** cuenta de AWS (`git clone` + `cdk deploy`, desde la Etapa 12), y la app evalúa **esa misma cuenta**, con permisos de solo lectura.

```text
CUENTA AWS DEL USUARIO
┌──────────────────────────────────────────────────────────┐
│  OpenAegis: CloudFront + S3 · API Gateway + Lambda ·      │
│             DynamoDB (controles y findings) · rol de      │
│             checks read-only                              │
│        │ lee la configuración (Get*/List*/Describe*)      │
│        ▼                                                  │
│  Los recursos del usuario (S3, IAM, CloudTrail…)          │
└──────────────────────────────────────────────────────────┘
```

## Por qué

- **Los datos nunca salen de la cuenta del usuario.** Nadie más tiene el "mapa de debilidades".
- **Cada uno paga su consumo**, en su propia factura.
- **Los permisos se pueden auditar antes de instalar:** al ser open source, `cdk diff` muestra exactamente qué permisos (read-only) se van a crear.
- Es lo más simple que cumple el objetivo, y coherente con un proyecto open source.

## Alternativas consideradas

| Modelo | Cómo funciona | Por qué no en la V1 |
|---|---|---|
| **CLI local** | El usuario corre los checks en su máquina, con sus credenciales | No ejercita la arquitectura web que el proyecto quiere aprender; queda como idea para reutilizar los checks [PROPUESTA] |
| **SaaS multi-tenant** | Una sola plataforma; cada cliente le da un rol read-only (cross-account con ExternalId) | Findings de **todos** los clientes en una sola nube, aislamiento entre tenants, auth multi-organización, el operador paga el cómputo de todos, cumplimiento. Mucho más grande |
| **Híbrido** | El escáner corre en la cuenta del cliente y envía los findings a una plataforma central | Combina la complejidad de los dos |
| **Multi-cuenta** (una instalación evalúa varias cuentas) | Cross-account roles | Lo habitual es hacerlo con AWS Organizations, que en el **Free plan pasa la cuenta al Paid plan y hace vencer los créditos** (D2) |

## Ventajas

- Privacidad y control total del usuario sobre sus datos.
- Sin infraestructura compartida que operar ni aislamiento entre clientes que garantizar.
- Confianza: la herramienta pide solo lectura, y se puede verificar.

## Desventajas

- **Hoy no es reproducible:** la infraestructura se creó a mano. Sin IaC, otra persona tendría que seguir los docs y hacer decenas de clics. **La Etapa 12 (CDK) es lo que hace viable este modelo.**
- Hace falta una instalación por cuenta: una organización con varias cuentas necesitaría varias copias.
- El usuario necesita credenciales con permisos para desplegar (y la primera vez, `cdk bootstrap`).
- Hay que decidir qué regiones evalúa cada check: IAM es global, CloudTrail es regional.

## Consideraciones de seguridad

- Los findings nunca cruzan cuentas: no hay riesgo de *tenant isolation* ni de *confused deputy*.
- El rol de checks tiene que ser estrictamente read-only. Queda pendiente decidir entre `SecurityAudit` (administrada por AWS, más amplia) y una policy propia mínima (Etapa 11).
- La app desplegada tiene acceso de lectura a la configuración de toda la cuenta: proteger su API (Cognito, Etapa 9) es parte del modelo.

## Consideraciones de costo

Cada usuario paga lo que consume en su cuenta; con el diseño serverless, centavos. No hay un costo central que crezca con la cantidad de usuarios.

## Consecuencias

- El README tiene una sección **"Deployment model"** que lo explica.
- CDK (Etapa 12) pasa de "buena práctica" a **requisito** del modelo.
- Los checks se diseñan como un módulo separado de la API, lo que habilita una CLI futura sin reescribirlos.

## Evolución futura

En la revisión **V1 → V2**: evaluar multi-cuenta (cross-account roles con ExternalId, teniendo en cuenta la restricción del Free plan), una CLI que reutilice los checks y, solo si aparece un motivo real, un modelo SaaS.
