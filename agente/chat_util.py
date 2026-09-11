"""Lógica pura del historial de chat (sin dependencia de tkinter)."""

from __future__ import annotations

MARCA_ENVIANDO = "enviando…"


def confirmar_mensaje_en_historial(
    historial: list[dict],
    nombre_local: str,
    id_mensaje: str,
    cuando: str,
) -> bool:
    """Actualiza el último mensaje optimista con la confirmación del servidor."""
    if not historial:
        return False
    for mensaje in reversed(historial):
        if mensaje.get("de") == nombre_local and mensaje.get("cuando") == MARCA_ENVIANDO:
            mensaje["id"] = id_mensaje
            mensaje["cuando"] = cuando
            return True
    return False


def revertir_pendiente_en_historial(
    historial: list[dict],
    nombre_local: str,
) -> bool:
    """Quita el último mensaje optimista del historial."""
    for indice in range(len(historial) - 1, -1, -1):
        mensaje = historial[indice]
        if mensaje.get("de") == nombre_local and mensaje.get("cuando") == MARCA_ENVIANDO:
            historial.pop(indice)
            return True
    return False


def indice_interlocutor(equipos: list[dict], interlocutor: str | None) -> int | None:
    """Devuelve el índice del interlocutor en la lista de equipos, o None."""
    if not interlocutor:
        return None
    clave = interlocutor.strip().lower()
    for indice, equipo in enumerate(equipos):
        if str(equipo.get("nombre", "")).strip().lower() == clave:
            return indice
    return None


def fusionar_historial_con_pendientes(
    historial_servidor: list[dict],
    historial_local: list[dict],
    nombre_local: str,
) -> list[dict]:
    """Conserva mensajes optimistas locales al recibir historial del servidor."""
    pendientes = [
        mensaje
        for mensaje in historial_local
        if mensaje.get("de") == nombre_local and mensaje.get("cuando") == MARCA_ENVIANDO
    ]
    if not pendientes:
        return list(historial_servidor)
    return list(historial_servidor) + pendientes
