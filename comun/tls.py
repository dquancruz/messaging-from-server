"""TLS opcional para la conexión agente ↔ servidor."""

from __future__ import annotations

import ssl
from pathlib import Path


def crear_contexto_servidor(
    certificado: Path | str,
    clave: Path | str,
) -> ssl.SSLContext:
    """Contexto TLS del lado servidor (certificado propio)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=str(certificado), keyfile=str(clave))
    return ctx


def crear_contexto_cliente(ca_certificado: Path | str | None = None) -> ssl.SSLContext:
    """Contexto TLS del lado agente.

    Si se indica ``ca_certificado``, valida el certificado del servidor.
    Si no, acepta certificados autofirmados (útil en laboratorio).
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if ca_certificado is not None:
        ctx.load_verify_locations(cafile=str(ca_certificado))
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx
