"""El stack de OpenAegis: UN solo stack, organizado en constructs por área.

Un stack (y no varios) para que instalar y desinstalar sea un solo `cdk deploy` / `cdk destroy`,
sin referencias entre stacks. Cada área va en su propio módulo y se suma acá:

    data.py           (12.3) tablas de controles, findings y scans
    compute.py        (12.3) Lambdas de la API y del scanner, con sus roles
    auth.py           (12.4) Cognito User Pool
    api.py            (12.4) HTTP API + JWT authorizer
    frontend.py       (12.5) S3 + CloudFront
    observability.py  (12.6) alarmas, SNS y dashboard

Fuera del stack, a propósito: el trail de CloudTrail. Es configuración de la cuenta y es
justamente lo que OpenAegis evalúa; `cdk destroy` no tiene que poder borrarlo.
"""

from aws_cdk import CfnOutput, Stack, Tags
from constructs import Construct

from openaegis.api import Api
from openaegis.auth import Auth
from openaegis.compute import Compute
from openaegis.data import Data


class OpenAegisStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        # Sin telemetría de CDK (el recurso CDKMetadata): una herramienta de seguridad que alguien
        # instala en su cuenta no manda datos que el usuario no eligió.
        super().__init__(scope, construct_id, analytics_reporting=False, **kwargs)

        # Todos los recursos del stack llevan esta etiqueta: sirve para filtrar costos y para
        # distinguirlos de los recursos creados a mano durante la migración.
        Tags.of(self).add("project", "openaegis")

        self.data = Data(self, "Data")
        self.compute = Compute(self, "Compute", data=self.data)
        self.auth = Auth(self, "Auth")
        self.api = Api(self, "Api", function=self.compute.api, auth=self.auth)

        # Lo que la SPA necesita para apuntar al stack (frontend/.env.local). No son secretos: quedan
        # visibles en el .js de la SPA. Pero son identificadores de la cuenta: no van al repo.
        CfnOutput(self, "ApiUrl", value=self.api.stage.url, description="API_PROXY_TARGET / VITE_API_URL")
        CfnOutput(self, "CognitoAuthority", value=self.auth.user_pool.user_pool_provider_url,
                  description="VITE_COGNITO_AUTHORITY")
        CfnOutput(self, "CognitoClientId", value=self.auth.client.user_pool_client_id,
                  description="VITE_COGNITO_CLIENT_ID")
        CfnOutput(self, "CognitoDomain", value=self.auth.domain.base_url(), description="VITE_COGNITO_DOMAIN")
