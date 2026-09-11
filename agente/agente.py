"""Conexión al servidor y coordinación entre red e interfaz."""

from __future__ import annotations

import logging
import queue
import socket
import ssl
import threading
import time
from pathlib import Path
from typing import Any

from agente import VERSION_AGENTE
from agente.plataforma import mensaje_hola, resolver_servidor
from comun import protocolo
from comun.tls import crear_contexto_cliente

registrador = logging.getLogger("agente.agente")

TIMEOUT_LECTURA = 1.0


def siguiente_espera_reconexion(intentos: int) -> float:
    """Segundos a esperar antes del siguiente intento de conexión."""
    esquema = protocolo.ESPERAS_RECONEXION
    if intentos < len(esquema):
        return float(esquema[intentos])
    return float(esquema[-1])


class _BufferLineas:
    """Acumula bytes del socket hasta completar líneas JSON."""

    def __init__(self) -> None:
        self._resto = b""

    def agregar(self, datos: bytes) -> list[bytes]:
        self._resto += datos
        lineas: list[bytes] = []
        while True:
            pos = self._resto.find(b"\n")
            if pos < 0:
                break
            linea = self._resto[: pos + 1]
            self._resto = self._resto[pos + 1 :]
            if linea.strip():
                lineas.append(linea)
        return lineas


def manejar_mensaje_servidor(mensaje: dict, cola_ui: queue.Queue) -> None:
    """Traduce un mensaje del servidor a eventos de interfaz."""
    tipo = mensaje["tipo"]
    if tipo == "mensaje":
        cola_ui.put({"tipo": "mostrar_mensaje", "mensaje": mensaje})
    elif tipo == "bienvenido":
        registrador.info(
            "conectado al servidor (sesión=%s, bloqueado=%s)",
            mensaje.get("sesion"),
            mensaje.get("bloqueado"),
        )
        cola_ui.put({"tipo": "sesion", "restante": mensaje.get("sesion")})
    elif tipo == "sesion":
        cola_ui.put({"tipo": "sesion", "restante": mensaje.get("restante")})
    elif tipo == "bloquear":
        cola_ui.put({"tipo": "bloquear", "texto": mensaje.get("texto")})
    elif tipo == "desbloquear":
        cola_ui.put({"tipo": "desbloquear"})
    elif tipo == "rechazado":
        registrador.error("rechazado por el servidor: %s", mensaje.get("motivo"))
    elif tipo == "pong":
        registrador.debug("mensaje del servidor: %s", tipo)
    elif tipo == "chat_estado":
        cola_ui.put({"tipo": "chat_estado", "habilitado": mensaje.get("habilitado")})
    elif tipo == "chat_lista":
        cola_ui.put({"tipo": "chat_lista", "equipos": mensaje.get("equipos", [])})
    elif tipo == "chat_recibido":
        cola_ui.put({"tipo": "chat_recibido", "mensaje": mensaje})
    elif tipo == "chat_enviado":
        cola_ui.put(
            {
                "tipo": "chat_enviado",
                "id": mensaje.get("id"),
                "para": mensaje.get("para"),
                "cuando": mensaje.get("cuando"),
            }
        )
    elif tipo == "chat_rechazado":
        cola_ui.put({"tipo": "chat_rechazado", "motivo": mensaje.get("motivo")})
    elif tipo == "chat_historial_respuesta":
        cola_ui.put(
            {
                "tipo": "chat_historial_respuesta",
                "con": mensaje.get("con"),
                "mensajes": mensaje.get("mensajes", []),
            }
        )
    else:
        registrador.warning("tipo de mensaje desconocido del servidor: %s", tipo)


