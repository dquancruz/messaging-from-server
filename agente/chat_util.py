"""Lógica pura del historial de chat (sin dependencia de tkinter)."""

from __future__ import annotations

MARCA_ENVIANDO = "enviando…"


def confirmar_mensaje_en_historial(
    historial: list[dict],
    nombre_local: str,
    para: str,
    id_mensaje: str,
    cuando: str,
) -> bool:
    """Actualiza el último mensaje optimista con la confirmación del servidor."""
    clave = para.strip().lower()
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
