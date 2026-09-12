"""Agente en modo consola para equipos sin escritorio gráfico.

Entrega avisos con ``wall`` a todas las terminales activas. Se usa en Debian
sin entorno gráfico, instalado como servicio systemd por el instalador Linux.
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import subprocess
import sys
import time
from pathlib import Path

from agente.agente import Agente
from agente.plataforma import ruta_config_por_defecto, ruta_logs

RUTA_CONFIG_LOCAL = Path(__file__).parent / "config.json"


class ErrorConfiguracion(Exception):
    """La configuración no se pudo leer o le falta un campo requerido."""


def cargar_config(ruta: Path) -> dict:
    try:
        with ruta.open("r", encoding="utf-8-sig") as f:
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
            logging.FileHandler(directorio / "agente-consola.log", encoding="utf-8"),
        ],
    )


def _anunciar(texto: str) -> None:
    mensaje = texto.strip()
    if not mensaje:
        return
    try:
        subprocess.run(
            ["wall", mensaje],
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except OSError as exc:
        logging.getLogger("agente.consola").warning("no se pudo usar wall: %s", exc)


def _formatear_mensaje(mensaje: dict) -> str:
    titulo = mensaje.get("titulo", "Cibercafé")
    cuerpo = mensaje.get("texto", "")
    nivel = mensaje.get("nivel", "info")
    return f"[{nivel.upper()}] {titulo}\n{cuerpo}"


def procesar_eventos(
    agente: Agente,
    detener: bool = False,
    tiempo_espera: float = 0.5,
) -> bool:
    """Procesa la cola de eventos de red. Devuelve False si debe terminar."""
    if detener:
        return False

    while True:
        try:
            evento = agente.cola_ui.get(timeout=tiempo_espera)
        except queue.Empty:
            return True

        tipo = evento.get("tipo")
        if tipo == "cerrar":
            return False
        if tipo == "mostrar_mensaje":
            mensaje = evento["mensaje"]
            _anunciar(_formatear_mensaje(mensaje))
            if mensaje.get("pedir_visto") and mensaje.get("id"):
                agente.cola_red.put({"tipo": "visto", "id": mensaje["id"]})
        elif tipo == "bloquear":
            texto = evento.get("texto") or "Tu tiempo terminó."
            _anunciar(f"BLOQUEO DE SESIÓN\n{texto}")
            if evento.get("desbloqueo_clave"):
                clave = input("Contraseña de desbloqueo: ")
                agente.cola_red.put({"tipo": "desbloquear_clave", "clave": clave})
        elif tipo == "desbloquear":
            _anunciar("Sesión desbloqueada. Puedes continuar usando el equipo.")
        elif tipo == "desbloquear_rechazado":
            _anunciar(f"No se pudo desbloquear: {evento.get('motivo', 'contraseña incorrecta')}")
        elif tipo == "sesion":
            restante = evento.get("restante")
            if restante is None:
                logging.getLogger("agente.consola").info("sesión finalizada")
            else:
                logging.getLogger("agente.consola").info(
                    "tiempo restante de sesión: %s s", restante
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agente de Ciber Mensajería (modo consola, sin ventanas)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="ruta al JSON de configuración",
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
    logger = logging.getLogger("agente.consola")
    logger.info("iniciando agente en modo consola (config=%s)", ruta_config)

    agente = Agente(config)
    agente.iniciar_red()

    try:
        while procesar_eventos(agente):
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("agente detenido por el usuario")
    finally:
        agente.detener()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
