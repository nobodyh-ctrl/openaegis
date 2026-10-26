"""Tests de checks.py con clientes FALSOS: no tocan AWS ni necesitan boto3."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from checks import (  # noqa: E402
    ACCOUNT_RESOURCE,
    CHECK_RESOURCE,
    ScanContext,
    run_checks,
    s3_account_public_access_block,
)


# --- Imitación mínima de un cliente de boto3 ---------------------------------

class FakeClientError(Exception):
    """Como botocore.exceptions.ClientError: el código viene en response["Error"]["Code"]."""

    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeNoSuchPublicAccessBlockConfiguration(FakeClientError):
    def __init__(self):
        super().__init__("NoSuchPublicAccessBlockConfiguration")


class FakeExceptions:
    ClientError = FakeClientError
    NoSuchPublicAccessBlockConfiguration = FakeNoSuchPublicAccessBlockConfiguration


class FakeS3Control:
    exceptions = FakeExceptions

    def __init__(self, config=None, error=None):
        self.config = config
        self.error = error
        self.calls = []

    def get_public_access_block(self, AccountId):
        self.calls.append(AccountId)
        if self.error:
            raise self.error
        return {"PublicAccessBlockConfiguration": self.config}


ALL_TRUE = {
    "BlockPublicAcls": True,
    "IgnorePublicAcls": True,
    "BlockPublicPolicy": True,
    "RestrictPublicBuckets": True,
}


def context_with(fake):
    return ScanContext(client=lambda service_name: fake, account_id="cuenta-de-prueba")


# --- Tests ------------------------------------------------------------------

class S3AccountPublicAccessBlockTests(unittest.TestCase):

    def test_las_4_activadas_es_pass(self):
        [result] = s3_account_public_access_block(context_with(FakeS3Control(config=ALL_TRUE)))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["resource_id"], ACCOUNT_RESOURCE)

    def test_una_desactivada_es_fail_y_la_nombra(self):
        fake = FakeS3Control(config={**ALL_TRUE, "BlockPublicPolicy": False})
        [result] = s3_account_public_access_block(context_with(fake))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("BlockPublicPolicy", result["evidence"])
        self.assertNotIn("IgnorePublicAcls", result["evidence"])

    def test_opcion_ausente_cuenta_como_desactivada(self):
        config = {k: v for k, v in ALL_TRUE.items() if k != "RestrictPublicBuckets"}
        [result] = s3_account_public_access_block(context_with(FakeS3Control(config=config)))
        self.assertEqual(result["status"], "FAIL")

    def test_nunca_configurado_es_fail_no_error(self):
        fake = FakeS3Control(error=FakeNoSuchPublicAccessBlockConfiguration())
        [result] = s3_account_public_access_block(context_with(fake))
        self.assertEqual(result["status"], "FAIL")

    def test_access_denied_es_error_no_pass(self):
        fake = FakeS3Control(error=FakeClientError("AccessDenied"))
        [result] = s3_account_public_access_block(context_with(fake))
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("AccessDenied", result["evidence"])

    def test_usa_el_id_de_cuenta_del_contexto(self):
        fake = FakeS3Control(config=ALL_TRUE)
        s3_account_public_access_block(context_with(fake))
        self.assertEqual(fake.calls, ["cuenta-de-prueba"])


class RunChecksTests(unittest.TestCase):

    def test_agrega_control_id_y_check_id(self):
        controls = [{"id": "c-1", "check_id": "s3-account-public-access-block"}]
        [finding] = run_checks(controls, context_with(FakeS3Control(config=ALL_TRUE)))
        self.assertEqual(finding["control_id"], "c-1")
        self.assertEqual(finding["check_id"], "s3-account-public-access-block")
        self.assertEqual(finding["status"], "PASS")

    def test_check_inexistente_es_error(self):
        [finding] = run_checks([{"id": "c-1", "check_id": "no-existe"}], context_with(FakeS3Control()))
        self.assertEqual(finding["status"], "ERROR")
        self.assertEqual(finding["resource_id"], CHECK_RESOURCE)

    def test_sin_controles_no_hay_findings(self):
        self.assertEqual(run_checks([], context_with(FakeS3Control())), [])


if __name__ == "__main__":
    unittest.main()
