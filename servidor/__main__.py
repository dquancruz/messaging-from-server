"""Punto de entrada del servidor.

Uso:
    python -m servidor --config servidor/config.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import ssl
import sys
from pathlib import Path

from comun import protocolo
from comun.tls import crear_contexto_servidor
from servidor.ad import ConsultorAD
from servidor.chat import GestorChat
from servidor.estado import EstadoServidor
from servidor.panel_http import PanelHTTP
from servidor.respaldo import EnviadorRespaldo
from servidor.servidor import Servidor

RUTA_CONFIG_POR_DEFECTO = Path(__file__).parent / "config.json"


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


def _crear_ssl_context(config: dict) -> ssl.SSLContext | None:
    if not config.get("tls_habilitado"):
        return None
    certificado = config.get("tls_certificado")
    clave = config.get("tls_clave")
    if not certificado or not clave:
        raise ErrorConfiguracion(
            "si 'tls_habilitado' es true deben definirse 'tls_certificado' y 'tls_clave'"
        )
    return crear_contexto_servidor(certificado, clave)


async def ejecutar(config: dict, directorio_datos: Path) -> None:
    estado = EstadoServidor(
        archivo_historial=directorio_datos / "historial.jsonl",
        avisos_minutos=config.get("avisos_minutos"),
        texto_fin_sesion=config.get("texto_fin_sesion", "Tu tiempo terminó, pasa a caja."),
    )
    gestor_chat = GestorChat(
        archivo_chat=directorio_datos / "chat.jsonl",
        limite_por_conversacion=int(config.get("chat_limite_por_conversacion", 500)),
        habilitado=bool(config.get("chat_habilitado", True)),
    )
    ssl_context = _crear_ssl_context(config)
    servidor = Servidor(
        estado=estado,
        token=config["token"],
        host=config.get("host_agentes", "0.0.0.0"),
        puerto=config.get("puerto_agentes", protocolo.PUERTO_AGENTES_POR_DEFECTO),
        ssl_context=ssl_context,
        gestor_chat=gestor_chat,
        password_desbloqueo=config.get("password_desbloqueo"),
    )
    servidor_asyncio = await servidor.iniciar()

    consultor_ad = ConsultorAD(
        habilitado=bool(config.get("ad_habilitado")),
        dominio=config.get("ad_dominio", "lab.lan"),
        filtro=config.get("ad_filtro", "*"),
        archivo_respaldo=config.get("ad_archivo_respaldo"),
        intervalo_segundos=int(config.get("ad_intervalo_segundos", 300)),
    )
    enviador_respaldo = EnviadorRespaldo(
        habilitado=bool(config.get("respaldo_habilitado")),
        dominio=config.get("ad_dominio", "lab.lan"),
        usuario_ssh=config.get("respaldo_ssh_usuario", "root"),
        timeout_segundos=int(config.get("respaldo_timeout_segundos", 15)),
    )

    host_panel = config.get("host_panel", "127.0.0.1")
    password_panel = config.get("password_panel")
    if host_panel == "0.0.0.0" and not password_panel:
        raise ErrorConfiguracion(
            "si 'host_panel' es '0.0.0.0' debe definirse 'password_panel' en la configuración"
        )

    loop = asyncio.get_running_loop()
    panel = PanelHTTP(
        servidor=servidor,
        loop=loop,
        host=host_panel,
        puerto=config.get("puerto_panel", protocolo.PUERTO_PANEL_POR_DEFECTO),
        password=password_panel,
        consultor_ad=consultor_ad,
        enviador_respaldo=enviador_respaldo,
        usuario_moderador=config.get("usuario_moderador", "moderador"),
        password_moderador=config.get("password_moderador"),
    )
    panel.iniciar()

    try:
        await servidor_asyncio.serve_forever()
    finally:
        panel.detener()
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
    logger.info("iniciando servidor (config=%s, token=%s)", args.config, config["token"])
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
