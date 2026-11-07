"""Tests de frontend.py: el bucket de la SPA y la distribución de CloudFront (Etapa 12.5).

Replican las Etapas 2, 3 y 8 (D9, D10, D13, D15, D17, D67, D101). La regla central: el bucket es
privado y la ÚNICA forma de leerlo es a través de ESTA distribución, solo con s3:GetObject.
"""

import json
import unittest

from test_stack import synth_template

# Política de caché administrada "CachingOptimized" (la que la consola llama "recomendada").
CACHING_OPTIMIZED = "658327ea-f89d-4fab-a63d-7e88639e58f6"


def as_list(value):
    return value if isinstance(value, list) else [value]


class FrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()
        cls.resources = cls.template.to_json()["Resources"]

    def of_type(self, resource_type):
        return {lid: r for lid, r in self.resources.items() if r["Type"] == resource_type}

    def only(self, resource_type):
        found = self.of_type(resource_type)
        self.assertEqual(len(found), 1, f"se esperaba un solo {resource_type}")
        return next(iter(found.items()))

    def distribution_config(self):
        _, distribution = self.only("AWS::CloudFront::Distribution")
        return distribution["Properties"]["DistributionConfig"]

    # ---- Bucket ----

    def test_bucket_privado_con_bpa_completo_y_sin_acls(self):
        _, bucket = self.only("AWS::S3::Bucket")
        props = bucket["Properties"]
        self.assertEqual(
            props["PublicAccessBlockConfiguration"],
            {"BlockPublicAcls": True, "BlockPublicPolicy": True, "IgnorePublicAcls": True, "RestrictPublicBuckets": True},
        )
        self.assertEqual(props["OwnershipControls"]["Rules"], [{"ObjectOwnership": "BucketOwnerEnforced"}])

    def test_bucket_con_sse_s3_y_sin_versioning(self):
        _, bucket = self.only("AWS::S3::Bucket")
        props = bucket["Properties"]
        encryption = props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        self.assertEqual(encryption["ServerSideEncryptionByDefault"]["SSEAlgorithm"], "AES256")  # D9, sin KMS
        self.assertNotIn("VersioningConfiguration", props)  # D10

    def test_bucket_se_borra_con_el_stack_pero_sin_vaciado_automatico(self):
        # El contenido se regenera con un build. Sin autoDeleteObjects: agregaría una Lambda
        # con permiso de borrar objetos. `cdk destroy` pide vaciarlo antes (infra/README.md).
        _, bucket = self.only("AWS::S3::Bucket")
        self.assertEqual(bucket["DeletionPolicy"], "Delete")
        self.assertEqual(self.of_type("Custom::S3AutoDeleteObjects"), {})

    def test_bucket_policy_solo_tls_y_get_object_para_esta_distribucion(self):
        _, policy = self.only("AWS::S3::BucketPolicy")
        statements = as_list(policy["Properties"]["PolicyDocument"]["Statement"])
        self.assertEqual(len(statements), 2, "solo el Deny sin TLS y el Allow de CloudFront")

        deny = next(s for s in statements if s["Effect"] == "Deny")
        self.assertEqual(deny["Condition"], {"Bool": {"aws:SecureTransport": "false"}})  # D101

        allow = next(s for s in statements if s["Effect"] == "Allow")
        self.assertEqual(allow["Action"], "s3:GetObject")  # sin ListBucket (D67)
        self.assertEqual(allow["Principal"], {"Service": "cloudfront.amazonaws.com"})
        distribution_id, _ = self.only("AWS::CloudFront::Distribution")
        self.assertIn(distribution_id, json.dumps(allow["Condition"]["StringEquals"]["AWS:SourceArn"]))

    # ---- Distribución ----

    def test_origen_s3_con_oac(self):
        oac_id, oac = self.only("AWS::CloudFront::OriginAccessControl")
        config = oac["Properties"]["OriginAccessControlConfig"]
        self.assertEqual(config["OriginAccessControlOriginType"], "s3")
        self.assertEqual(config["SigningBehavior"], "always")
        origin = self.distribution_config()["Origins"][0]
        self.assertEqual(origin["OriginAccessControlId"], {"Fn::GetAtt": [oac_id, "Id"]})
        self.assertEqual(origin["S3OriginConfig"]["OriginAccessIdentity"], "")  # nada de OAI (D13)

    def test_https_obligatorio_y_cache_recomendada(self):
        behavior = self.distribution_config()["DefaultCacheBehavior"]
        self.assertEqual(behavior["ViewerProtocolPolicy"], "redirect-to-https")
        self.assertEqual(behavior["CachePolicyId"], CACHING_OPTIMIZED)

    def test_index_html_en_la_raiz_y_error_pages_de_la_spa(self):
        config = self.distribution_config()
        self.assertEqual(config["DefaultRootObject"], "index.html")
        expected = [
            {"ErrorCode": code, "ResponseCode": 200, "ResponsePagePath": "/index.html", "ErrorCachingMinTTL": 10}
            for code in (403, 404)
        ]
        self.assertCountEqual(config["CustomErrorResponses"], expected)  # D67

    def test_sin_waf_ni_logging(self):
        config = self.distribution_config()
        self.assertNotIn("WebACLId", config)  # D15
        self.assertNotIn("Logging", config)  # D17

    def test_el_frontend_no_agrega_lambdas(self):
        # Ni BucketDeployment ni autoDeleteObjects: la subida de la SPA es scripts/deploy_spa.sh.
        self.assertEqual(len(self.of_type("AWS::Lambda::Function")), 2)

    def test_outputs_para_desplegar_la_spa(self):
        outputs = self.template.to_json().get("Outputs", {})
        for name in ("SpaUrl", "SpaBucket", "DistributionId"):
            with self.subTest(output=name):
                self.assertIn(name, outputs)


if __name__ == "__main__":
    unittest.main()
