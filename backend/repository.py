"""Único módulo que habla con DynamoDB. El resto del código no sabe que existe boto3."""

import os

import boto3
from boto3.dynamodb.conditions import Attr

# --- Cold start: se ejecuta una vez por entorno de ejecución ---
TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def _scan_all(**scan_kwargs):
    """Scan paginado: un Scan devuelve como máximo 1 MB por llamada."""
    items = []
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        scan_kwargs["ExclusiveStartKey"] = last_key


def list_controls():
    return _scan_all()


def get_control(control_id):
    """Retorna el control o None si no existe."""
    response = table.get_item(Key={"id": control_id})
    return response.get("Item")


def find_control_by_code(code):
    """Busca un control por code paginando el scan. Retorna el item o None."""
    # Sin Limit: en un Scan con filtro, Limit acota los items LEÍDOS, no los devueltos
    scan_kwargs = {"FilterExpression": Attr("code").eq(code)}
    while True:
        response = table.scan(**scan_kwargs)
        if response.get("Items"):
            return response["Items"][0]
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return None
        scan_kwargs["ExclusiveStartKey"] = last_key


def create_control(item):
    # put_item sobrescribe sin avisar si la clave existe; la condición lo impide
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")


def delete_control(control_id):
    """Elimina el control. Retorna el item eliminado o None si no existía."""
    try:
        response = table.delete_item(
            Key={"id": control_id},
            ConditionExpression="attribute_exists(id)",
            ReturnValues="ALL_OLD",
        )
        return response["Attributes"]
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return None


def set_control_status(control_id, status, updated_at):
    """Lo usa el scanner (D94). Escribe SOLO status y updated_at y no devuelve el item (ReturnValues NONE):
    la policy del scanner solo permite eso. Retorna False si el control ya no existe."""
    try:
        table.update_item(
            Key={"id": control_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},  # status es palabra reservada de DynamoDB
            ExpressionAttributeValues={":status": status, ":updated_at": updated_at},
            ConditionExpression="attribute_exists(id)",
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def update_control(control_id, fields):
    """Actualiza los campos indicados. Retorna el item actualizado o None si no existe."""
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": v for k, v in fields.items()}
    expression = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)

    try:
        response = table.update_item(
            Key={"id": control_id},
            UpdateExpression=expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(id)",
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"]
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return None
