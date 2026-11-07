"""Tests de data.py: las tres tablas, sus claves y qué pasa con cada una en un `cdk destroy`."""

import unittest

from test_stack import synth_template


def table(template, name):
    tables = template.find_resources("AWS::DynamoDB::Table", {"Properties": {"TableName": name}})
    if len(tables) != 1:
        raise AssertionError(f"se esperaba una tabla {name}, hay {len(tables)}")
    return next(iter(tables.values()))


class DataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()

    def test_hay_tres_tablas(self):
        self.template.resource_count_is("AWS::DynamoDB::Table", 3)

    def test_claves_de_cada_tabla(self):
        # El backend depende de estas claves (ARCHITECTURE.md §4 y §4b): cambiarlas obliga a
        # reemplazar la tabla, y con eso se pierden los datos.
        expected = {
            "openaegis-controls": [{"AttributeName": "id", "KeyType": "HASH"}],
            "openaegis-findings": [
                {"AttributeName": "control_id", "KeyType": "HASH"},
                {"AttributeName": "resource_id", "KeyType": "RANGE"},
            ],
            "openaegis-scans": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "started_at", "KeyType": "RANGE"},
            ],
        }
        for name, key_schema in expected.items():
            with self.subTest(table=name):
                self.assertEqual(table(self.template, name)["Properties"]["KeySchema"], key_schema)

    def test_todas_on_demand_y_sin_indices(self):
        # On-demand: sin capacidad reservada que se pague aunque no haya tráfico.
        for name in ("openaegis-controls", "openaegis-findings", "openaegis-scans"):
            with self.subTest(table=name):
                props = table(self.template, name)["Properties"]
                self.assertEqual(props["BillingMode"], "PAY_PER_REQUEST")
                self.assertNotIn("GlobalSecondaryIndexes", props)

    def test_los_controles_sobreviven_a_un_destroy(self):
        controls = table(self.template, "openaegis-controls")
        # RetainExceptOnCreate = RETAIN_ON_UPDATE_OR_DELETE: si falla el deploy que la crea, se borra.
        self.assertEqual(controls["DeletionPolicy"], "RetainExceptOnCreate")
        self.assertEqual(controls["UpdateReplacePolicy"], "Retain")
        self.assertTrue(controls["Properties"]["DeletionProtectionEnabled"])

    def test_findings_y_scans_se_borran_con_el_stack(self):
        # Los regenera el próximo scan; dejarlos huérfanos haría fallar la reinstalación (nombre fijo).
        for name in ("openaegis-findings", "openaegis-scans"):
            with self.subTest(table=name):
                resource = table(self.template, name)
                self.assertEqual(resource["DeletionPolicy"], "Delete")
                self.assertEqual(resource["Properties"].get("DeletionProtectionEnabled", False), False)

    def test_cifrado_sin_kms_propio(self):
        # "Owned by DynamoDB": sin costo de KMS. Una clave propia costaría USD 1/mes.
        for resource in self.template.find_resources("AWS::DynamoDB::Table").values():
            sse = resource["Properties"].get("SSESpecification", {})
            self.assertNotIn("KMSMasterKeyId", sse)


if __name__ == "__main__":
    unittest.main()
