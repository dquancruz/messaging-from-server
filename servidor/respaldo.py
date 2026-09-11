"""Envío de avisos por métodos alternativos cuando no hay agente.

- Windows: ``msg.exe`` (mismo enfoque que ``legacy/panel-cibercafe.ps1``).
- Linux/macOS: SSH con ``wall`` en la sesión remota.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from typing import Any

registrador = logging.getLogger("servidor.respaldo")


class EnviadorRespaldo:
    """Manda mensajes a equipos que no tienen el agente conectado."""

    def __init__(
        self,
        *,
        habilitado: bool = False,
        dominio: str = "lab.lan",
        usuario_ssh: str = "root",
        timeout_segundos: int = 15,
    ) -> None:
        self.habilitado = habilitado
        self.dominio = dominio
        self.usuario_ssh = usuario_ssh
        self.timeout_segundos = timeout_segundos

    def enviar(self, equipo: str, texto: str, so: str = "desconocido") -> dict[str, Any]:
        nombre = equipo.strip().lower()
        if not self.habilitado:
            return {"equipo": nombre, "ok": False, "metodo": None, "error": "respaldo deshabilitado"}
        if so == "windows":
            return self._enviar_msg_windows(nombre, texto)
        if so in ("linux", "macos"):
            return self._enviar_ssh(nombre, texto)
        # Sin SO conocido: intentar msg en Windows del servidor y luego SSH
        if platform.system() == "Windows":
            resultado = self._enviar_msg_windows(nombre, texto)
            if resultado["ok"]:
                return resultado
        return self._enviar_ssh(nombre, texto)

    def _enviar_msg_windows(self, equipo: str, texto: str) -> dict[str, Any]:
        if shutil.which("msg.exe") is None:
            return {
                "equipo": equipo,
                "ok": False,
                "metodo": "msg.exe",
                "error": "msg.exe no está disponible en este servidor",
            }
        destino = f"{equipo}.{self.dominio}" if "." not in equipo else equipo
        comando = ["msg.exe", f"*/SERVER:{destino}", "*", texto]
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_segundos,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            registrador.warning("msg.exe a %s falló: %s", destino, exc)
            return {"equipo": equipo, "ok": False, "metodo": "msg.exe", "error": str(exc)}
        if resultado.returncode == 0:
            registrador.info("mensaje de respaldo enviado a %s con msg.exe", destino)
            return {"equipo": equipo, "ok": True, "metodo": "msg.exe", "error": None}
        detalle = (resultado.stderr or resultado.stdout or "error desconocido").strip()
        registrador.warning("msg.exe a %s devolvió %s: %s", destino, resultado.returncode, detalle)
        return {
            "equipo": equipo,
            "ok": False,
            "metodo": "msg.exe",
            "error": detalle,
        }

    def _enviar_ssh(self, equipo: str, texto: str) -> dict[str, Any]:
        if shutil.which("ssh") is None:
            return {
                "equipo": equipo,
                "ok": False,
                "metodo": "ssh",
                "error": "ssh no está disponible en este servidor",
            }
        host = f"{equipo}.{self.dominio}" if "." not in equipo else equipo
        mensaje_escapado = texto.replace("'", "'\"'\"'")
        comando_remoto = f"wall '{mensaje_escapado}'"
        comando = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.timeout_segundos}",
            f"{self.usuario_ssh}@{host}",
            comando_remoto,
        ]
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_segundos + 5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            registrador.warning("SSH a %s falló: %s", host, exc)
            return {"equipo": equipo, "ok": False, "metodo": "ssh", "error": str(exc)}
        if resultado.returncode == 0:
            registrador.info("mensaje de respaldo enviado a %s por SSH", host)
            return {"equipo": equipo, "ok": True, "metodo": "ssh", "error": None}
        detalle = (resultado.stderr or resultado.stdout or "error desconocido").strip()
        registrador.warning("SSH a %s devolvió %s: %s", host, resultado.returncode, detalle)
        return {"equipo": equipo, "ok": False, "metodo": "ssh", "error": detalle}
