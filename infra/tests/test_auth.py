"""Tests de auth.py: el User Pool y el app client de Cognito (Etapa 12.4).

Replican la configuración de la Etapa 9 (D80, docs/09-cognito.md §4.1). Cada test es una regla de
seguridad: si alguien abre el registro, saca el MFA o agrega un scope, el test falla.
"""

import json
import unittest

from test_stack import synth_template


class AuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synth_template()
        cls.resources = cls.template.to_json()["Resources"]

    def only(self, resource_type):
        found = [r for r in self.resources.values() if r["Type"] == resource_type]
        self.assertEqual(len(found), 1, f"se esperaba un solo {resource_type}")
        return found[0]

    # ---- User Pool ----

    def test_mfa_obligatorio_solo_con_app_autenticadora(self):
        props = self.only("AWS::Cognito::UserPool")["Properties"]
        self.assertEqual(props["MfaConfiguration"], "ON")
        # Sin SMS: cuesta (SNS) y es el factor más débil (SIM swapping).
        self.assertEqual(props["EnabledMfas"], ["SOFTWARE_TOKEN_MFA"])

    def test_nadie_se_registra_solo(self):
        props = self.only("AWS::Cognito::UserPool")["Properties"]
        self.assertTrue(props["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"])

    def test_plan_essentials(self):
        props = self.only("AWS::Cognito::UserPool")["Properties"]
        self.assertEqual(props["UserPoolTier"], "ESSENTIALS")

    def test_recuperacion_de_cuenta_solo_por_email(self):
        # Sin SMS (costo de SNS y no hay teléfonos cargados).
        props = self.only("AWS::Cognito::UserPool")["Properties"]
        self.assertEqual(
            props["AccountRecoverySetting"]["RecoveryMechanisms"],
            [{"Name": "verified_email", "Priority": 1}],
        )

    def test_el_pool_se_conserva_y_esta_protegido(self):
        # Los usuarios, con su MFA registrado, no se regeneran: como la tabla de controles (D106).
        pool = self.only("AWS::Cognito::UserPool")
        self.assertEqual(pool["Properties"]["DeletionProtection"], "ACTIVE")
        self.assertEqual(pool["DeletionPolicy"], "Retain")
        self.assertEqual(pool["UpdateReplacePolicy"], "Retain")

    # ---- App client ----

    def test_app_client_publico_sin_secret(self):
        # Una SPA no puede guardar un secret: lo reemplaza PKCE.
        props = self.only("AWS::Cognito::UserPoolClient")["Properties"]
        self.assertFalse(props["GenerateSecret"])

    def test_solo_authorization_code_con_openid_y_email(self):
        props = self.only("AWS::Cognito::UserPoolClient")["Properties"]
        self.assertTrue(props["AllowedOAuthFlowsUserPoolClient"])
        self.assertEqual(props["AllowedOAuthFlows"], ["code"])
        self.assertCountEqual(props["AllowedOAuthScopes"], ["openid", "email"])
        self.assertEqual(props["SupportedIdentityProviders"], ["COGNITO"])

    def test_callbacks_solo_de_localhost_por_ahora(self):
        # El dominio de CloudFront se suma en el 12.5, como referencia (nunca escrito en el repo).
        props = self.only("AWS::Cognito::UserPoolClient")["Properties"]
        self.assertEqual(props["CallbackURLs"], ["http://localhost:5173/app/callback"])
        self.assertEqual(props["LogoutURLs"], ["http://localhost:5173/app"])

    def test_duracion_de_tokens_y_revocacion(self):
        props = self.only("AWS::Cognito::UserPoolClient")["Properties"]
        minutes = {"AccessToken": "minutes", "IdToken": "minutes", "RefreshToken": "minutes"}
        self.assertEqual(props["TokenValidityUnits"], minutes)
        self.assertEqual(props["AccessTokenValidity"], 60)
        self.assertEqual(props["IdTokenValidity"], 60)
        self.assertEqual(props["RefreshTokenValidity"], 720)  # 12 h (D81)
        self.assertTrue(props["EnableTokenRevocation"])

    def test_flujos_de_autenticacion_minimos(self):
        # SRP (la contraseña nunca viaja) + refresh. Sin USER_PASSWORD_AUTH ni CUSTOM_AUTH.
        props = self.only("AWS::Cognito::UserPoolClient")["Properties"]
        self.assertCountEqual(props["ExplicitAuthFlows"], ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"])

    def test_no_revela_si_un_usuario_existe(self):
        props = self.only("AWS::Cognito::UserPoolClient")["Properties"]
        self.assertEqual(props["PreventUserExistenceErrors"], "ENABLED")

    # ---- Dominio del login ----

    def test_prefijo_del_dominio_derivado_del_id_del_stack(self):
        # Único en todo AWS sin escribirlo en el repo: "openaegis-" + un tramo del UUID del stack.
        domain = self.only("AWS::Cognito::UserPoolDomain")["Properties"]["Domain"]
        self.assertIsInstance(domain, dict, "el prefijo no puede ser un texto fijo")
        rendered = json.dumps(domain)
        self.assertIn("openaegis", rendered)
        self.assertIn("AWS::StackId", rendered)


if __name__ == "__main__":
    unittest.main()
