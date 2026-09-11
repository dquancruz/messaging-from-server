"""Detección de plataforma, rutas y bloqueo de instancia única."""

from __future__ import annotations

import getpass
import os
import platform
import socket
import sys
from pathlib import Path

from comun import protocolo


def detectar_so() -> str:
    """Devuelve ``windows``, ``linux`` o ``macos`` según el sistema."""
    sistema = sys.platform
    if sistema == "win32":
        return "windows"
    if sistema == "darwin":
        return "macos"
    return "linux"


def version_so() -> str:
    return platform.platform()


def nombre_equipo() -> str:
    return socket.gethostname().strip().lower()


def usuario_actual() -> str:
    return getpass.getuser()


def directorio_estado() -> Path:
    """Carpeta para logs, bloqueo de instancia y datos locales del agente."""
    so = detectar_so()
    if so == "windows":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "CiberMensajeria"
        return Path.home() / "AppData" / "Local" / "CiberMensajeria"
    if so == "macos":
        return Path.home() / "Library" / "Logs" / "CiberMensajeria"
    return Path.home() / ".local" / "state" / "ciber-agente"


def ruta_logs() -> Path:
    return directorio_estado() / "logs"


def ruta_config_por_defecto() -> Path:
    so = detectar_so()
    if so == "windows":
        base = os.environ.get("PROGRAMDATA")
        if base:
            return Path(base) / "CiberMensajeria" / "agente.json"
        return Path("C:/ProgramData/CiberMensajeria/agente.json")
    if so == "macos":
        return Path("/Library/Application Support/CiberMensajeria/agente.json")
    return Path("/etc/ciber-mensajeria/agente.json")


def ruta_bloqueo_instancia() -> Path:
    return directorio_estado() / "agente.lock"


def _proceso_activo(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        codigo_salida = ctypes.c_ulong()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo_salida)):
            kernel32.CloseHandle(handle)
            return codigo_salida.value == STILL_ACTIVE
        kernel32.CloseHandle(handle)
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def adquirir_bloqueo_instancia() -> bool:
    """Intenta asegurar que solo haya un agente por usuario.

    Devuelve ``True`` si esta instancia obtuvo el bloqueo; ``False`` si ya
    hay otra corriendo.
    """
    ruta = ruta_bloqueo_instancia()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    if ruta.exists():
        try:
            pid = int(ruta.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = 0
        if _proceso_activo(pid):
            return False
        try:
            ruta.unlink()
        except OSError:
            return False

    try:
        ruta.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return False
    return True


def liberar_bloqueo_instancia() -> None:
    ruta = ruta_bloqueo_instancia()
    if not ruta.exists():
        return
    try:
        pid = int(ruta.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid = -1
    if pid == os.getpid():
        try:
            ruta.unlink()
        except OSError:
            pass


def resolver_servidor(servidor: str, servidor_respaldo: str, puerto: int) -> str:
    """Devuelve el host al que conectar.

    Intenta resolver ``servidor``; si falla, usa ``servidor_respaldo``.
    """
    candidatos = [servidor.strip(), servidor_respaldo.strip()]
    vistos: set[str] = set()
    for host in candidatos:
        if not host or host in vistos:
            continue
        vistos.add(host)
        try:
            socket.getaddrinfo(host, puerto, type=socket.SOCK_STREAM)
            return host
        except OSError:
            continue
    return servidor_respaldo.strip() or servidor.strip()


def mensaje_hola(token: str, version_agente: str) -> dict:
    """Arma el mensaje ``hola`` con los datos de esta máquina."""
    so = detectar_so()
    if so not in protocolo.SISTEMAS_OPERATIVOS_VALIDOS:
        so = "linux"
    return {
        "tipo": "hola",
        "token": token,
        "equipo": nombre_equipo(),
        "so": so,
        "version_so": version_so(),
        "usuario": usuario_actual(),
        "version_agente": version_agente,
    }
