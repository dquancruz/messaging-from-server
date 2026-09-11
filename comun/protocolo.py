"""Protocolo de mensajería entre agente y servidor.

Cada mensaje es un objeto JSON en UTF-8, en una sola línea terminada en
``\\n``. Este módulo sabe codificar y decodificar esas líneas, y validar
que cada mensaje tenga los campos que le corresponden según su ``tipo``.

Ver ``docs/protocolo.md`` para la tabla completa de tipos de mensaje.
"""

from __future__ import annotations

import json
from typing import Any, Callable

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


# ---------------------------------------------------------------------------
# Validadores por campo (además de "está presente", que ya cubre
# CAMPOS_REQUERIDOS)
# ---------------------------------------------------------------------------


def _es_str(valor: Any) -> bool:
    return isinstance(valor, str)


def _es_str_no_vacio(valor: Any) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _es_bool(valor: Any) -> bool:
    return isinstance(valor, bool)


def _es_so_valido(valor: Any) -> bool:
    return isinstance(valor, str) and valor in SISTEMAS_OPERATIVOS_VALIDOS


def _es_nivel_valido(valor: Any) -> bool:
    return isinstance(valor, str) and valor in NIVELES_VALIDOS


def _es_segundos_o_none(valor: Any) -> bool:
    # bool es subclase de int en Python; True/False no cuentan como segundos
    return valor is None or (isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0)


_VALIDADORES_CAMPOS: dict[str, dict[str, Callable[[Any], bool]]] = {
    "hola": {
        "token": _es_str_no_vacio,
        "equipo": _es_str_no_vacio,
        "so": _es_so_valido,
        "version_so": _es_str,
        "usuario": _es_str_no_vacio,
        "version_agente": _es_str,
    },
    "visto": {"id": _es_str_no_vacio},
    "ping": {},
    "bienvenido": {"sesion": _es_segundos_o_none, "bloqueado": _es_bool},
    "rechazado": {"motivo": _es_str},
    "mensaje": {
        "id": _es_str_no_vacio,
        "titulo": _es_str,
        "texto": _es_str,
        "nivel": _es_nivel_valido,
        "pedir_visto": _es_bool,
    },
    "sesion": {"restante": _es_segundos_o_none},
    "bloquear": {"texto": _es_str},
    "desbloquear": {},
    "pong": {},
}


def _validar_mensaje(
    mensaje: Any, tipos_permitidos: frozenset[str] | None = None
) -> dict:
    """Valida que ``mensaje`` sea un dict con un ``tipo`` conocido, todos
    sus campos requeridos, y cada campo del tipo y forma que le
    corresponde. Devuelve el mismo dict si es válido.

    Si se pasa ``tipos_permitidos`` (por ejemplo ``TIPOS_AGENTE_SERVIDOR``),
    también exige que ``tipo`` pertenezca a ese conjunto — así el servidor no
    acepta de un agente un tipo que solo el servidor debería mandar, y
    viceversa.
    """
    if not isinstance(mensaje, dict):
        raise ErrorProtocolo(
            f"el mensaje debe ser un objeto JSON, no {type(mensaje).__name__}"
        )

    tipo = mensaje.get("tipo")
    if tipo is None:
        raise ErrorProtocolo("falta el campo 'tipo'")
    if tipo not in CAMPOS_REQUERIDOS:
        raise ErrorProtocolo(f"tipo de mensaje desconocido: {tipo!r}")
    if tipos_permitidos is not None and tipo not in tipos_permitidos:
        raise ErrorProtocolo(f"tipo de mensaje no permitido aquí: {tipo!r}")

    faltantes = CAMPOS_REQUERIDOS[tipo] - mensaje.keys()
    if faltantes:
        raise ErrorProtocolo(
            f"faltan campos {sorted(faltantes)} para el tipo '{tipo}'"
        )

    for campo, es_valido in _VALIDADORES_CAMPOS[tipo].items():
        valor = mensaje[campo]
        if not es_valido(valor):
            raise ErrorProtocolo(
                f"campo '{campo}' inválido para el tipo '{tipo}': {valor!r}"
            )

    return mensaje


def codificar(mensaje: dict, tipos_permitidos: frozenset[str] | None = None) -> bytes:
    """Convierte un dict de mensaje en una línea JSON+``\\n`` en UTF-8,
    lista para escribir en el socket.

    Lanza ``ErrorProtocolo`` si el mensaje no es válido o si, ya
    codificado, supera ``TAMANO_MAXIMO_MENSAJE``.
    """
    _validar_mensaje(mensaje, tipos_permitidos)

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


def decodificar_linea(
    datos: bytes | str, tipos_permitidos: frozenset[str] | None = None
) -> dict:
    """Convierte una línea recibida por el socket en un dict de mensaje ya
    validado.

    Lanza ``ErrorProtocolo`` si la línea supera ``TAMANO_MAXIMO_MENSAJE``,
    no es JSON válido, no es un objeto, tiene un tipo desconocido o no
    permitido (ver ``tipos_permitidos`` en ``_validar_mensaje``), le faltan
    campos requeridos, o alguno de sus campos no tiene la forma esperada.
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

    return _validar_mensaje(mensaje, tipos_permitidos)
