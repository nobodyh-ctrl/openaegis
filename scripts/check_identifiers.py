"""Falla si algún archivo versionado contiene un identificador real de AWS.

La documentación usa marcadores (<cuenta>, <api-id>, <distribucion>); este chequeo
detecta cuando, por error, se pega el valor real. Revisa los archivos que devuelve
`git ls-files` y también el XML que los diagramas .drawio.png llevan embebido.

Salida: código 0 si no encuentra nada; 1 si encuentra algo (con archivo y línea).
"""

import re
import struct
import subprocess
import sys
import urllib.parse

PATTERNS = {
    # 12 dígitos sueltos: un ID de cuenta (dentro de un ARN o solo).
    # Los límites (?<![\w-]) / (?![\w-]) evitan falsos positivos dentro de UUIDs o hashes.
    "ID de cuenta de AWS": re.compile(r"(?<![\w-])\d{12}(?![\w-])"),
    # Endpoint de una API de API Gateway: <api-id de 10 caracteres>.execute-api.<región>
    "ID de API Gateway": re.compile(r"\b[a-z0-9]{10}\.execute-api\.[a-z0-9-]+\.amazonaws\.com"),
    # Dominio de una distribución de CloudFront: d<id>.cloudfront.net
    "Dominio de CloudFront": re.compile(r"\bd[a-z0-9]{8,}\.cloudfront\.net"),
    # Access key de largo plazo (AKIA) o temporal (ASIA)
    "Access key de AWS": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def find_identifiers(text):
    """Devuelve una lista de (número de línea, tipo, valor encontrado)."""
    hits = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                hits.append((line_no, kind, match.group(0)))
    return hits


def drawio_xml(data):
    """Extrae el XML que draw.io guarda en el chunk tEXt 'mxfile' de un PNG ('' si no tiene)."""
    i = 8  # salteamos la firma del PNG
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        chunk_type = data[i + 4:i + 8]
        if chunk_type == b"tEXt":
            keyword, _, value = data[i + 8:i + 8 + length].partition(b"\0")
            if keyword == b"mxfile":
                return urllib.parse.unquote(value.decode("latin-1"))
        i += 12 + length
    return ""


def mask(value):
    """Nunca se imprime el valor completo: los logs de un repo público también son públicos."""
    return value[:4] + "..." if len(value) > 4 else "..."


def main():
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
    found = 0
    for path in files:
        with open(path, "rb") as f:
            data = f.read()
        if path.endswith(".png"):
            text = drawio_xml(data)
        elif b"\0" in data:
            continue  # otro archivo binario: no hay texto que revisar
        else:
            text = data.decode("utf-8", errors="replace")
        for line_no, kind, value in find_identifiers(text):
            print(f"{path}:{line_no}: posible {kind} ({mask(value)}). Reemplazalo por un marcador.")
            found += 1

    if found:
        print(f"\n{found} identificador(es) encontrado(s). Usá <cuenta>, <api-id>, <distribucion>, etc.")
        return 1
    print(f"OK: {len(files)} archivos revisados, sin identificadores reales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
