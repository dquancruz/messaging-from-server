"""Consulta equipos del dominio Active Directory.

En DC01 (Windows Server con el módulo ActiveDirectory) ejecuta
``Get-ADComputer``. En otros entornos (desarrollo, pruebas) puede leer
una lista fija desde un archivo JSON.
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

registrador = logging.getLogger("servidor.ad")

_SO_POR_SISTEMA_OPERATIVO = {
    "windows": "windows",
    "linux": "linux",
    "mac": "macos",
    "darwin": "macos",
}


def _normalizar_so(sistema: str | None) -> str:
    if not sistema:
        return "desconocido"
    texto = sistema.lower()
    for clave, valor in _SO_POR_SISTEMA_OPERATIVO.items():
        if clave in texto:
            return valor
    return "desconocido"


def _parsear_json_powershell(salida: str) -> list[dict[str, Any]]:
    try:
        datos = json.loads(salida)
    except json.JSONDecodeError as exc:
        raise ValueError(f"salida de PowerShell no es JSON válido: {exc}") from exc
    if not isinstance(datos, list):
        raise ValueError("se esperaba una lista de equipos de Active Directory")
    resultado: list[dict[str, Any]] = []
    for item in datos:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get("Name", "")).strip().lower()
        if not nombre:
            continue
        resultado.append(
            {
                "nombre": nombre,
                "so": _normalizar_so(item.get("OperatingSystem")),
                "fuente": "ad",
            }
        )
    return resultado


class ConsultorAD:
    """Obtiene la lista de equipos del dominio y la cachea unos minutos."""

    def __init__(
        self,
        *,
        habilitado: bool = False,
        dominio: str = "lab.lan",
        filtro: str = "*",
        archivo_respaldo: Path | str | None = None,
        intervalo_segundos: int = 300,
    ) -> None:
        self.habilitado = habilitado
        self.dominio = dominio
        self.filtro = filtro
        self.archivo_respaldo = Path(archivo_respaldo) if archivo_respaldo else None
        self.intervalo_segundos = max(30, intervalo_segundos)
        self._cache: list[dict[str, Any]] = []
        self._ultima_consulta: float = 0.0

    def listar_equipos(self, forzar: bool = False) -> list[dict[str, Any]]:
        if not self.habilitado:
            return []
        ahora = time.monotonic()
        if not forzar and self._cache and (ahora - self._ultima_consulta) < self.intervalo_segundos:
            return list(self._cache)
        try:
            self._cache = self._consultar()
        except Exception as exc:  # noqa: BLE001 - se deja la caché anterior si existe
            registrador.warning("no se pudo consultar Active Directory: %s", exc)
            if not self._cache:
                self._cache = []
        self._ultima_consulta = ahora
        return list(self._cache)

    def _consultar(self) -> list[dict[str, Any]]:
        if platform.system() == "Windows":
            return self._consultar_powershell()
        if self.archivo_respaldo is not None and self.archivo_respaldo.is_file():
            return self._consultar_archivo(self.archivo_respaldo)
        registrador.info(
            "Active Directory habilitado pero no hay módulo AD ni archivo de respaldo; "
            "se devuelve lista vacía"
        )
        return []

    def _consultar_powershell(self) -> list[dict[str, Any]]:
        script = (
            f"Get-ADComputer -Filter '{self.filtro}' -Properties OperatingSystem "
            "| Select-Object Name, OperatingSystem "
            "| ConvertTo-Json -Compress"
        )
        comando = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        if resultado.returncode != 0:
            detalle = (resultado.stderr or resultado.stdout or "").strip()
            raise RuntimeError(f"Get-ADComputer falló: {detalle}")
        salida = resultado.stdout.strip()
        if not salida:
            return []
        # ConvertTo-Json devuelve un objeto si hay un solo equipo
        if salida.startswith("{"):
            salida = f"[{salida}]"
        return _parsear_json_powershell(salida)

    def _consultar_archivo(self, ruta: Path) -> list[dict[str, Any]]:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, list):
            raise ValueError(f"'{ruta}' debe contener una lista JSON de equipos")
        resultado: list[dict[str, Any]] = []
        for item in datos:
            if isinstance(item, str):
                nombre = item.strip().lower()
                if nombre:
                    resultado.append({"nombre": nombre, "so": "desconocido", "fuente": "ad"})
                continue
            if not isinstance(item, dict):
                continue
            nombre = str(item.get("nombre", "")).strip().lower()
            if not nombre:
                continue
            resultado.append(
                {
                    "nombre": nombre,
                    "so": item.get("so", "desconocido"),
                    "fuente": "ad",
                }
            )
        return resultado
