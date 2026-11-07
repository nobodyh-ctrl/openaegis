"""Cognito: el User Pool, el app client de la SPA y el dominio del login (Etapa 12.4).

Replica la configuración de la Etapa 9 (D80, D81; docs/09-cognito.md §4.1) en un pool NUEVO, en
paralelo con el manual (D102). El usuario se crea a mano (nadie se registra solo) y registra su
TOTP en el primer login.

| Qué               | Valor                                                                      |
|-------------------|----------------------------------------------------------------------------|
| Registro          | cerrado: solo el admin crea usuarios                                       |
| MFA               | obligatorio, solo TOTP (sin SMS: cuesta y es el factor más débil)          |
| App client        | público, sin secret (lo reemplaza PKCE), solo Authorization Code           |
| Scopes            | openid + email                                                             |
| Callbacks         | solo localhost por ahora; el dominio de CloudFront se suma en el 12.5      |
| Tokens            | access e ID 60 min, refresh 12 h, revocación activa                        |
| Si se borra el stack | el pool SE CONSERVA: los usuarios con su MFA no se regeneran (como D106) |
"""

from aws_cdk import Aws, Duration, Fn, RemovalPolicy
from aws_cdk import aws_cognito as cognito
from constructs import Construct

LOCAL_SPA = "http://localhost:5173"


def _domain_prefix():
    """"openaegis-" + el primer tramo del UUID del stack: único en todo AWS y sin escribirlo en el repo.

    AWS::StackId = arn:aws:cloudformation:<región>:<cuenta>:stack/OpenAegis/<uuid>. Se toma el UUID
    (no la cuenta) para que la URL del login no exponga el ID de la cuenta.
    """
    stack_uuid = Fn.select(2, Fn.split("/", Aws.STACK_ID))
    return Fn.join("-", ["openaegis", Fn.select(0, Fn.split("-", stack_uuid))])


class Auth(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="openaegis-users",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            mfa=cognito.Mfa.REQUIRED,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Login de Cognito (hosted UI clásico): no necesita recursos de branding.
        self.domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=_domain_prefix()),
        )

        self.client = self.user_pool.add_client(
            "SpaClient",
            user_pool_client_name="openaegis-spa",
            generate_secret=False,
            # SRP: la contraseña nunca viaja. CDK suma ALLOW_REFRESH_TOKEN_AUTH solo.
            auth_flows=cognito.AuthFlow(user_srp=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
                callback_urls=[f"{LOCAL_SPA}/app/callback"],
                logout_urls=[f"{LOCAL_SPA}/app"],
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            access_token_validity=Duration.minutes(60),
            id_token_validity=Duration.minutes(60),
            refresh_token_validity=Duration.hours(12),
            enable_token_revocation=True,
            # "Usuario o contraseña incorrectos" en los dos casos: no se puede averiguar qué emails existen.
            prevent_user_existence_errors=True,
        )
