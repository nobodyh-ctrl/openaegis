#!/usr/bin/env bash
# Sube el build de la SPA al bucket del stack OpenAegis (Etapa 12.5, D79). Se corre en CloudShell.
#
#   bash ~/openaegis/scripts/deploy_spa.sh [ruta/al/dist.zip]      (por defecto: ~/dist.zip)
#
# El build se hace en la PC (sin credenciales de AWS) y se sube a CloudShell con Actions → Upload
# file. Este script solo usa la CLI de AWS: saca el bucket y la distribución de los outputs del
# stack, verifica que el build sea de ESTE stack y sube en el orden que evita pantallas en blanco.
set -euo pipefail

ZIP="${1:-$HOME/dist.zip}"
STACK=OpenAegis

fail() { echo "ERROR: $*" >&2; exit 1; }

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

[ -f "$ZIP" ] || fail "no encuentro $ZIP (subilo con Actions → Upload file)"

BUCKET=$(output SpaBucket)
DIST=$(output DistributionId)
API_URL=$(output ApiUrl)
CLIENT_ID=$(output CognitoClientId)
[ -n "$BUCKET" ] && [ "$BUCKET" != "None" ] || fail "el stack no tiene el output SpaBucket (¿falta el cdk deploy del 12.5?)"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
unzip -q "$ZIP" -d "$WORK"
[ -f "$WORK/index.html" ] && [ -d "$WORK/assets" ] || fail "el zip tiene que tener index.html y assets/ en la raíz"

# La URL de la API y el client de Cognito quedan DENTRO del .js al compilar. Un build hecho con los
# valores de otro entorno daría 401 en cada pedido: mejor frenarlo acá. No se imprime ningún valor.
API_HOST=${API_URL#https://}
API_HOST=${API_HOST%/}
grep -rqF "$API_HOST" "$WORK/assets" || fail "el build no apunta a la API de este stack (revisá VITE_API_URL)"
grep -rqF "$CLIENT_ID" "$WORK/assets" || fail "el build no usa el app client de este stack (revisá VITE_COGNITO_CLIENT_ID)"

# Orden: assets → public/ → index.html. Si index.html llegara antes, podría apuntar a un .js que
# todavía no existe. Sin --delete: una pestaña abierta con el index.html anterior sigue pidiendo
# sus chunks viejos.
echo "1/4 assets/ (nombres con hash: 1 año, immutable)"
aws s3 sync "$WORK/assets" "s3://$BUCKET/assets" --only-show-errors \
  --cache-control "public, max-age=31536000, immutable"

echo "2/4 archivos de public/ (sin hash: 1 día)"
aws s3 sync "$WORK" "s3://$BUCKET" --only-show-errors \
  --exclude "assets/*" --exclude "index.html" --cache-control "public, max-age=86400"

echo "3/4 index.html (no-cache), al final"
aws s3 cp "$WORK/index.html" "s3://$BUCKET/index.html" --only-show-errors --cache-control "no-cache"

# "/" y "/index.html" son dos claves de caché distintas: "/" se sirve por el default root object.
echo "4/4 invalidación de / y /index.html (tarda 1-2 minutos)"
INVALIDATION=$(aws cloudfront create-invalidation --distribution-id "$DIST" \
  --paths "/" "/index.html" --query "Invalidation.Id" --output text)
aws cloudfront wait invalidation-completed --distribution-id "$DIST" --id "$INVALIDATION"

echo "Listo. La URL de la SPA es el output SpaUrl del stack."
