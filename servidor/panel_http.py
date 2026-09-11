"""Panel web del servidor: API JSON y archivos estáticos.

Corre en un hilo con ``ThreadingHTTPServer``. Para hablar con el bucle de
asyncio del servidor de agentes usa ``asyncio.run_coroutine_threadsafe``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from comun import protocolo
from servidor.ad import ConsultorAD
from servidor.respaldo import EnviadorRespaldo
from servidor.servidor import Servidor

registrador = logging.getLogger("servidor.panel")

RUTA_PANEL = Path(__file__).parent / "panel"
USUARIO_PANEL = "admin"


class PanelHTTP:
    """Sirve el panel web y la API REST en un hilo aparte."""

    def __init__(
        self,
        servidor: Servidor,
        loop: asyncio.AbstractEventLoop,
        host: str = "127.0.0.1",
        puerto: int = protocolo.PUERTO_PANEL_POR_DEFECTO,
        password: str | None = None,
        consultor_ad: ConsultorAD | None = None,
        enviador_respaldo: EnviadorRespaldo | None = None,
    ) -> None:
        self.servidor = servidor
        self.loop = loop
        self.host = host
        self.puerto = puerto
        self.password = password
        self.consultor_ad = consultor_ad
        self.enviador_respaldo = enviador_respaldo
        self._httpd: ThreadingHTTPServer | None = None
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        handler = _crear_handler(self)
        self._httpd = ThreadingHTTPServer((self.host, self.puerto), handler)
        self._hilo = threading.Thread(
            target=self._httpd.serve_forever,
            name="panel-http",
            daemon=True,
        )
        self._hilo.start()
        registrador.info("panel web en http://%s:%s", self.host, self.puerto)

    def detener(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._hilo is not None:
            self._hilo.join(timeout=5)
            self._hilo = None
        registrador.info("panel web detenido")

    def requiere_autenticacion(self) -> bool:
        return self.host == "0.0.0.0" and bool(self.password)


def _crear_handler(panel: PanelHTTP) -> type[BaseHTTPRequestHandler]:
    class ManejadorPanel(BaseHTTPRequestHandler):
        server_version = "CiberMensajeriaPanel/0.1"

        def log_message(self, formato: str, *args: Any) -> None:
            registrador.debug("%s - %s", self.address_string(), formato % args)

        def do_GET(self) -> None:
            if not self._autenticado():
                return
            ruta = urlparse(self.path).path
            if ruta == "/api/equipos":
                equipos_ad = (
                    panel.consultor_ad.listar_equipos()
                    if panel.consultor_ad is not None
                    else None
                )
                self._responder_json(panel.servidor.estado.obtener_equipos_api(equipos_ad))
            elif ruta == "/api/historial":
                self._responder_json(panel.servidor.estado.historial(ultimos=100))
            elif ruta == "/api/historial.csv":
                self._responder_csv(panel.servidor.estado.historial_csv())
            elif ruta == "/" or ruta.startswith("/panel/"):
                self._servir_estatico(ruta)
            else:
                self._enviar_error(HTTPStatus.NOT_FOUND, "ruta no encontrada")

        def do_POST(self) -> None:
            if not self._autenticado():
                return
            ruta = urlparse(self.path).path
            if ruta == "/api/mensaje":
                self._api_mensaje()
            elif ruta == "/api/sesion/iniciar":
                self._api_sesion_iniciar()
            elif ruta == "/api/sesion/extender":
                self._api_sesion_extender()
            elif ruta == "/api/sesion/terminar":
                self._api_sesion_terminar()
            elif ruta == "/api/desbloquear":
                self._api_desbloquear()
            else:
                self._enviar_error(HTTPStatus.NOT_FOUND, "ruta no encontrada")

        def _autenticado(self) -> bool:
            if not panel.requiere_autenticacion():
                return True
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Basic "):
                self._pedir_autenticacion()
                return False
            try:
                decodificado = base64.b64decode(auth[6:], validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                self._pedir_autenticacion()
                return False
            if ":" not in decodificado:
                self._pedir_autenticacion()
                return False
            usuario, clave = decodificado.split(":", 1)
            if usuario != USUARIO_PANEL or clave != panel.password:
                self._pedir_autenticacion()
                return False
            return True

        def _pedir_autenticacion(self) -> None:
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="Ciber Mensajería"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Se requiere autenticación.\n".encode("utf-8"))

        def _leer_cuerpo_json(self) -> dict[str, Any] | None:
            longitud = int(self.headers.get("Content-Length", "0"))
            if longitud <= 0:
                self._enviar_error(HTTPStatus.BAD_REQUEST, "cuerpo vacío")
                return None
            try:
                datos = self.rfile.read(longitud)
                cuerpo = json.loads(datos.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._enviar_error(HTTPStatus.BAD_REQUEST, "JSON inválido")
                return None
            if not isinstance(cuerpo, dict):
                self._enviar_error(HTTPStatus.BAD_REQUEST, "se esperaba un objeto JSON")
                return None
            return cuerpo

        def _api_mensaje(self) -> None:
            cuerpo = self._leer_cuerpo_json()
            if cuerpo is None:
                return

            destinos = cuerpo.get("destinos")
            texto = cuerpo.get("texto", "")
            nivel = cuerpo.get("nivel", "info")
            usar_respaldo = bool(cuerpo.get("usar_respaldo", False))

            if destinos is None:
                self._enviar_error(HTTPStatus.BAD_REQUEST, "falta el campo 'destinos'")
                return
            if not isinstance(texto, str) or not texto.strip():
                self._enviar_error(HTTPStatus.BAD_REQUEST, "falta el campo 'texto'")
                return
            if nivel not in protocolo.NIVELES_VALIDOS:
                self._enviar_error(
                    HTTPStatus.BAD_REQUEST,
                    f"nivel inválido (use: {', '.join(sorted(protocolo.NIVELES_VALIDOS))})",
                )
                return
            if not (
                destinos == "todos"
                or (isinstance(destinos, list) and all(isinstance(d, str) for d in destinos))
            ):
                self._enviar_error(
                    HTTPStatus.BAD_REQUEST,
                    "'destinos' debe ser 'todos' o una lista de nombres",
                )
                return

            futuro = asyncio.run_coroutine_threadsafe(
                panel.servidor.enviar_mensaje(
                    destinos=destinos,
                    texto=texto.strip(),
                    nivel=nivel,
                    usar_respaldo=usar_respaldo,
                    enviador_respaldo=panel.enviador_respaldo,
                    equipos_ad=(
                        panel.consultor_ad.listar_equipos()
                        if panel.consultor_ad is not None
                        else None
                    ),
                ),
                panel.loop,
            )
            try:
                resultado = futuro.result(timeout=10)
            except Exception as exc:  # noqa: BLE001 - se devuelve al cliente como 500
                registrador.exception("error al enviar mensaje desde el panel")
                self._enviar_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            self._responder_json(resultado)

        def _api_sesion_iniciar(self) -> None:
            self._api_sesion("iniciar_sesion", ("equipo", "minutos"))

        def _api_sesion_extender(self) -> None:
            self._api_sesion("extender_sesion", ("equipo", "minutos"))

        def _api_sesion_terminar(self) -> None:
            self._api_sesion("terminar_sesion", ("equipo",))

        def _api_desbloquear(self) -> None:
            self._api_sesion("desbloquear_equipo", ("equipo",))

        def _api_sesion(self, metodo: str, campos: tuple[str, ...]) -> None:
            cuerpo = self._leer_cuerpo_json()
            if cuerpo is None:
                return

            valores: dict[str, Any] = {}
            for campo in campos:
                valor = cuerpo.get(campo)
                if valor is None or (isinstance(valor, str) and not valor.strip()):
                    self._enviar_error(HTTPStatus.BAD_REQUEST, f"falta el campo '{campo}'")
                    return
                valores[campo] = valor

            if "minutos" in valores:
                minutos = valores["minutos"]
                if not isinstance(minutos, int) or isinstance(minutos, bool) or minutos <= 0:
                    self._enviar_error(
                        HTTPStatus.BAD_REQUEST,
                        "'minutos' debe ser un entero positivo",
                    )
                    return

            futuro = asyncio.run_coroutine_threadsafe(
                getattr(panel.servidor, metodo)(**valores),
                panel.loop,
            )
            try:
                resultado = futuro.result(timeout=10)
            except ValueError as exc:
                self._enviar_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                registrador.exception("error en API de sesión")
                self._enviar_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            self._responder_json(resultado)

        def _responder_json(self, datos: Any, codigo: HTTPStatus = HTTPStatus.OK) -> None:
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _responder_csv(self, contenido: str) -> None:
            cuerpo = contenido.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="historial-ciber-mensajeria.csv"',
            )
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _enviar_error(self, codigo: HTTPStatus, mensaje: str) -> None:
            self._responder_json({"error": mensaje}, codigo)

        def _servir_estatico(self, ruta: str) -> None:
            if ruta == "/":
                archivo = RUTA_PANEL / "index.html"
            else:
                relativa = ruta.removeprefix("/panel/").lstrip("/")
                archivo = (RUTA_PANEL / relativa).resolve()
                if not str(archivo).startswith(str(RUTA_PANEL.resolve())):
                    self._enviar_error(HTTPStatus.FORBIDDEN, "ruta no permitida")
                    return

            if not archivo.is_file():
                self._enviar_error(HTTPStatus.NOT_FOUND, "archivo no encontrado")
                return

            contenido = archivo.read_bytes()
            tipo = mimetypes.guess_type(str(archivo))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{tipo}; charset=utf-8" if tipo.startswith("text/") else tipo)
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)

    return ManejadorPanel
