"""Puerto local de administración para herramientas de desarrollo.

Escucha solo en ``127.0.0.1`` y acepta comandos JSON de una línea. El panel
web de la Fase 3 lo reemplazará; por ahora sirve para mandar mensajes de
prueba con ``herramientas/enviar_mensaje.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from servidor.estado import EstadoServidor

registrador = logging.getLogger("servidor.admin")

PUERTO_ADMIN_POR_DEFECTO = 5051


class ServidorAdmin:
    def __init__(
        self,
        estado: EstadoServidor,
        host: str = "127.0.0.1",
        puerto: int = PUERTO_ADMIN_POR_DEFECTO,
    ) -> None:
        self.estado = estado
        self.host = host
        self.puerto = puerto
        self._servidor: asyncio.AbstractServer | None = None

    async def iniciar(self) -> asyncio.AbstractServer:
        self._servidor = await asyncio.start_server(
            self._manejar_conexion, host=self.host, port=self.puerto
        )
        registrador.info("admin escuchando en %s:%s", self.host, self.puerto)
        return self._servidor

    async def detener(self) -> None:
        if self._servidor is not None:
            self._servidor.close()
            await self._servidor.wait_closed()

    async def _manejar_conexion(
        self, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter
    ) -> None:
        try:
            linea = await lector.readline()
            if not linea:
                return
            try:
                comando = json.loads(linea.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                await self._responder(escritor, {"ok": False, "error": f"JSON inválido: {exc}"})
                return

            respuesta = await self._ejecutar(comando)
            await self._responder(escritor, respuesta)
        finally:
            escritor.close()
            try:
                await escritor.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _ejecutar(self, comando: dict[str, Any]) -> dict[str, Any]:
        accion = comando.get("accion")
        if accion != "mensaje":
            return {"ok": False, "error": f"acción desconocida: {accion!r}"}

        destinos = comando.get("destinos")
        texto = comando.get("texto")
        if not destinos or not isinstance(texto, str):
            return {"ok": False, "error": "faltan 'destinos' o 'texto'"}

        try:
            enviados = await self.estado.enviar_mensaje(
                destinos=destinos,
                titulo=comando.get("titulo", "Cibercafé"),
                texto=texto,
                nivel=comando.get("nivel", "info"),
                pedir_visto=bool(comando.get("pedir_visto", True)),
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "enviados": enviados}

    async def _responder(self, escritor: asyncio.StreamWriter, datos: dict[str, Any]) -> None:
        escritor.write((json.dumps(datos, ensure_ascii=False) + "\n").encode("utf-8"))
        await escritor.drain()
