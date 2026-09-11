"""Punto de entrada del servidor.

Uso:
    python -m servidor --config servidor/config.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from comun import protocolo
from servidor.estado import EstadoServidor
from servidor.servidor import Servidor

RUTA_CONFIG_POR_DEFECTO = Path(__file__).parent / "config.json"


class ErrorConfiguracion(Exception):
    """La configuración no se pudo leer o le falta un campo requerido."""


def cargar_config(ruta: Path) -> dict:
    try:
        with ruta.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except OSError as exc:
        raise ErrorConfiguracion(f"no se pudo leer '{ruta}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorConfiguracion(f"'{ruta}' no es JSON válido: {exc}") from exc

    if "token" not in config:
        raise ErrorConfiguracion(f"a '{ruta}' le falta el campo requerido 'token'")

    return config


def configurar_logs(directorio: Path) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    formato = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=formato,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(directorio / "servidor.log", encoding="utf-8"),
        ],
    )


async def ejecutar(config: dict, directorio_datos: Path) -> None:
    estado = EstadoServidor(archivo_historial=directorio_datos / "historial.jsonl")
    servidor = Servidor(
        estado=estado,
        token=config["token"],
        host=config.get("host_agentes", "0.0.0.0"),
        puerto=config.get("puerto_agentes", protocolo.PUERTO_AGENTES_POR_DEFECTO),
    )
    servidor_asyncio = await servidor.iniciar()
    try:
        await servidor_asyncio.serve_forever()
    finally:
        await servidor.detener()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor de Ciber Mensajería")
    parser.add_argument("--config", type=Path, default=RUTA_CONFIG_POR_DEFECTO)
    parser.add_argument(
        "--datos", type=Path, default=Path("datos"), help="carpeta para logs e historial"
    )
    args = parser.parse_args(argv)

    try:
        config = cargar_config(args.config)
    except ErrorConfiguracion as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 1

    configurar_logs(args.datos)
    logger = logging.getLogger("servidor")
    logger.info("iniciando servidor (config=%s)", args.config)
    try:
        asyncio.run(ejecutar(config, args.datos))
    except KeyboardInterrupt:
        logger.info("servidor detenido por el usuario")
    except OSError as exc:
        # p. ej. el puerto ya está en uso
        logger.error("no se pudo iniciar el servidor: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
