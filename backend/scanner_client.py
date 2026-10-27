"""Dispara la Lambda openaegis-scanner desde la API. Único módulo de la API que usa el cliente de Lambda."""

import json
import os

import boto3

# --- Cold start ---
SCANNER_FUNCTION = os.environ["SCANNER_FUNCTION"]
lambda_client = boto3.client("lambda")


def start_scan(requested_by):
    """Invocación ASINCRÓNICA (D93): Lambda encola el evento y responde 202 sin esperar al scan.
    Si el scanner falla, la API no se entera: lo ve la alarma openaegis-scanner-errors."""
    lambda_client.invoke(
        FunctionName=SCANNER_FUNCTION,
        InvocationType="Event",
        Payload=json.dumps({"requested_by": requested_by}).encode(),
    )
