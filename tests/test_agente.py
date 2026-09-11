import asyncio
import queue
import socket
import threading
import time
import unittest
from unittest import mock

from agente.agente import (
    ClienteRed,
    manejar_mensaje_servidor,
    siguiente_espera_reconexion,
)
from agente.plataforma import nombre_equipo, resolver_servidor
from comun import protocolo
from servidor.admin import ServidorAdmin
from servidor.estado import EstadoServidor
from servidor.servidor import Servidor

HOLA_BASE = {
    "tipo": "hola",
    "token": "secreto",
    "equipo": "pc-agente",
    "so": "linux",
    "version_so": "22.04",
    "usuario": "dquan",
    "version_agente": "0.2.0",
}


class PruebasReconexion(unittest.TestCase):
    def test_espera_creciente_hasta_el_tope(self):
        self.assertEqual(siguiente_espera_reconexion(0), 1)
        self.assertEqual(siguiente_espera_reconexion(1), 2)
        self.assertEqual(siguiente_espera_reconexion(5), 30)
        self.assertEqual(siguiente_espera_reconexion(99), 30)

    def test_resolver_servidor_usa_respaldo_si_falla_dns(self):
        with mock.patch("socket.getaddrinfo", side_effect=OSError("no resuelve")):
            host = resolver_servidor("dc01.lab.lan", "192.168.1.10", 5050)
        self.assertEqual(host, "192.168.1.10")

    def test_resolver_servidor_prefiere_nombre_si_resuelve(self):
        with mock.patch("socket.getaddrinfo", return_value=[(None, None, None, None, None)]):
            host = resolver_servidor("dc01.lab.lan", "192.168.1.10", 5050)
        self.assertEqual(host, "dc01.lab.lan")


class PruebasManejoMensajes(unittest.TestCase):
    def test_mensaje_del_servidor_llega_a_la_cola_ui(self):
        cola_ui: queue.Queue = queue.Queue()
        mensaje = {
            "tipo": "mensaje",
            "id": "abc",
            "titulo": "Aviso",
            "texto": "Hola",
            "nivel": "info",
            "pedir_visto": True,
        }
        manejar_mensaje_servidor(mensaje, cola_ui)
        evento = cola_ui.get_nowait()
        self.assertEqual(evento["tipo"], "mostrar_mensaje")
        self.assertEqual(evento["mensaje"], mensaje)


class PruebasClienteRed(unittest.TestCase):
    def test_reconecta_tras_caida_del_servidor(self):
        cola_ui: queue.Queue = queue.Queue()
        cola_red: queue.Queue = queue.Queue()
        detener = threading.Event()

        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(1)
        host, puerto = servidor.getsockname()

        conexiones = 0

        def aceptar():
            nonlocal conexiones
            while not detener.is_set() and conexiones < 2:
                try:
                    servidor.settimeout(0.5)
                    conn, _ = servidor.accept()
                except OSError:
                    continue
                conexiones += 1
                if conexiones == 1:
                    self._atender_primera_conexion(conn)
                else:
                    self._atender_segunda_conexion(conn)

        hilo_servidor = threading.Thread(target=aceptar, daemon=True)
        hilo_servidor.start()

        cliente = ClienteRed(
            {
                "servidor": host,
                "servidor_respaldo": host,
                "puerto": puerto,
                "token": "secreto",
            },
            cola_ui,
            cola_red,
            detener,
        )
        cliente.start()

        tiempo_limite = time.monotonic() + 8
        while conexiones < 2 and time.monotonic() < tiempo_limite:
            time.sleep(0.1)

        detener.set()
        cliente.join(timeout=2)
        servidor.close()
        self.assertGreaterEqual(conexiones, 2)

    def _atender_primera_conexion(self, conn: socket.socket) -> None:
        buffer = b""
        while b"\n" not in buffer:
            buffer += conn.recv(4096)
        conn.sendall(
            protocolo.codificar({"tipo": "bienvenido", "sesion": None, "bloqueado": False})
        )
        time.sleep(0.2)
        conn.close()

    def _atender_segunda_conexion(self, conn: socket.socket) -> None:
        buffer = b""
        while b"\n" not in buffer:
            buffer += conn.recv(4096)
        conn.sendall(
            protocolo.codificar({"tipo": "bienvenido", "sesion": None, "bloqueado": False})
        )
        time.sleep(0.3)
        conn.close()


class PruebasIntegracionAgenteServidor(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.estado = EstadoServidor()
        self.servidor = Servidor(estado=self.estado, token="secreto", host="127.0.0.1", puerto=0)
        self.servidor_asyncio = await self.servidor.iniciar()
        self.admin = ServidorAdmin(estado=self.estado, host="127.0.0.1", puerto=0)
        self.admin_asyncio = await self.admin.iniciar()

        self.host_agentes, self.puerto_agentes = self.servidor_asyncio.sockets[0].getsockname()[:2]
        self.host_admin, self.puerto_admin = self.admin_asyncio.sockets[0].getsockname()[:2]

        self.cola_ui: queue.Queue = queue.Queue()
        self.cola_red: queue.Queue = queue.Queue()
        self.detener = threading.Event()
        self.cliente = ClienteRed(
            {
                "servidor": self.host_agentes,
                "servidor_respaldo": self.host_agentes,
                "puerto": self.puerto_agentes,
                "token": "secreto",
            },
            self.cola_ui,
            self.cola_red,
            self.detener,
        )
        self.cliente.start()

    async def asyncTearDown(self):
        self.detener.set()
        self.cliente.join(timeout=2)
        await self.admin.detener()
        await self.servidor.detener()

    async def test_mensaje_del_servidor_llega_al_agente(self):
        await asyncio.sleep(0.2)
        enviados = await self.estado.enviar_mensaje(
            destinos=nombre_equipo(),
            titulo="Prueba",
            texto="Hola desde el servidor",
            nivel="aviso",
            pedir_visto=True,
            id_mensaje="msg-1",
        )
        self.assertGreaterEqual(enviados, 0)

        evento = None
        for _ in range(30):
            try:
                evento = self.cola_ui.get(timeout=0.2)
                break
            except queue.Empty:
                await asyncio.sleep(0.1)
        self.assertIsNotNone(evento)
        assert evento is not None
        self.assertEqual(evento["tipo"], "mostrar_mensaje")
        self.assertEqual(evento["mensaje"]["texto"], "Hola desde el servidor")

    async def test_visto_llega_al_historial(self):
        equipo = nombre_equipo()
        for _ in range(30):
            if self.estado.equipos.get(equipo, None) and self.estado.equipos[equipo].conectado:
                break
            await asyncio.sleep(0.1)
        self.assertTrue(self.estado.equipos[equipo].conectado)

        self.cola_red.put({"tipo": "visto", "id": "msg-99"})
        for _ in range(30):
            eventos = [e for e in self.estado.historial() if e.get("tipo") == "visto"]
            ids = [e.get("id_mensaje") for e in eventos]
            if "msg-99" in ids:
                break
            await asyncio.sleep(0.1)
        self.assertIn("msg-99", ids)


if __name__ == "__main__":
    unittest.main()
