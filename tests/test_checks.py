"""Tests de checks.py con clientes FALSOS: no tocan AWS ni necesitan boto3."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import json  # noqa: E402

from checks import (  # noqa: E402
    ACCOUNT_RESOURCE,
    CHECK_RESOURCE,
    ROOT_RESOURCE,
    ScanContext,
    cloudtrail_multi_region_logging,
    control_status,
    iam_root_mfa,
    run_checks,
    s3_account_public_access_block,
    s3_bucket_public_access_block,
    s3_bucket_tls_only,
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


class FakeS3:
    """Cliente de S3 falso. En S3, NoSuchPublicAccessBlockConfiguration y NoSuchBucketPolicy
    NO son excepciones modeladas: llegan como ClientError con ese código."""

    exceptions = FakeExceptions

    def __init__(self, buckets, bpa=None, policies=None, list_error=None):
        self.buckets = buckets
        self.bpa = bpa or {}            # nombre → config, o una excepción
        self.policies = policies or {}  # nombre → dict de policy, o una excepción
        self.list_error = list_error

    def list_buckets(self):
        if self.list_error:
            raise self.list_error
        return {"Buckets": [{"Name": name} for name in self.buckets]}

    def get_public_access_block(self, Bucket):
        value = self.bpa.get(Bucket, FakeClientError("NoSuchPublicAccessBlockConfiguration"))
        if isinstance(value, Exception):
            raise value
        return {"PublicAccessBlockConfiguration": value}

    def get_bucket_policy(self, Bucket):
        value = self.policies.get(Bucket, FakeClientError("NoSuchBucketPolicy"))
        if isinstance(value, Exception):
            raise value
        return {"Policy": json.dumps(value)}


def context_with_clients(**clients):
    return ScanContext(client=lambda service_name: clients[service_name], account_id="cuenta-de-prueba")


def by_resource(results):
    return {r["resource_id"]: r for r in results}


TLS_DENY = {
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:*",
    "Resource": ["arn:aws:s3:::b", "arn:aws:s3:::b/*"],
    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
}


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



class S3BucketPublicAccessBlockTests(unittest.TestCase):

    def test_bucket_con_las_4_es_pass(self):
        s3 = FakeS3(["a"], bpa={"a": ALL_TRUE})
        [result] = s3_bucket_public_access_block(context_with_clients(s3=s3, s3control=FakeS3Control(config={})))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["resource_id"], "arn:aws:s3:::a")

    def test_sin_bpa_propio_pero_cuenta_cubre_es_pass_con_evidencia(self):
        s3 = FakeS3(["a"])  # sin configuración propia
        [result] = s3_bucket_public_access_block(context_with_clients(s3=s3, s3control=FakeS3Control(config=ALL_TRUE)))
        self.assertEqual(result["status"], "PASS")
        self.assertIn("cuenta", result["evidence"])

    def test_sin_bpa_propio_ni_de_la_cuenta_es_fail(self):
        s3 = FakeS3(["a"])
        control = FakeS3Control(error=FakeNoSuchPublicAccessBlockConfiguration())
        [result] = s3_bucket_public_access_block(context_with_clients(s3=s3, s3control=control))
        self.assertEqual(result["status"], "FAIL")

    def test_un_finding_por_bucket_y_error_aislado(self):
        s3 = FakeS3(["a", "b"], bpa={"a": ALL_TRUE, "b": FakeClientError("AccessDenied")})
        results = by_resource(s3_bucket_public_access_block(context_with_clients(s3=s3, s3control=FakeS3Control(config={}))))
        self.assertEqual(results["arn:aws:s3:::a"]["status"], "PASS")
        self.assertEqual(results["arn:aws:s3:::b"]["status"], "ERROR")

    def test_no_poder_listar_es_un_error_del_check(self):
        s3 = FakeS3([], list_error=FakeClientError("AccessDenied"))
        [result] = s3_bucket_public_access_block(context_with_clients(s3=s3, s3control=FakeS3Control(config={})))
        self.assertEqual((result["resource_id"], result["status"]), (CHECK_RESOURCE, "ERROR"))

    def test_sin_buckets_no_hay_findings(self):
        self.assertEqual(s3_bucket_public_access_block(context_with_clients(s3=FakeS3([]), s3control=FakeS3Control(config={}))), [])


class S3BucketTlsOnlyTests(unittest.TestCase):

    def run_check(self, policy):
        s3 = FakeS3(["b"], policies={} if policy is None else {"b": policy})
        [result] = s3_bucket_tls_only(context_with_clients(s3=s3))
        return result

    def test_deny_sin_tls_es_pass(self):
        self.assertEqual(self.run_check({"Statement": [TLS_DENY]})["status"], "PASS")

    def test_sin_bucket_policy_es_fail(self):
        self.assertEqual(self.run_check(None)["status"], "FAIL")

    def test_policy_sin_el_deny_es_fail(self):
        oac = {"Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"}, "Action": "s3:GetObject"}
        self.assertEqual(self.run_check({"Statement": [oac]})["status"], "FAIL")

    def test_allow_condicionado_no_alcanza(self):
        allow = {**TLS_DENY, "Effect": "Allow", "Condition": {"Bool": {"aws:SecureTransport": "true"}}}
        self.assertEqual(self.run_check({"Statement": [allow]})["status"], "FAIL")

    def test_deny_solo_de_algunas_acciones_no_alcanza(self):
        partial = {**TLS_DENY, "Action": "s3:GetObject"}
        self.assertEqual(self.run_check({"Statement": [partial]})["status"], "FAIL")

    def test_clave_en_mayusculas_y_valor_booleano(self):
        st = {**TLS_DENY, "Principal": {"AWS": "*"}, "Action": ["s3:*"],
              "Condition": {"Bool": {"AWS:SecureTransport": False}}}
        self.assertEqual(self.run_check({"Statement": st})["status"], "PASS")  # Statement como objeto, no lista

    def test_error_al_leer_la_policy_es_error(self):
        s3 = FakeS3(["b"], policies={"b": FakeClientError("AccessDenied")})
        [result] = s3_bucket_tls_only(context_with_clients(s3=s3))
        self.assertEqual(result["status"], "ERROR")


class FakeCloudTrail:
    exceptions = FakeExceptions

    def __init__(self, trails, logging=None, error=None):
        self.trails = trails
        self.logging = logging or {}  # ARN → bool
        self.error = error
        self.describe_kwargs = None

    def describe_trails(self, **kwargs):
        self.describe_kwargs = kwargs
        if self.error:
            raise self.error
        return {"trailList": self.trails}

    def get_trail_status(self, Name):
        return {"IsLogging": self.logging.get(Name, False)}


def trail(name, multi_region=True):
    return {"Name": name, "TrailARN": f"arn:aws:cloudtrail:us-east-1:cuenta-de-prueba:trail/{name}", "IsMultiRegionTrail": multi_region}


class CloudTrailTests(unittest.TestCase):

    def run_check(self, fake):
        [result] = cloudtrail_multi_region_logging(context_with_clients(cloudtrail=fake))
        return result

    def test_multi_region_logueando_es_pass(self):
        t = trail("principal")
        result = self.run_check(FakeCloudTrail([t], logging={t["TrailARN"]: True}))
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("cuenta-de-prueba", result["evidence"])  # la evidencia lleva el nombre, no el ARN

    def test_sin_trails_es_fail(self):
        self.assertEqual(self.run_check(FakeCloudTrail([]))["status"], "FAIL")

    def test_solo_trails_de_una_region_es_fail(self):
        t = trail("regional", multi_region=False)
        self.assertEqual(self.run_check(FakeCloudTrail([t], logging={t["TrailARN"]: True}))["status"], "FAIL")

    def test_multi_region_detenido_es_fail(self):
        result = self.run_check(FakeCloudTrail([trail("detenido")]))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("detenido", result["evidence"])

    def test_incluye_los_trails_de_otras_regiones(self):
        fake = FakeCloudTrail([])
        self.run_check(fake)
        self.assertEqual(fake.describe_kwargs, {"includeShadowTrails": True})

    def test_access_denied_es_error(self):
        self.assertEqual(self.run_check(FakeCloudTrail([], error=FakeClientError("AccessDenied")))["status"], "ERROR")


class FakeIam:
    exceptions = FakeExceptions

    def __init__(self, summary=None, error=None):
        self.summary = summary or {}
        self.error = error

    def get_account_summary(self):
        if self.error:
            raise self.error
        return {"SummaryMap": self.summary}


class IamRootMfaTests(unittest.TestCase):

    def run_check(self, fake):
        [result] = iam_root_mfa(context_with_clients(iam=fake))
        self.assertEqual(result["resource_id"], ROOT_RESOURCE)
        return result["status"]

    def test_con_mfa_es_pass(self):
        self.assertEqual(self.run_check(FakeIam({"AccountMFAEnabled": 1})), "PASS")

    def test_sin_mfa_es_fail(self):
        self.assertEqual(self.run_check(FakeIam({"AccountMFAEnabled": 0})), "FAIL")

    def test_access_denied_es_error(self):
        self.assertEqual(self.run_check(FakeIam(error=FakeClientError("AccessDenied"))), "ERROR")


class ControlStatusTests(unittest.TestCase):
    """Status de un control automático a partir de sus findings (D94)."""

    def test_todos_pass_es_pass(self):
        self.assertEqual(control_status(["PASS", "PASS"]), "PASS")

    def test_un_fail_manda_aunque_haya_error(self):
        self.assertEqual(control_status(["PASS", "ERROR", "FAIL"]), "FAIL")

    def test_un_error_sin_fail_es_review(self):
        self.assertEqual(control_status(["PASS", "ERROR"]), "REVIEW")

    def test_sin_findings_es_review(self):
        self.assertEqual(control_status([]), "REVIEW")


if __name__ == "__main__":
    unittest.main()
