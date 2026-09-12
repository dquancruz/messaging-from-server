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
from urllib.parse import parse_qs, urlparse

from comun import protocolo
from servidor.ad import ConsultorAD
from servidor.respaldo import EnviadorRespaldo
from servidor.servidor import Servidor

registrador = logging.getLogger("servidor.panel")

RUTA_PANEL = Path(__file__).parent / "panel"
RUTA_MODERACION = RUTA_PANEL / "moderacion"
USUARIO_PANEL = "admin"
REALM_MODERACION = "Ciber Mensajeria - Moderacion"


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
        usuario_moderador: str = "moderador",
        password_moderador: str | None = None,
    ) -> None:
        self.servidor = servidor
        self.loop = loop
        self.host = host
        self.puerto = puerto
        self.password = password
        self.consultor_ad = consultor_ad
        self.enviador_respaldo = enviador_respaldo
        self.usuario_moderador = usuario_moderador
        self.password_moderador = password_moderador
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
            ruta = urlparse(self.path).path
            if ruta.startswith("/api/moderacion/") or ruta.startswith("/moderacion/"):
                if not self._autenticado_moderador():
                    return
                if ruta == "/api/moderacion/conversaciones":
                    self._api_moderacion_conversaciones()
                elif ruta == "/api/moderacion/mensajes":
                    self._api_moderacion_mensajes()
                elif ruta == "/moderacion/" or ruta.startswith("/moderacion/"):
                    self._servir_moderacion(ruta)
                else:
                    self._enviar_error(HTTPStatus.NOT_FOUND, "ruta no encontrada")
                return

            if not self._autenticado_caja():
                return
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
            elif ruta == "/api/chat/estado":
                self._api_chat_estado()
            elif ruta == "/" or ruta.startswith("/panel/"):
                self._servir_estatico(ruta)
            else:
                self._enviar_error(HTTPStatus.NOT_FOUND, "ruta no encontrada")

        def do_POST(self) -> None:
            ruta = urlparse(self.path).path
            if ruta.startswith("/api/moderacion/"):
                if not self._autenticado_moderador():
                    return
                self._enviar_error(HTTPStatus.METHOD_NOT_ALLOWED, "método no permitido")
                return

            if not self._autenticado_caja():
                return
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
            elif ruta == "/api/chat/habilitar":
                self._api_chat_habilitar()
            else:
                self._enviar_error(HTTPStatus.NOT_FOUND, "ruta no encontrada")

        def _decodificar_basic(self) -> tuple[str, str] | None:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Basic "):
                return None
            try:
                decodificado = base64.b64decode(auth[6:], validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return None
            if ":" not in decodificado:
                return None
            usuario, clave = decodificado.split(":", 1)
            return usuario, clave

        def _autenticado_caja(self) -> bool:
            if not panel.requiere_autenticacion():
                return True
            credenciales = self._decodificar_basic()
            if credenciales is None:
                self._pedir_autenticacion_caja()
                return False
            usuario, clave = credenciales
            if usuario != USUARIO_PANEL or clave != panel.password:
                self._pedir_autenticacion_caja()
                return False
            return True

        def _autenticado_moderador(self) -> bool:
            if not panel.password_moderador:
                self._enviar_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "moderación no configurada (falta password_moderador)",
                )
                return False
            credenciales = self._decodificar_basic()
            if credenciales is None:
                self._pedir_autenticacion_moderador()
                return False
            usuario, clave = credenciales
            if usuario != panel.usuario_moderador or clave != panel.password_moderador:
                self._pedir_autenticacion_moderador()
                return False
            return True

        def _pedir_autenticacion_caja(self) -> None:
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="Ciber Mensajería"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Se requiere autenticación.\n".encode("utf-8"))

        def _pedir_autenticacion_moderador(self) -> None:
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", f'Basic realm="{REALM_MODERACION}"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Se requiere autenticación de moderación.\n".encode("utf-8"))

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

        def _api_chat_estado(self) -> None:
            gestor = panel.servidor.gestor_chat
            if gestor is None:
                self._responder_json({"habilitado": False})
                return
            self._responder_json({"habilitado": gestor.habilitado})

        def _api_chat_habilitar(self) -> None:
            cuerpo = self._leer_cuerpo_json()
            if cuerpo is None:
                return
            habilitado = cuerpo.get("habilitado")
            if not isinstance(habilitado, bool):
                self._enviar_error(
                    HTTPStatus.BAD_REQUEST,
                    "falta el campo booleano 'habilitado'",
                )
                return
            futuro = asyncio.run_coroutine_threadsafe(
                panel.servidor.cambiar_chat_habilitado(habilitado),
                panel.loop,
            )
            try:
                resultado = futuro.result(timeout=10)
            except ValueError as exc:
                self._enviar_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                registrador.exception("error al cambiar estado del chat")
                self._enviar_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            self._responder_json(resultado)

        def _api_moderacion_conversaciones(self) -> None:
            gestor = panel.servidor.gestor_chat
            if gestor is None:
                self._responder_json([])
                return
            self._responder_json(gestor.listar_conversaciones())

        def _api_moderacion_mensajes(self) -> None:
            gestor = panel.servidor.gestor_chat
            if gestor is None:
                self._responder_json([])
                return
            consulta = parse_qs(urlparse(self.path).query)
            de = consulta.get("de", [""])[0].strip().lower()
            para = consulta.get("para", [""])[0].strip().lower()
            ultimos_raw = consulta.get("ultimos", ["50"])[0]
            if not de or not para:
                self._enviar_error(
                    HTTPStatus.BAD_REQUEST,
                    "se requieren los parámetros 'de' y 'para'",
                )
                return
            try:
                ultimos = int(ultimos_raw)
            except ValueError:
                ultimos = 50
            self._responder_json(gestor.mensajes_conversacion(de, para, ultimos))

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

            self._enviar_archivo(archivo)

        def _servir_moderacion(self, ruta: str) -> None:
            if ruta == "/moderacion/" or ruta == "/moderacion":
                archivo = RUTA_MODERACION / "index.html"
            elif ruta == "/moderacion/comun.js":
                archivo = RUTA_PANEL / "comun.js"
            else:
                relativa = ruta.removeprefix("/moderacion/").lstrip("/")
                archivo = (RUTA_MODERACION / relativa).resolve()
                if not str(archivo).startswith(str(RUTA_MODERACION.resolve())):
                    self._enviar_error(HTTPStatus.FORBIDDEN, "ruta no permitida")
                    return
            self._enviar_archivo(archivo)

        def _enviar_archivo(self, archivo: Path) -> None:
            if not archivo.is_file():
                self._enviar_error(HTTPStatus.NOT_FOUND, "archivo no encontrado")
                return

            contenido = archivo.read_bytes()
            tipo = mimetypes.guess_type(str(archivo))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                f"{tipo}; charset=utf-8" if tipo.startswith("text/") else tipo,
            )
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)

    return ManejadorPanel
