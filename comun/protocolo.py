"""Protocolo de mensajería entre agente y servidor.

Cada mensaje es un objeto JSON en UTF-8, en una sola línea terminada en
``\\n``. Este módulo sabe codificar y decodificar esas líneas, y validar
que cada mensaje tenga los campos que le corresponden según su ``tipo``.

Ver ``docs/protocolo.md`` para la tabla completa de tipos de mensaje.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Constantes del protocolo
# ---------------------------------------------------------------------------

VERSION_PROTOCOLO = 1

PUERTO_AGENTES_POR_DEFECTO = 5050
PUERTO_PANEL_POR_DEFECTO = 8080

# Latido: el agente manda "ping" cada INTERVALO_PING segundos. El servidor
# considera desconectado a un equipo si pasan TIMEOUT_DESCONEXION segundos
# sin recibir nada de él.
INTERVALO_PING = 15
TIMEOUT_DESCONEXION = 45

# Espera creciente de reconexión del agente (tope 30s), en segundos.
ESPERAS_RECONEXION = (1, 2, 4, 8, 16, 30)

# Un mensaje (la línea JSON completa, con el "\n") de más de esto se rechaza.
TAMANO_MAXIMO_MENSAJE = 64 * 1024  # 64 KB

SISTEMAS_OPERATIVOS_VALIDOS = frozenset({"windows", "linux", "macos"})
NIVELES_VALIDOS = frozenset({"info", "aviso", "critico"})


class ErrorProtocolo(Exception):
    """Un mensaje no cumple el protocolo (JSON inválido, tipo desconocido,
    campo faltante, o demasiado grande)."""


# ---------------------------------------------------------------------------
# Campos requeridos por tipo de mensaje
# ---------------------------------------------------------------------------

# Agente -> servidor
_CAMPOS_AGENTE_SERVIDOR: dict[str, frozenset[str]] = {
    "hola": frozenset(
        {"token", "equipo", "so", "version_so", "usuario", "version_agente"}
    ),
    "visto": frozenset({"id"}),
    "ping": frozenset(),
}

# Servidor -> agente
_CAMPOS_SERVIDOR_AGENTE: dict[str, frozenset[str]] = {
    "bienvenido": frozenset({"sesion", "bloqueado"}),
    "rechazado": frozenset({"motivo"}),
    "mensaje": frozenset({"id", "titulo", "texto", "nivel", "pedir_visto"}),
    "sesion": frozenset({"restante"}),
    "bloquear": frozenset({"texto"}),
    "desbloquear": frozenset(),
    "pong": frozenset(),
}

CAMPOS_REQUERIDOS: dict[str, frozenset[str]] = {
    **_CAMPOS_AGENTE_SERVIDOR,
    **_CAMPOS_SERVIDOR_AGENTE,
}

TIPOS_AGENTE_SERVIDOR = frozenset(_CAMPOS_AGENTE_SERVIDOR)
TIPOS_SERVIDOR_AGENTE = frozenset(_CAMPOS_SERVIDOR_AGENTE)


def _validar_mensaje(mensaje: Any) -> dict:
    """Valida que ``mensaje`` sea un dict con un ``tipo`` conocido y todos
    sus campos requeridos. Devuelve el mismo dict si es válido."""
    if not isinstance(mensaje, dict):
        raise ErrorProtocolo(
            f"el mensaje debe ser un objeto JSON, no {type(mensaje).__name__}"
        )

    tipo = mensaje.get("tipo")
    if tipo is None:
        raise ErrorProtocolo("falta el campo 'tipo'")
    if tipo not in CAMPOS_REQUERIDOS:
        raise ErrorProtocolo(f"tipo de mensaje desconocido: {tipo!r}")

    faltantes = CAMPOS_REQUERIDOS[tipo] - mensaje.keys()
    if faltantes:
        raise ErrorProtocolo(
            f"faltan campos {sorted(faltantes)} para el tipo '{tipo}'"
        )

    return mensaje


def codificar(mensaje: dict) -> bytes:
    """Convierte un dict de mensaje en una línea JSON+``\\n`` en UTF-8,
    lista para escribir en el socket.

    Lanza ``ErrorProtocolo`` si el mensaje no es válido o si, ya
    codificado, supera ``TAMANO_MAXIMO_MENSAJE``.
    """
    _validar_mensaje(mensaje)

    try:
        linea = json.dumps(mensaje, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise ErrorProtocolo(f"no se pudo codificar el mensaje: {exc}") from exc

    datos = linea.encode("utf-8")
    if len(datos) > TAMANO_MAXIMO_MENSAJE:
        raise ErrorProtocolo(
            f"mensaje de {len(datos)} bytes supera el máximo de "
            f"{TAMANO_MAXIMO_MENSAJE} bytes"
        )
    return datos


def decodificar_linea(datos: bytes | str) -> dict:
    """Convierte una línea recibida por el socket en un dict de mensaje ya
    validado.

    Lanza ``ErrorProtocolo`` si la línea supera ``TAMANO_MAXIMO_MENSAJE``,
    no es JSON válido, no es un objeto, tiene un tipo desconocido o le
    faltan campos requeridos.
    """
    if isinstance(datos, bytes):
        if len(datos) > TAMANO_MAXIMO_MENSAJE:
            raise ErrorProtocolo(
                f"mensaje de {len(datos)} bytes supera el máximo de "
                f"{TAMANO_MAXIMO_MENSAJE} bytes"
            )
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ErrorProtocolo(f"la línea no es UTF-8 válido: {exc}") from exc
    else:
        texto = datos
        if len(texto.encode("utf-8")) > TAMANO_MAXIMO_MENSAJE:
            raise ErrorProtocolo(
                f"mensaje supera el máximo de {TAMANO_MAXIMO_MENSAJE} bytes"
            )

    texto = texto.strip()
    if not texto:
        raise ErrorProtocolo("línea vacía")

    try:
        mensaje = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErrorProtocolo(f"JSON inválido: {exc}") from exc

    return _validar_mensaje(mensaje)
