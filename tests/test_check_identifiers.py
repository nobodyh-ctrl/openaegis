"""Tests de scripts/check_identifiers.py: detecta valores reales y deja pasar los marcadores.

Los valores "reales" de ejemplo se arman concatenando, para que este mismo archivo
no dispare el chequeo cuando se revisa el repo.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_identifiers import find_identifiers, mask  # noqa: E402

FAKE_ACCOUNT = "1234" + "56789012"
FAKE_API_ID = "abcde" + "12345"
FAKE_DISTRIBUTION = "d1a2b3c4" + "d5e6f7"
FAKE_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


def kinds(text):
    return [kind for _, kind, _ in find_identifiers(text)]


class DetectaValoresRealesTests(unittest.TestCase):

    def test_id_de_cuenta_dentro_de_un_arn(self):
        text = f"arn:aws:lambda:us-east-1:{FAKE_ACCOUNT}:function:cloud-sec-checklist-api"
        self.assertEqual(kinds(text), ["ID de cuenta de AWS"])

    def test_id_de_cuenta_suelto(self):
        self.assertEqual(kinds(f'"Account": "{FAKE_ACCOUNT}"'), ["ID de cuenta de AWS"])

    def test_endpoint_de_api_gateway(self):
        text = f"https://{FAKE_API_ID}.execute-api.us-east-1.amazonaws.com/controls"
        self.assertEqual(kinds(text), ["ID de API Gateway"])

    def test_dominio_de_cloudfront(self):
        self.assertEqual(kinds(f"https://{FAKE_DISTRIBUTION}.cloudfront.net"), ["Dominio de CloudFront"])

    def test_access_key(self):
        self.assertEqual(kinds(f"aws_access_key_id = {FAKE_KEY}"), ["Access key de AWS"])

    def test_informa_el_numero_de_linea(self):
        hits = find_identifiers(f"linea 1\nlinea 2 {FAKE_ACCOUNT}\n")
        self.assertEqual(hits[0][0], 2)


class DejaPasarMarcadoresTests(unittest.TestCase):

    def test_marcadores_de_la_documentacion(self):
        text = (
            "arn:aws:lambda:us-east-1:<cuenta>:function:cloud-sec-checklist-api\n"
            "https://<api-id>.execute-api.us-east-1.amazonaws.com\n"
            "https://<distribucion>.cloudfront.net\n"
            "| `AKIA...` | Access key de largo plazo |\n"
        )
        self.assertEqual(find_identifiers(text), [])

    def test_uuids_fechas_y_hashes_no_son_cuentas(self):
        text = (
            "65f38383-241b-4e7b-aa38-123456789012\n"  # último bloque de un UUID con 12 dígitos
            "2026-10-15T22:03:37+00:00\n"
            "3d3c42e5aac5ba805825da76410c181273ba90b1\n"  # SHA de un commit
        )
        self.assertEqual(find_identifiers(text), [])


class MaskTests(unittest.TestCase):

    def test_nunca_muestra_el_valor_completo(self):
        self.assertEqual(mask(FAKE_ACCOUNT), "1234...")


if __name__ == "__main__":
    unittest.main()
