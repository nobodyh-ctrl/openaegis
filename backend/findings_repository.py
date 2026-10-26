"""Persistencia de findings y scans en DynamoDB. Como repository.py: el resto del código no sabe que existe boto3."""

import os

import boto3
from boto3.dynamodb.conditions import Key

# --- Cold start ---
dynamodb = boto3.resource("dynamodb")
findings_table = dynamodb.Table(os.environ["FINDINGS_TABLE"])
scans_table = dynamodb.Table(os.environ["SCANS_TABLE"])

# Todos los scans comparten la partición: Query + ScanIndexForward=False da el último, ya ordenado
SCAN_PK = "SCAN"


def _query_all(table, **query_kwargs):
    """Query paginado: como el Scan, devuelve como máximo 1 MB por llamada."""
    items = []
    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        query_kwargs["ExclusiveStartKey"] = last_key


def save_findings(findings):
    """Escribe (o pisa) cada finding. batch_writer agrupa de a 25 y reintenta los que DynamoDB no procesó."""
    with findings_table.batch_writer() as batch:
        for finding in findings:
            batch.put_item(Item=finding)


def delete_stale_findings(control_id, scan_id):
    """Borra los findings del control que NO escribió este scan: recursos que ya no existen. Retorna cuántos borró."""
    items = _query_all(
        findings_table,
        KeyConditionExpression=Key("control_id").eq(control_id),
        ProjectionExpression="resource_id, scan_id",
    )
    stale = [item for item in items if item.get("scan_id") != scan_id]
    with findings_table.batch_writer() as batch:
        for item in stale:
            batch.delete_item(Key={"control_id": control_id, "resource_id": item["resource_id"]})
    return len(stale)


def save_scan(summary):
    scans_table.put_item(Item={"pk": SCAN_PK, **summary})
