/** Configuración de la app que no es secreta. Se lee al compilar (variables VITE_). */

/** Región que evalúa este despliegue (D5: una sola región). El ID de cuenta se muestra recién con Cognito (D64). */
export const AWS_REGION = import.meta.env.VITE_AWS_REGION ?? "us-east-1";

/** Repositorio del proyecto (público). */
export const REPO_URL = "https://github.com/nobodyh-ctrl/openaegis";
