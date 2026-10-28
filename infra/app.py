"""Punto de entrada de la app de CDK (Etapa 12). `cdk synth` ejecuta este archivo (ver cdk.json).

Sin `env` (cuenta/región): el stack es "environment-agnostic", así que `cdk synth` no necesita
credenciales y corre igual en PowerShell, en CloudShell y en el CI (D59). La cuenta y la región
las pone `cdk deploy` con las credenciales de CloudShell.
"""

import aws_cdk as cdk

from openaegis.stack import OpenAegisStack

app = cdk.App()
OpenAegisStack(
    app,
    "OpenAegis",
    description="OpenAegis: controles de seguridad cloud y checks read-only (self-hosted, single-account).",
)
app.synth()
