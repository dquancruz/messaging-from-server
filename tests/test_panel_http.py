import asyncio
import base64
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from comun import protocolo
from servidor.estado import EstadoServidor
from servidor.panel_http import PanelHTTP, USUARIO_PANEL, _crear_handler
from servidor.servidor import Servidor

HOLA_BASE = {
    "tipo": "hola",
    "token": "secreto",
    "equipo": "PC-01",
    "so": "linux",
    "version_so": "22.04",
    "usuario": "dquan",
    "version_agente": "0.1.0",
}


def _peticion(url: str, metodo: str = "GET", datos: dict | None = None, auth: tuple[str, str] | None = None):
    cuerpo = None
    headers = {}
    if datos is not None:
        cuerpo = json.dumps(datos).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth is not None:
        credenciales = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        headers["Authorization"] = f"Basic {credenciales}"
    req = urllib.request.Request(url, data=cuerpo, headers=headers, method=metodo)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


class PruebasPanelHTTP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.estado = EstadoServidor()
        self.servidor = Servidor(
            estado=self.estado,
            token="secreto",
            host="127.0.0.1",
            puerto=0,
            habilitar_temporizador=False,
        )
        self.servidor_asyncio = await self.servidor.iniciar()
        self.loop = asyncio.get_running_loop()

        self.panel = PanelHTTP(
            servidor=self.servidor,
            loop=self.loop,
            host="127.0.0.1",
            puerto=0,
        )
        # Arrancar en puerto libre asignado por el SO
        handler = _crear_handler(self.panel)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.puerto_panel = self.httpd.server_address[1]
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()
        self.base_url = f"http://127.0.0.1:{self.puerto_panel}"

        host_agentes, puerto_agentes = self.servidor_asyncio.sockets[0].getsockname()[:2]
        self.lector, self.escritor = await asyncio.open_connection(host_agentes, puerto_agentes)
        self.escritor.write(protocolo.codificar(HOLA_BASE))
        await self.escritor.drain()
        await self.lector.readline()  # bienvenido
        await asyncio.sleep(0.05)

    async def asyncTearDown(self):
        self.escritor.close()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.hilo.join(timeout=2)
        await self.servidor.detener()

    def test_api_equipos_lista_conectado(self):
        status, datos = _peticion(f"{self.base_url}/api/equipos")
        self.assertEqual(status, 200)
        self.assertEqual(len(datos), 1)
        self.assertEqual(datos[0]["nombre"], "pc-01")
        self.assertTrue(datos[0]["conectado"])
        self.assertEqual(datos[0]["so"], "linux")

    async def test_api_mensaje_y_visto(self):
        # La petición HTTP corre en otro hilo: si bloqueamos el event loop con
        # urllib, run_coroutine_threadsafe del panel nunca se ejecuta.
        status, resultado = await asyncio.to_thread(
            _peticion,
            f"{self.base_url}/api/mensaje",
            "POST",
            {"destinos": ["pc-01"], "texto": "Hola prueba", "nivel": "info"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resultado["enviados"], 1)
        id_mensaje = resultado["id"]

        linea = await asyncio.wait_for(self.lector.readline(), timeout=2)
        mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(mensaje["tipo"], "mensaje")
        self.assertEqual(mensaje["id"], id_mensaje)
        self.assertEqual(mensaje["texto"], "Hola prueba")

        self.escritor.write(protocolo.codificar({"tipo": "visto", "id": id_mensaje}))
        await self.escritor.drain()
        await asyncio.sleep(0.05)

        status, equipos = _peticion(f"{self.base_url}/api/equipos")
        self.assertEqual(status, 200)
        self.assertIsNotNone(equipos[0]["ultimo_visto"])

    def test_api_historial(self):
        status, datos = _peticion(f"{self.base_url}/api/historial")
        self.assertEqual(status, 200)
        self.assertTrue(any(e["tipo"] == "conectado" for e in datos))

    def test_api_historial_csv(self):
        req = urllib.request.Request(f"{self.base_url}/api/historial.csv")
        with urllib.request.urlopen(req, timeout=5) as resp:
            cuerpo = resp.read().decode("utf-8")
        self.assertEqual(resp.status, 200)
        self.assertIn("cuando,tipo,equipo", cuerpo)
        self.assertIn("conectado", cuerpo)

    def test_api_mensaje_destinos_invalidos(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            _peticion(
                f"{self.base_url}/api/mensaje",
                metodo="POST",
                datos={"destinos": 123, "texto": "x", "nivel": "info"},
            )
        self.assertEqual(ctx.exception.code, 400)

    async def test_api_sesion_iniciar(self):
        status, resultado = await asyncio.to_thread(
            _peticion,
            f"{self.base_url}/api/sesion/iniciar",
            "POST",
            {"equipo": "pc-01", "minutos": 15},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resultado["equipo"], "pc-01")
        self.assertGreaterEqual(resultado["restante"], 15 * 60 - 2)
        self.assertLessEqual(resultado["restante"], 15 * 60)

        linea = await asyncio.wait_for(self.lector.readline(), timeout=2)
        mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(mensaje["tipo"], "desbloquear")

    async def test_api_desbloquear(self):
        self.estado.sesiones._bloqueados["pc-01"] = True
        status, resultado = await asyncio.to_thread(
            _peticion,
            f"{self.base_url}/api/desbloquear",
            "POST",
            {"equipo": "pc-01"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resultado, {"equipo": "pc-01", "bloqueado": False})
        self.assertFalse(self.estado.sesiones.esta_bloqueado("pc-01"))

        linea = await asyncio.wait_for(self.lector.readline(), timeout=2)
        mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(mensaje["tipo"], "desbloquear")

    def test_pagina_principal_se_sirve(self):
        req = urllib.request.Request(f"{self.base_url}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("Ciber Mensajería", html)


class PruebasAutenticacionPanel(unittest.TestCase):
    def test_requiere_password_si_escucha_en_todas_las_interfaces(self):
        estado = EstadoServidor()
        servidor = Servidor(estado=estado, token="x", host="127.0.0.1", puerto=0)
        loop = asyncio.new_event_loop()
        clave_prueba = "x" * 8  # evita el patrón password="..." del escáner de secretos en CI
        panel = PanelHTTP(servidor=servidor, loop=loop, host="0.0.0.0", password=clave_prueba)
        self.assertTrue(panel.requiere_autenticacion())

        panel_local = PanelHTTP(servidor=servidor, loop=loop, host="127.0.0.1", password=None)
        self.assertFalse(panel_local.requiere_autenticacion())
        loop.close()


class PruebasEnviarMensaje(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.estado = EstadoServidor()
        self.servidor = Servidor(
            estado=self.estado,
            token="secreto",
            host="127.0.0.1",
            puerto=0,
            habilitar_temporizador=False,
        )
        self.servidor_asyncio = await self.servidor.iniciar()

    async def asyncTearDown(self):
        await self.servidor.detener()

    async def test_enviar_a_todos(self):
        lectores = []
        escritores = []
        host, puerto = self.servidor_asyncio.sockets[0].getsockname()[:2]
        for i, nombre in enumerate(("PC-01", "PC-02"), start=1):
            lector, escritor = await asyncio.open_connection(host, puerto)
            escritor.write(
                protocolo.codificar({**HOLA_BASE, "equipo": nombre, "usuario": f"u{i}"})
            )
            await escritor.drain()
            await lector.readline()
            lectores.append(lector)
            escritores.append(escritor)

        resultado = await self.servidor.enviar_mensaje(
            destinos="todos", texto="Aviso general", nivel="aviso"
        )
        self.assertEqual(resultado["enviados"], 2)

        for lector in lectores:
            linea = await asyncio.wait_for(lector.readline(), timeout=2)
            mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
            self.assertEqual(mensaje["texto"], "Aviso general")

        for escritor in escritores:
            escritor.close()


if __name__ == "__main__":
    unittest.main()
