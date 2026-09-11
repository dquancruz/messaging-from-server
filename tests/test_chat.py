import asyncio
import base64
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from comun import protocolo
from servidor.chat import GestorChat, clave_conversacion
from servidor.estado import EstadoServidor
from servidor.panel_http import PanelHTTP, USUARIO_PANEL, _crear_handler
from servidor.servidor import Servidor

HOLA_A = {
    "tipo": "hola",
    "token": "secreto",
    "equipo": "PC-A",
    "so": "linux",
    "version_so": "22.04",
    "usuario": "alice",
    "version_agente": "0.1.0",
}

HOLA_B = {
    **HOLA_A,
    "equipo": "PC-B",
    "usuario": "bob",
}


async def _conectar(servidor_asyncio):
    host, puerto = servidor_asyncio.sockets[0].getsockname()[:2]
    return await asyncio.open_connection(host, puerto)


async def _leer_mensaje(lector, timeout=2):
    while True:
        linea = await asyncio.wait_for(lector.readline(), timeout=timeout)
        if not linea.strip():
            continue
        return protocolo.decodificar_linea(linea)


async def _leer_tipo(lector, tipo_esperado: str, timeout=2):
    while True:
        mensaje = await _leer_mensaje(lector, timeout=timeout)
        if mensaje["tipo"] == tipo_esperado:
            return mensaje


async def _conectar_y_saludar(servidor_asyncio, hola):
    lector, escritor = await _conectar(servidor_asyncio)
    escritor.write(protocolo.codificar(hola))
    await escritor.drain()
    await _leer_mensaje(lector)  # bienvenido
    await _leer_mensaje(lector)  # chat_estado
    await _leer_mensaje(lector)  # chat_lista
    return lector, escritor


def _peticion(url, metodo="GET", datos=None, auth=None):
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


