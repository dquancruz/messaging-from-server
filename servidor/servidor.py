"""Núcleo del servidor: acepta conexiones de agentes por TCP y les habla el
protocolo definido en ``comun/protocolo.py``.

Las sesiones con tiempo (bloquear/desbloquear/contador) llegan en la
Fase 4; por ahora ``bienvenido`` siempre manda ``sesion: null`` y
``bloqueado: false``. Ver PLAN.md.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from comun import protocolo
from servidor.estado import EstadoServidor

registrador = logging.getLogger("servidor.servidor")

# Cuánto se espera el "hola" inicial antes de cerrar la conexión.
TIMEOUT_HOLA = 10

# Resultado de _leer_linea_con_timeout: la lectura salió bien (linea puede
# ser b'' si el otro lado cerró la conexión, o sea EOF), expiró el tiempo de
# espera, o la línea superaba el tamaño máximo permitido.
_LECTURA_OK = "ok"
_LECTURA_TIMEOUT = "timeout"
_LECTURA_DEMASIADO_GRANDE = "demasiado_grande"


class Servidor:
    """Escucha agentes en ``host:puerto`` y mantiene su registro en
    ``estado``."""

    def __init__(
        self,
        estado: EstadoServidor,
        token: str,
        host: str = "0.0.0.0",
        puerto: int = protocolo.PUERTO_AGENTES_POR_DEFECTO,
        timeout_hola: float = TIMEOUT_HOLA,
        timeout_desconexion: float = protocolo.TIMEOUT_DESCONEXION,
    ) -> None:
        self.estado = estado
        self.token = token
        self.host = host
        self.puerto = puerto
        # Configurables para que las pruebas no tengan que esperar minutos
        # reales; en producción se usan los valores del protocolo.
        self.timeout_hola = timeout_hola
        self.timeout_desconexion = timeout_desconexion
        self._servidor: asyncio.AbstractServer | None = None

    async def iniciar(self) -> asyncio.AbstractServer:
        self._servidor = await asyncio.start_server(
            self._manejar_conexion,
            host=self.host,
            port=self.puerto,
            limit=protocolo.TAMANO_MAXIMO_MENSAJE,
        )
        direcciones = ", ".join(str(s.getsockname()) for s in self._servidor.sockets or ())
        registrador.info("escuchando agentes en %s", direcciones)
        return self._servidor

    async def detener(self) -> None:
        if self._servidor is not None:
            self._servidor.close()
            await self._servidor.wait_closed()
        self.estado.cerrar()
        registrador.info("servidor detenido")

    async def enviar_mensaje(
        self,
        *,
        destinos: list[str] | str,
        texto: str,
        nivel: str = "info",
        titulo: str = "Cibercafé",
        pedir_visto: bool = True,
    ) -> dict[str, Any]:
        """Envía un mensaje emergente a uno o varios equipos.

        ``destinos`` puede ser una lista de nombres de equipo o la cadena
        ``"todos"`` para mandarlo a todos los conectados.
        """
        if nivel not in protocolo.NIVELES_VALIDOS:
            raise ValueError(f"nivel inválido: {nivel!r}")

        if destinos == "todos":
            nombres = sorted(
                nombre for nombre, eq in self.estado.equipos.items() if eq.conectado
            )
        else:
            nombres = [d.strip().lower() for d in destinos if d.strip()]

        if not nombres:
            return {"enviados": 0, "equipos": [], "id": None}

        id_mensaje = str(uuid.uuid4())
        mensaje = {
            "tipo": "mensaje",
            "id": id_mensaje,
            "titulo": titulo,
            "texto": texto,
            "nivel": nivel,
            "pedir_visto": pedir_visto,
        }

        equipos_alcanzados: set[str] = set()
        for nombre_equipo, escritor in self.estado.escritores_de(nombres):
            if await self._enviar(escritor, mensaje):
                equipos_alcanzados.add(nombre_equipo)

        for nombre in equipos_alcanzados:
            self.estado.registrar_mensaje_enviado(nombre, id_mensaje)

        registrador.info(
            "mensaje '%s' enviado a %s equipo(s): %s",
            id_mensaje,
            len(equipos_alcanzados),
            ", ".join(sorted(equipos_alcanzados)) or "(ninguno)",
        )
        return {
            "id": id_mensaje,
            "enviados": len(equipos_alcanzados),
            "equipos": sorted(equipos_alcanzados),
        }

    async def _enviar(self, escritor: asyncio.StreamWriter, mensaje: dict) -> bool:
        """Manda un mensaje; si la conexión ya se cayó, no explota."""
        try:
            escritor.write(protocolo.codificar(mensaje))
            await escritor.drain()
            return True
        except (ConnectionError, OSError) as exc:
            registrador.debug("no se pudo enviar '%s': %s", mensaje.get("tipo"), exc)
            return False

    async def _leer_linea_con_timeout(
        self, lector: asyncio.StreamReader, timeout: float
    ) -> tuple[str, bytes | None]:
        """Lee una línea con un timeout. Devuelve ``(_LECTURA_OK, línea)``
        -- la línea puede ser ``b''`` si el otro lado cerró la conexión
        (EOF) --, ``(_LECTURA_TIMEOUT, None)`` si expiró el timeout, o
        ``(_LECTURA_DEMASIADO_GRANDE, None)`` si la línea supera
        ``protocolo.TAMANO_MAXIMO_MENSAJE``.

        Nota: pese a lo que dice la documentación de asyncio, ``readline()``
        no levanta ``asyncio.LimitOverrunError`` cuando se supera el
        ``limit`` del stream -- la atrapa internamente y la vuelve a
        levantar como un ``ValueError`` sencillo. Por eso se atrapa
        ``ValueError`` acá, no ``LimitOverrunError``.
        """
        try:
            linea = await asyncio.wait_for(lector.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            return (_LECTURA_TIMEOUT, None)
        except ValueError:
            return (_LECTURA_DEMASIADO_GRANDE, None)
        return (_LECTURA_OK, linea)

    async def _recibir_hola(
        self, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter, ip: str
    ) -> dict | None:
        estado_lectura, linea = await self._leer_linea_con_timeout(lector, self.timeout_hola)
        if estado_lectura == _LECTURA_TIMEOUT:
            registrador.warning("%s no mandó 'hola' a tiempo", ip)
            return None
        if estado_lectura == _LECTURA_DEMASIADO_GRANDE:
            registrador.warning("%s mandó una línea demasiado grande antes de saludar", ip)
            return None

        if not linea:
            return None  # se desconectó antes de saludar

        try:
            mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_AGENTE_SERVIDOR)
        except protocolo.ErrorProtocolo as exc:
            registrador.warning("saludo inválido de %s: %s", ip, exc)
            return None

        if mensaje["tipo"] != "hola":
            await self._enviar(escritor, {"tipo": "rechazado", "motivo": "se esperaba 'hola'"})
            registrador.warning("%s mandó '%s' en vez de 'hola'", ip, mensaje["tipo"])
            return None

        if mensaje["token"] != self.token:
            await self._enviar(escritor, {"tipo": "rechazado", "motivo": "token incorrecto"})
            registrador.warning("token incorrecto de %s (equipo=%s)", ip, mensaje.get("equipo"))
            return None

        return mensaje

    async def _bucle_mensajes(
        self,
        lector: asyncio.StreamReader,
        escritor: asyncio.StreamWriter,
        nombre_equipo: str,
        id_conexion: int,
    ) -> None:
        while True:
            estado_lectura, linea = await self._leer_linea_con_timeout(
                lector, self.timeout_desconexion
            )
            if estado_lectura == _LECTURA_TIMEOUT:
                registrador.info(
                    "'%s' sin latido en %ss, se da por desconectado", nombre_equipo, self.timeout_desconexion
                )
                return
            if estado_lectura == _LECTURA_DEMASIADO_GRANDE:
                registrador.warning(
                    "'%s' mandó una línea demasiado grande, se cierra la conexión", nombre_equipo
                )
                return

            if not linea:
                registrador.info("'%s' cerró la conexión", nombre_equipo)
                return

            try:
                mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_AGENTE_SERVIDOR)
            except protocolo.ErrorProtocolo as exc:
                registrador.warning("mensaje inválido de '%s': %s", nombre_equipo, exc)
                continue

            tipo = mensaje["tipo"]
            if tipo == "ping":
                self.estado.registrar_latido(nombre_equipo, id_conexion)
                await self._enviar(escritor, {"tipo": "pong"})
            elif tipo == "visto":
                self.estado.registrar_latido(nombre_equipo, id_conexion)
                self.estado.registrar_visto(nombre_equipo, mensaje["id"])
                registrador.info("'%s' confirmó visto de %s", nombre_equipo, mensaje["id"])
            else:
                registrador.warning(
                    "'%s' mandó un tipo inesperado para un agente: '%s'", nombre_equipo, tipo
                )

    async def _manejar_conexion(
        self, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter
    ) -> None:
        peer = escritor.get_extra_info("peername")
        ip = peer[0] if peer else "desconocida"
        nombre_equipo: str | None = None
        id_conexion: int | None = None

        try:
            hola = await self._recibir_hola(lector, escritor, ip)
            if hola is None:
                return

            nombre_equipo = hola["equipo"].strip().lower()
            id_conexion = self.estado.registrar_conexion(
                nombre=nombre_equipo,
                so=hola["so"],
                version_so=hola["version_so"],
                usuario=hola["usuario"],
                version_agente=hola["version_agente"],
                ip=ip,
                escritor=escritor,
            )
            registrador.info(
                "equipo '%s' conectado (usuario=%s, so=%s, ip=%s)",
                nombre_equipo, hola["usuario"], hola["so"], ip,
            )

            enviado = await self._enviar(
                escritor, {"tipo": "bienvenido", "sesion": None, "bloqueado": False}
            )
            if not enviado:
                return

            await self._bucle_mensajes(lector, escritor, nombre_equipo, id_conexion)
        finally:
            if nombre_equipo is not None and id_conexion is not None:
                self.estado.quitar_conexion(nombre_equipo, id_conexion)
            escritor.close()
            try:
                await escritor.wait_closed()
            except Exception as exc:  # noqa: BLE001 - solo se quiere loguear y seguir
                registrador.debug(
                    "error al cerrar la conexión de %s: %s", nombre_equipo or ip, exc
                )
