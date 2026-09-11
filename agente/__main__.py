"""Punto de entrada del agente.

Uso:
    python -m agente --config agente/config.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tkinter as tk
from pathlib import Path

from agente.agente import Agente
from agente.plataforma import (
    adquirir_bloqueo_instancia,
    liberar_bloqueo_instancia,
    ruta_config_por_defecto,
    ruta_logs,
)
from agente.ventanas import GestorVentanas

RUTA_CONFIG_LOCAL = Path(__file__).parent / "config.json"


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

    for campo in ("servidor", "token"):
        if campo not in config:
            raise ErrorConfiguracion(f"a '{ruta}' le falta el campo requerido '{campo}'")

    return config


def configurar_logs() -> None:
    directorio = ruta_logs()
    directorio.mkdir(parents=True, exist_ok=True)
    formato = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=formato,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(directorio / "agente.log", encoding="utf-8"),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agente de Ciber Mensajería")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="ruta al JSON de configuración (por defecto: la del SO o agente/config.json)",
    )
    args = parser.parse_args(argv)

    ruta_config = args.config
    if ruta_config is None:
        ruta_sistema = ruta_config_por_defecto()
        ruta_config = ruta_sistema if ruta_sistema.exists() else RUTA_CONFIG_LOCAL

    try:
        config = cargar_config(ruta_config)
    except ErrorConfiguracion as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 1

    configurar_logs()
    logger = logging.getLogger("agente")
    logger.info("iniciando agente (config=%s)", ruta_config)

    if not adquirir_bloqueo_instancia():
        logger.error("ya hay otra instancia del agente corriendo para este usuario")
        return 1

    agente = Agente(config)
    root = tk.Tk()
    root.withdraw()

    def al_cerrar() -> None:
        agente.detener()
        liberar_bloqueo_instancia()

    gestor = GestorVentanas(
        root, agente.cola_ui, agente.cola_red, config=config, al_cerrar=al_cerrar
    )
    agente.iniciar_red()

    try:
        gestor.iniciar()
    except KeyboardInterrupt:
        logger.info("agente detenido por el usuario")
    finally:
        agente.detener()
        liberar_bloqueo_instancia()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