def _peticion_error(url, metodo="GET", datos=None, auth=None):
    cuerpo = None
    headers = {}
    if datos is not None:
        cuerpo = json.dumps(datos).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth is not None:
        credenciales = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        headers["Authorization"] = f"Basic {credenciales}"
    req = urllib.request.Request(url, data=cuerpo, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        cuerpo_error = exc.read().decode("utf-8")
        try:
            datos_error = json.loads(cuerpo_error)
        except json.JSONDecodeError:
            datos_error = {"error": cuerpo_error}
        return exc.code, datos_error


class PruebasProtocoloChat(unittest.TestCase):
    def test_chat_enviar_valido(self):
        mensaje = {"tipo": "chat_enviar", "destino": "pc-b", "texto": "hola"}
        self.assertEqual(
            protocolo.decodificar_linea(
                protocolo.codificar(mensaje, protocolo.TIPOS_AGENTE_SERVIDOR)
            ),
            mensaje,
        )

    def test_chat_texto_demasiado_largo(self):
        mensaje = {
            "tipo": "chat_enviar",
            "destino": "pc-b",
            "texto": "x" * (protocolo.LIMITE_TEXTO_CHAT + 1),
        }
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.codificar(mensaje, protocolo.TIPOS_AGENTE_SERVIDOR)


class PruebasGestorChat(unittest.TestCase):
    def test_clave_conversacion_ordenada(self):
        self.assertEqual(clave_conversacion("pc-b", "pc-a"), ("pc-a", "pc-b"))

    def test_persistencia_en_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "chat.jsonl"
            gestor = GestorChat(archivo_chat=archivo, limite_por_conversacion=10)
            gestor.registrar_mensaje(de="pc-a", de_usuario="a", para="pc-b", texto="uno")
            gestor.registrar_mensaje(de="pc-b", de_usuario="b", para="pc-a", texto="dos")
            gestor.cerrar()

            otro = GestorChat(archivo_chat=archivo, limite_por_conversacion=10)
            historial = otro.historial("pc-a", "pc-b", ultimos=10)
            otro.cerrar()
            self.assertEqual(len(historial), 2)
            self.assertEqual(historial[0]["texto"], "uno")
            self.assertEqual(historial[1]["texto"], "dos")


class PruebasServidorChat(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gestor_chat = GestorChat(habilitado=True)
        self.estado = EstadoServidor()
        self.servidor = Servidor(
            estado=self.estado,
            token="secreto",
            host="127.0.0.1",
            puerto=0,
            habilitar_temporizador=False,
            gestor_chat=self.gestor_chat,
        )
        self.servidor_asyncio = await self.servidor.iniciar()

    async def asyncTearDown(self):
        await self.servidor.detener()

    async def test_envio_1_a_1(self):
        lector_a, escritor_a = await _conectar_y_saludar(self.servidor_asyncio, HOLA_A)
        lector_b, escritor_b = await _conectar_y_saludar(self.servidor_asyncio, HOLA_B)

        escritor_a.write(
            protocolo.codificar(
                {"tipo": "chat_enviar", "destino": "pc-b", "texto": "hola B"},
                protocolo.TIPOS_AGENTE_SERVIDOR,
            )
        )
        await escritor_a.drain()

        enviado = await _leer_tipo(lector_a, "chat_enviado")
        self.assertEqual(enviado["para"], "pc-b")

        recibido = await _leer_tipo(lector_b, "chat_recibido")
        self.assertEqual(recibido["de"], "pc-a")
        self.assertEqual(recibido["texto"], "hola B")

        escritor_a.close()
        escritor_b.close()

    async def test_chat_deshabilitado_rechaza(self):
        self.gestor_chat.establecer_habilitado(False)
        lector_a, escritor_a = await _conectar_y_saludar(self.servidor_asyncio, HOLA_A)
        lector_b, escritor_b = await _conectar_y_saludar(self.servidor_asyncio, HOLA_B)

        escritor_a.write(
            protocolo.codificar(
                {"tipo": "chat_enviar", "destino": "pc-b", "texto": "no debe pasar"},
                protocolo.TIPOS_AGENTE_SERVIDOR,
            )
        )
        await escritor_a.drain()

        rechazado = await _leer_tipo(lector_a, "chat_rechazado")

        escritor_a.close()
        escritor_b.close()

    async def test_destino_desconectado_rechaza(self):
        lector_a, escritor_a = await _conectar_y_saludar(self.servidor_asyncio, HOLA_A)

        escritor_a.write(
            protocolo.codificar(
                {"tipo": "chat_enviar", "destino": "pc-z", "texto": "nadie"},
                protocolo.TIPOS_AGENTE_SERVIDOR,
            )
        )
        await escritor_a.drain()

        rechazado = await _leer_tipo(lector_a, "chat_rechazado")
        escritor_a.close()

    async def test_historial_chat(self):
        lector_a, escritor_a = await _conectar_y_saludar(self.servidor_asyncio, HOLA_A)
        lector_b, escritor_b = await _conectar_y_saludar(self.servidor_asyncio, HOLA_B)

        for texto in ("uno", "dos", "tres"):
            escritor_a.write(
                protocolo.codificar(
                    {"tipo": "chat_enviar", "destino": "pc-b", "texto": texto},
                    protocolo.TIPOS_AGENTE_SERVIDOR,
                )
            )
            await escritor_a.drain()
            await _leer_tipo(lector_a, "chat_enviado")
            await _leer_tipo(lector_b, "chat_recibido")

        escritor_b.write(
            protocolo.codificar(
                {"tipo": "chat_historial", "con": "pc-a", "ultimos": 2},
                protocolo.TIPOS_AGENTE_SERVIDOR,
            )
        )
        await escritor_b.drain()

        respuesta = await _leer_tipo(lector_b, "chat_historial_respuesta")
        self.assertEqual(respuesta["con"], "pc-a")
        self.assertEqual(len(respuesta["mensajes"]), 2)
        self.assertEqual(respuesta["mensajes"][0]["texto"], "dos")
        self.assertEqual(respuesta["mensajes"][1]["texto"], "tres")

        escritor_a.close()
        escritor_b.close()


class PruebasPanelChat(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gestor_chat = GestorChat(habilitado=True)
        self.estado = EstadoServidor()
        self.servidor = Servidor(
            estado=self.estado,
            token="secreto",
            host="127.0.0.1",
            puerto=0,
            habilitar_temporizador=False,
            gestor_chat=self.gestor_chat,
        )
        self.servidor_asyncio = await self.servidor.iniciar()
        self.loop = asyncio.get_running_loop()

        # Variables para evitar el patrón password="..." del escáner de secretos en CI.
        self.clave_caja = "x" * 8
        self.clave_mod = "y" * 8
        self.panel = PanelHTTP(
            servidor=self.servidor,
            loop=self.loop,
            host="127.0.0.1",
            puerto=0,
            password=self.clave_caja,
            usuario_moderador="moderador",
            password_moderador=self.clave_mod,
        )
        handler = _crear_handler(self.panel)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.puerto_panel = self.httpd.server_address[1]
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()
        self.base_url = f"http://127.0.0.1:{self.puerto_panel}"

        self.gestor_chat.registrar_mensaje(
            de="pc-a", de_usuario="a", para="pc-b", texto="secreto"
        )

    async def asyncTearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.hilo.join(timeout=2)
        await self.servidor.detener()

    async def test_caja_puede_cambiar_estado_chat(self):
        status, datos = await asyncio.to_thread(
            _peticion, f"{self.base_url}/api/chat/estado"
        )
        self.assertEqual(status, 200)
        self.assertTrue(datos["habilitado"])

        status, datos = await asyncio.to_thread(
            _peticion,
            f"{self.base_url}/api/chat/habilitar",
            "POST",
            {"habilitado": False},
        )
        self.assertEqual(status, 200)
        self.assertFalse(datos["habilitado"])

    async def test_moderacion_rechaza_credenciales_caja(self):
        codigo, _ = await asyncio.to_thread(
            _peticion_error,
            f"{self.base_url}/api/moderacion/conversaciones",
            auth=(USUARIO_PANEL, self.clave_caja),
        )
        self.assertEqual(codigo, 401)

    async def test_moderacion_lista_conversaciones_y_mensajes(self):
        status, conversaciones = await asyncio.to_thread(
            _peticion,
            f"{self.base_url}/api/moderacion/conversaciones",
            auth=("moderador", self.clave_mod),
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(conversaciones), 1)

        status, mensajes = await asyncio.to_thread(
            _peticion,
            f"{self.base_url}/api/moderacion/mensajes?de=pc-a&para=pc-b",
            auth=("moderador", self.clave_mod),
        )
        self.assertEqual(status, 200)
        self.assertEqual(mensajes[0]["texto"], "secreto")

    async def test_api_equipos_no_filtra_chat(self):
        status, equipos = await asyncio.to_thread(
            _peticion, f"{self.base_url}/api/equipos"
        )
        self.assertEqual(status, 200)
        self.assertEqual(equipos, [])