class ClienteRed(threading.Thread):
    """Hilo que mantiene la conexión TCP con el servidor."""

    def __init__(
        self,
        config: dict[str, Any],
        cola_ui: queue.Queue,
        cola_red: queue.Queue,
        detener: threading.Event,
        version_agente: str = VERSION_AGENTE,
    ) -> None:
        super().__init__(name="agente-red", daemon=True)
        self.config = config
        self.cola_ui = cola_ui
        self.cola_red = cola_red
        self.detener = detener
        self.version_agente = version_agente
        self._socket: socket.socket | None = None

    def run(self) -> None:
        intentos = 0
        while not self.detener.is_set():
            try:
                self._sesion()
                intentos = 0
            except _RechazadoPorServidor as exc:
                registrador.error("%s", exc)
                return
            except (OSError, protocolo.ErrorProtocolo) as exc:
                registrador.warning("conexión interrumpida: %s", exc)
            finally:
                self._cerrar_socket()

            if self.detener.is_set():
                break

            espera = siguiente_espera_reconexion(intentos)
            intentos += 1
            registrador.info("reintento de conexión en %.0f s", espera)
            if self.detener.wait(espera):
                break

    def _sesion(self) -> None:
        host = resolver_servidor(
            self.config["servidor"],
            self.config.get("servidor_respaldo", ""),
            int(self.config.get("puerto", protocolo.PUERTO_AGENTES_POR_DEFECTO)),
        )
        puerto = int(self.config.get("puerto", protocolo.PUERTO_AGENTES_POR_DEFECTO))
        registrador.info("conectando a %s:%s", host, puerto)

        sock = socket.create_connection((host, puerto), timeout=10)
        if self.config.get("tls_habilitado"):
            ca = self.config.get("tls_ca")
            contexto = crear_contexto_cliente(Path(ca) if ca else None)
            sock = contexto.wrap_socket(sock, server_hostname=host)
        sock.settimeout(TIMEOUT_LECTURA)
        self._socket = sock

        hola = mensaje_hola(self.config["token"], self.version_agente)
        sock.sendall(protocolo.codificar(hola, protocolo.TIPOS_AGENTE_SERVIDOR))

        buffer = _BufferLineas()
        bienvenida = self._leer_siguiente_mensaje(sock, buffer)
        if bienvenida is None:
            raise ConnectionError("el servidor cerró la conexión al saludar")
        if bienvenida["tipo"] == "rechazado":
            raise _RechazadoPorServidor(bienvenida.get("motivo", "motivo desconocido"))
        manejar_mensaje_servidor(bienvenida, self.cola_ui)

        ultimo_ping = time.monotonic()
        while not self.detener.is_set():
            self._enviar_pendientes_red(sock)

            try:
                datos = sock.recv(4096)
            except socket.timeout:
                datos = None
            except OSError as exc:
                raise ConnectionError(str(exc)) from exc

            if datos:
                for linea in buffer.agregar(datos):
                    if len(linea) > protocolo.TAMANO_MAXIMO_MENSAJE:
                        raise protocolo.ErrorProtocolo("línea demasiado grande del servidor")
                    mensaje = protocolo.decodificar_linea(
                        linea, protocolo.TIPOS_SERVIDOR_AGENTE
                    )
                    manejar_mensaje_servidor(mensaje, self.cola_ui)
            elif datos is not None:
                raise ConnectionError("el servidor cerró la conexión")

            ahora = time.monotonic()
            if ahora - ultimo_ping >= protocolo.INTERVALO_PING:
                sock.sendall(protocolo.codificar({"tipo": "ping"}))
                ultimo_ping = ahora

    def _enviar_pendientes_red(self, sock: socket.socket) -> None:
        while True:
            try:
                evento = self.cola_red.get_nowait()
            except queue.Empty:
                return
            tipo = evento.get("tipo")
            if tipo == "visto":
                sock.sendall(
                    protocolo.codificar(
                        {"tipo": "visto", "id": evento["id"]},
                        protocolo.TIPOS_AGENTE_SERVIDOR,
                    )
                )
            elif tipo == "chat_enviar":
                sock.sendall(
                    protocolo.codificar(
                        {
                            "tipo": "chat_enviar",
                            "destino": evento["destino"],
                            "texto": evento["texto"],
                        },
                        protocolo.TIPOS_AGENTE_SERVIDOR,
                    )
                )
            elif tipo == "chat_historial":
                mensaje = {"tipo": "chat_historial", "con": evento["con"]}
                if "ultimos" in evento:
                    mensaje["ultimos"] = evento["ultimos"]
                sock.sendall(
                    protocolo.codificar(mensaje, protocolo.TIPOS_AGENTE_SERVIDOR)
                )

    def _leer_siguiente_mensaje(
        self, sock: socket.socket, buffer: _BufferLineas
    ) -> dict | None:
        while True:
            for linea in buffer.agregar(b""):
                return protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
            datos = sock.recv(4096)
            if not datos:
                return None
            for linea in buffer.agregar(datos):
                return protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)

    def _cerrar_socket(self) -> None:
        if self._socket is None:
            return
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._socket.close()
        except OSError:
            pass
        self._socket = None


class _RechazadoPorServidor(Exception):
    pass


class Agente:
    """Coordina el hilo de red y la interfaz tkinter."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.cola_ui: queue.Queue = queue.Queue()
        self.cola_red: queue.Queue = queue.Queue()
        self.detener = threading.Event()
        self.cliente_red = ClienteRed(config, self.cola_ui, self.cola_red, self.detener)

    def iniciar_red(self) -> None:
        self.cliente_red.start()

    def detener(self) -> None:
        self.detener.set()
        self.cola_ui.put({"tipo": "cerrar"})
