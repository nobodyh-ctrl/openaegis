"""La fachada: el bucket de la SPA y la distribución de CloudFront (Etapa 12.5).

Replica las Etapas 2, 3 y 8 (D9, D10, D13, D15-D17, D67, D101), sin mejoras: en una migración,
primero se mueve y después se mejora, de a una cosa por vez.

    navegador ──HTTPS──► CloudFront (OAC, error pages 403/404 → /index.html con 200)
                              └──► S3 privado: solo s3:GetObject, solo para ESTA distribución

El build NO lo sube CDK: lo sube scripts/deploy_spa.sh (D79). El build lleva adentro la URL de la
API y los datos de Cognito, que recién existen después del deploy del stack.

Si se borra el stack: el bucket se borra, pero solo si está vacío. Sin autoDeleteObjects, que
agregaría una Lambda con permiso de borrar objetos (ver infra/README.md, "Desinstalar").
"""

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from constructs import Construct


class Frontend(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        # Nombre generado por CDK: no se usa en comandos (sale del output SpaBucket).
        self.bucket = s3.Bucket(
            self,
            "Bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,  # sin ACLs
            encryption=s3.BucketEncryption.S3_MANAGED,  # SSE-S3, sin costo de KMS
            enforce_ssl=True,  # Deny con aws:SecureTransport=false (D101)
            versioned=False,  # D10: el contenido se regenera con un build
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Las rutas de la SPA (/app/controles) no existen en S3. Sin s3:ListBucket, S3 responde
        # 403 a una clave inexistente: las dos se resuelven con index.html y React dibuja la ruta.
        spa_routes = [
            cloudfront.ErrorResponse(
                http_status=code,
                response_http_status=200,
                response_page_path="/index.html",
                ttl=Duration.seconds(10),
            )
            for code in (403, 404)
        ]

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment="openaegis-spa",
            # OAC con el permiso mínimo por defecto de CDK: solo s3:GetObject, con
            # AWS:SourceArn = esta distribución.
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,  # respeta el Cache-Control de D79
            ),
            default_root_object="index.html",
            error_responses=spa_routes,
            enable_logging=False,  # D17
        )

        # Lo que necesitan Cognito (callbacks) y la API (CORS): una referencia, nunca un texto.
        self.domain_name = self.distribution.distribution_domain_name
        self.url = f"https://{self.domain_name}"
