"""Estado en memoria del servidor: equipos conectados e historial.

La Fase 1 solo cubre registro y conexiones; las sesiones con tiempo
(bloqueo, contador, avisos automáticos) llegan en la Fase 4 — ver
PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

registrador = logging.getLogger("servidor.estado")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Conexion:
    """Una conexión TCP activa. Un mismo equipo puede tener varias, una por
    usuario con sesión abierta."""

    escritor: asyncio.StreamWriter
    usuario: str
    ip: str
    conectado_desde: str = field(default_factory=_ahora)
    ultimo_latido: str = field(default_factory=_ahora)


@dataclass
class Equipo:
    """Todo lo que el servidor sabe de un equipo."""

    nombre: str
    so: str
    version_so: str
    version_agente: str
    conexiones: dict[int, Conexion] = field(default_factory=dict)

    @property
    def conectado(self) -> bool:
        return bool(self.conexiones)

    def a_dict(self) -> dict[str, Any]:
        usuarios = sorted(c.usuario for c in self.conexiones.values())
        return {
            "nombre": self.nombre,
            "so": self.so,
            "version_so": self.version_so,
            "version_agente": self.version_agente,
            "conectado": self.conectado,
            "usuarios": usuarios,
            "conexiones_activas": len(self.conexiones),
        }


class EstadoServidor:
    """Registro de equipos e historial en memoria.

    El historial también se escribe a un archivo ``.jsonl`` (un evento por
    línea) para no perderlo si el servidor se reinicia.
    """

    def __init__(
        self,
        archivo_historial: Path | str | None = None,
        limite_historial: int = 500,
    ) -> None:
        self.equipos: dict[str, Equipo] = {}
        self._historial: list[dict[str, Any]] = []
        self._limite_historial = limite_historial
        self._archivo_historial = Path(archivo_historial) if archivo_historial else None
        self._siguiente_id_conexion = 1

    # -- historial -----------------------------------------------------

    def registrar_evento(self, tipo: str, **detalle: Any) -> None:
        evento = {"tipo": tipo, "cuando": _ahora(), **detalle}
        self._historial.append(evento)
        if len(self._historial) > self._limite_historial:
            self._historial.pop(0)
        if self._archivo_historial is not None:
            try:
                self._archivo_historial.parent.mkdir(parents=True, exist_ok=True)
                with self._archivo_historial.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(evento, ensure_ascii=False) + "\n")
            except OSError as exc:
                registrador.warning("no se pudo escribir historial.jsonl: %s", exc)

    def historial(self, ultimos: int = 100) -> list[dict[str, Any]]:
        return self._historial[-ultimos:]

    # -- registro de equipos/conexiones ---------------------------------

    def registrar_conexion(
        self,
        *,
        nombre: str,
        so: str,
        version_so: str,
        usuario: str,
        version_agente: str,
        ip: str,
        escritor: asyncio.StreamWriter,
    ) -> int:
        """Registra una nueva conexión de agente. Devuelve un id de
        conexión que se usa después para quitarla con
        ``quitar_conexion``."""
        equipo = self.equipos.get(nombre)
        if equipo is None:
            equipo = Equipo(
                nombre=nombre, so=so, version_so=version_so, version_agente=version_agente
            )
            self.equipos[nombre] = equipo
        else:
            # ya existía (otra sesión abierta, o se reconectó): refrescamos
            # los datos que pueden haber cambiado
            equipo.so = so
            equipo.version_so = version_so
            equipo.version_agente = version_agente

        id_conexion = self._siguiente_id_conexion
        self._siguiente_id_conexion += 1
        equipo.conexiones[id_conexion] = Conexion(escritor=escritor, usuario=usuario, ip=ip)

        self.registrar_evento("conectado", equipo=nombre, usuario=usuario, ip=ip, so=so)
        return id_conexion

    def registrar_latido(self, nombre: str, id_conexion: int) -> None:
        equipo = self.equipos.get(nombre)
        if equipo is None:
            return
        conexion = equipo.conexiones.get(id_conexion)
        if conexion is not None:
            conexion.ultimo_latido = _ahora()

    def quitar_conexion(self, nombre: str, id_conexion: int) -> None:
        equipo = self.equipos.get(nombre)
        if equipo is None:
            return
        conexion = equipo.conexiones.pop(id_conexion, None)
        if conexion is None:
            return
        self.registrar_evento("desconectado", equipo=nombre, usuario=conexion.usuario)

    def obtener_equipos(self) -> list[dict[str, Any]]:
        return [e.a_dict() for e in sorted(self.equipos.values(), key=lambda e: e.nombre)]
