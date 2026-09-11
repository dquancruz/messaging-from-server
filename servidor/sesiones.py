"""Lógica de sesiones con tiempo (cibercafé).

Mantiene el estado de cada sesión y calcula qué acciones disparar en cada
tick del temporizador. El reloj es inyectable para pruebas con tiempo
simulado.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SesionEquipo:
    """Tiempo restante de un equipo en el cibercafé."""

    termina_en: float
    minutos_asignados: int
    avisos_enviados: set[int] = field(default_factory=set)


@dataclass
class AccionSesion:
    """Algo que el servidor debe mandar a un agente tras revisar sesiones."""

    equipo: str
    mensaje: dict


def formatear_aviso_minutos(minutos: int) -> tuple[str, str]:
    """Devuelve (texto, nivel) para un aviso automático."""
    if minutos == 1:
        return "Te queda 1 minuto", "critico"
    return f"Te quedan {minutos} minutos", "aviso"


class GestorSesiones:
    """Estado de sesiones por equipo y revisión periódica."""

    def __init__(
        self,
        avisos_minutos: list[int] | None = None,
        texto_fin_sesion: str = "Tu tiempo terminó, pasa a caja.",
        reloj: Callable[[], float] | None = None,
    ) -> None:
        self.avisos_minutos = sorted(set(avisos_minutos or [5, 1]), reverse=True)
        self.texto_fin_sesion = texto_fin_sesion
        self._reloj = reloj or time.monotonic
        self._sesiones: dict[str, SesionEquipo] = {}
        self._bloqueados: dict[str, bool] = {}
        self._texto_bloqueo: dict[str, str] = {}

    def reloj(self) -> float:
        return self._reloj()

    def esta_bloqueado(self, equipo: str) -> bool:
        return self._bloqueados.get(equipo, False)

    def texto_bloqueo(self, equipo: str) -> str:
        return self._texto_bloqueo.get(equipo, self.texto_fin_sesion)

    def tiempo_restante(self, equipo: str) -> int | None:
        sesion = self._sesiones.get(equipo)
        if sesion is None:
            return None
        restante = int(sesion.termina_en - self._reloj())
        if restante <= 0:
            return 0
        return restante

    def iniciar(self, equipo: str, minutos: int) -> None:
        ahora = self._reloj()
        self._sesiones[equipo] = SesionEquipo(
            termina_en=ahora + minutos * 60,
            minutos_asignados=minutos,
            avisos_enviados=set(),
        )
        self._bloqueados[equipo] = False
        self._texto_bloqueo.pop(equipo, None)

    def extender(self, equipo: str, minutos: int) -> None:
        ahora = self._reloj()
        sesion = self._sesiones.get(equipo)
        if sesion is None:
            self.iniciar(equipo, minutos)
            return
        base = max(sesion.termina_en, ahora)
        sesion.termina_en = base + minutos * 60
        sesion.minutos_asignados += minutos
        sesion.avisos_enviados.clear()
        self._bloqueados[equipo] = False
        self._texto_bloqueo.pop(equipo, None)

    def terminar(self, equipo: str) -> None:
        if equipo in self._sesiones:
            self._sesiones[equipo].termina_en = self._reloj()
        else:
            self._sesiones[equipo] = SesionEquipo(
                termina_en=self._reloj(),
                minutos_asignados=0,
            )

    def desbloquear(self, equipo: str) -> None:
        self._bloqueados[equipo] = False
        self._texto_bloqueo.pop(equipo, None)

    def quitar_sesion(self, equipo: str) -> None:
        self._sesiones.pop(equipo, None)

    def revisar(self, equipos_conocidos: set[str]) -> list[AccionSesion]:
        """Revisa todas las sesiones activas y devuelve mensajes a enviar."""
        acciones: list[AccionSesion] = []
        ahora = self._reloj()

        for equipo in list(self._sesiones.keys()):
            if equipo not in equipos_conocidos:
                continue

            sesion = self._sesiones[equipo]
            restante = int(sesion.termina_en - ahora)

            if restante > 0:
                acciones.extend(self._avisos_pendientes(equipo, sesion, restante))
                acciones.append(
                    AccionSesion(equipo, {"tipo": "sesion", "restante": restante})
                )
                continue

            if not self._bloqueados.get(equipo, False):
                texto = self.texto_fin_sesion
                self._bloqueados[equipo] = True
                self._texto_bloqueo[equipo] = texto
                acciones.append(
                    AccionSesion(equipo, {"tipo": "bloquear", "texto": texto})
                )

            acciones.append(AccionSesion(equipo, {"tipo": "sesion", "restante": None}))
            self._sesiones.pop(equipo, None)

        return acciones

    def _avisos_pendientes(
        self, equipo: str, sesion: SesionEquipo, restante_segundos: int
    ) -> list[AccionSesion]:
        acciones: list[AccionSesion] = []
        restante_minutos = restante_segundos / 60

        for umbral in self.avisos_minutos:
            if umbral in sesion.avisos_enviados:
                continue
            if restante_minutos <= umbral:
                texto, nivel = formatear_aviso_minutos(umbral)
                sesion.avisos_enviados.add(umbral)
                acciones.append(
                    AccionSesion(
                        equipo,
                        {
                            "tipo": "mensaje",
                            "id": f"aviso-{equipo}-{umbral}",
                            "titulo": "Cibercafé",
                            "texto": texto,
                            "nivel": nivel,
                            "pedir_visto": True,
                        },
                    )
                )
        return acciones
