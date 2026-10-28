"""Tests del stack de CDK, sin AWS: sintetizan la plantilla y revisan reglas de seguridad.

Corren desde infra/:  python -m unittest discover -s tests -v
Cada construct nuevo (12.3 en adelante) suma sus propios tests; estos son las reglas generales,
que tienen que seguir valiendo para cualquier recurso que se agregue.
"""

import unittest

import aws_cdk as cdk
from aws_cdk.assertions import Template

from openaegis.stack import OpenAegisStack


def synth_template():
    app = cdk.App()
    return Template.from_stack(OpenAegisStack(app, "OpenAegis"))


def iam_statements(template):
    """Todos los statements de IAM de la plantilla: policies sueltas, managed e inline de los roles."""
    resources = template.to_json().get("Resources", {})
    documents = []
    for resource in resources.values():
        props = resource.get("Properties", {})
        if resource["Type"] in ("AWS::IAM::Policy", "AWS::IAM::ManagedPolicy"):
            documents.append(props["PolicyDocument"])
        elif resource["Type"] == "AWS::IAM::Role":
            documents.extend(p["PolicyDocument"] for p in props.get("Policies", []))
    for document in documents:
        statements = document["Statement"]
        yield from statements if isinstance(statements, list) else [statements]


class StackRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()

    def test_ninguna_policy_da_todas_las_acciones_de_un_servicio(self):
        # Least privilege (AGENTS.md §8): acciones concretas. "*" o "s3:*" no pasan.
        # Se permiten comodines parciales que genera CDK, como "s3:GetObject*".
        for statement in iam_statements(self.template):
            if statement.get("Effect") != "Allow":
                continue
            actions = statement["Action"]
            for action in actions if isinstance(actions, list) else [actions]:
                with self.subTest(action=action):
                    self.assertNotEqual(action, "*")
                    self.assertFalse(action.endswith(":*"), f"acción demasiado amplia: {action}")

    def test_el_trail_de_cloudtrail_no_es_parte_del_stack(self):
        # El trail es configuración de la cuenta y es lo que OpenAegis evalúa:
        # `cdk destroy` no tiene que poder borrarlo.
        self.template.resource_count_is("AWS::CloudTrail::Trail", 0)

    def test_todo_lleva_la_etiqueta_del_proyecto(self):
        # Hoy el stack no tiene recursos; esta regla se vuelve útil desde 12.3.
        for logical_id, resource in self.template.to_json().get("Resources", {}).items():
            tags = resource.get("Properties", {}).get("Tags")
            if tags is None:
                continue  # no todos los tipos de recurso aceptan etiquetas
            with self.subTest(resource=logical_id):
                if isinstance(tags, dict):  # algunos tipos usan un mapa en vez de una lista
                    self.assertEqual(tags.get("project"), "openaegis")
                else:
                    self.assertIn({"Key": "project", "Value": "openaegis"}, tags)


if __name__ == "__main__":
    unittest.main()
