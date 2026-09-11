"""Levanta N agentes falsos para probar el servidor sin las máquinas reales.

Uso:
    python herramientas/simular_agentes.py --n 4
    python herramientas/simular_agentes.py --n 4 --host 192.168.1.10 --puerto 5050 --token XXX
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Se ejecuta como script suelto (no como "python -m"), así que el
# directorio del repo no queda en sys.path por su cuenta.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comun import protocolo  # noqa: E402  (después del sys.path.insert)

registrador = logging.getLogger("simulador")

SISTEMAS = ("windows", "linux", "macos")


async def _conectar_una_vez(nombre: str, so: str, host: str, puerto: int, token: str) -> None:
    etiqueta = f"{nombre} ({so})"
    lector, escritor = await asyncio.open_connection(host, puerto)
    try:
        escritor.write(
            protocolo.codificar(
                {
                    "tipo": "hola",
                    "token": token,
                    "equipo": nombre,
                    "so": so,
                    "version_so": "1.0-simulado",
                    "usuario": f"usuario-{nombre.lower()}",
                    "version_agente": "0.1.0-simulador",
                }
            )
        )
        await escritor.drain()

        linea = await lector.readline()
        if not linea:
            raise ConnectionError("el servidor cerró la conexión al saludar")

        bienvenida = protocolo.decodificar_linea(linea)
        if bienvenida["tipo"] == "rechazado":
            registrador.error("%s: rechazado por el servidor (%s)", etiqueta, bienvenida["motivo"])
            return
        registrador.info("%s: conectado", etiqueta)

        tarea_latidos = asyncio.create_task(_mandar_latidos(escritor))
        tarea_lectura = asyncio.create_task(_leer_mensajes(etiqueta, lector, escritor))
        listas, pendientes = await asyncio.wait(
            {tarea_latidos, tarea_lectura}, return_when=asyncio.FIRST_COMPLETED
        )
        for tarea in pendientes:
            tarea.cancel()
        for tarea in listas:
            excepcion = tarea.exception()
            if excepcion is not None:
                raise excepcion
    finally:
        escritor.close()


async def _agente_falso(indice: int, host: str, puerto: int, token: str) -> None:
    nombre = f"PC-{indice:02d}"
    so = SISTEMAS[(indice - 1) % len(SISTEMAS)]
    etiqueta = f"{nombre} ({so})"

    while True:
        try:
            await _conectar_una_vez(nombre, so, host, puerto, token)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError, protocolo.ErrorProtocolo) as exc:
            registrador.warning("%s: se cortó la conexión (%s), reintento en 2s", etiqueta, exc)
        await asyncio.sleep(2)


async def _mandar_latidos(escritor: asyncio.StreamWriter) -> None:
    while True:
        await asyncio.sleep(protocolo.INTERVALO_PING)
        escritor.write(protocolo.codificar({"tipo": "ping"}))
        await escritor.drain()


async def _leer_mensajes(
    etiqueta: str, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter
) -> None:
    while True:
        linea = await lector.readline()
        if not linea:
            raise ConnectionError("el servidor cerró la conexión")

        try:
            mensaje = protocolo.decodificar_linea(linea)
        except protocolo.ErrorProtocolo as exc:
            registrador.warning("%s: mensaje inválido del servidor: %s", etiqueta, exc)
            continue

        tipo = mensaje["tipo"]
        if tipo == "mensaje":
            registrador.info("%s: recibió '%s': %s", etiqueta, mensaje["titulo"], mensaje["texto"])
            if mensaje.get("pedir_visto"):
                await asyncio.sleep(2)
                escritor.write(protocolo.codificar({"tipo": "visto", "id": mensaje["id"]}))
                await escritor.drain()
        elif tipo == "pong":
            pass
        else:
            registrador.info("%s: '%s' (todavía no implementado en el simulador)", etiqueta, tipo)


async def _correr(n: int, host: str, puerto: int, token: str) -> None:
    tareas = [asyncio.create_task(_agente_falso(i, host, puerto, token)) for i in range(1, n + 1)]
    await asyncio.gather(*tareas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agentes falsos para probar el servidor")
    parser.add_argument("--n", type=int, default=4, help="cuántos agentes falsos levantar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=protocolo.PUERTO_AGENTES_POR_DEFECTO)
    parser.add_argument("--token", default="cambia-este-token")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        asyncio.run(_correr(args.n, args.host, args.puerto, args.token))
    except KeyboardInterrupt:
        registrador.info("simulador detenido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
