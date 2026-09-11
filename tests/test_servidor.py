import asyncio
import unittest

from comun import protocolo
from servidor.estado import EstadoServidor
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


async def _conectar(servidor_asyncio):
    host, puerto = servidor_asyncio.sockets[0].getsockname()[:2]
    return await asyncio.open_connection(host, puerto)


async def _leer_mensaje(lector, timeout=2):
    linea = await asyncio.wait_for(lector.readline(), timeout=timeout)
    return protocolo.decodificar_linea(linea)


class PruebasServidor(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.estado = EstadoServidor()
        self.servidor = Servidor(
            estado=self.estado,
            token="secreto",
            host="127.0.0.1",
            puerto=0,
            timeout_desconexion=0.3,
        )
        self.servidor_asyncio = await self.servidor.iniciar()

    async def asyncTearDown(self):
        await self.servidor.detener()

    async def test_registro_exitoso(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar(HOLA_BASE))
        await escritor.drain()

        bienvenida = await _leer_mensaje(lector)
        self.assertEqual(bienvenida, {"tipo": "bienvenido", "sesion": None, "bloqueado": False})

        await asyncio.sleep(0.05)  # dejar que el servidor termine de registrar
        self.assertIn("pc-01", self.estado.equipos)
        self.assertTrue(self.estado.equipos["pc-01"].conectado)
        self.assertEqual(self.estado.equipos["pc-01"].so, "linux")

    async def test_token_incorrecto_es_rechazado(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar({**HOLA_BASE, "token": "malo", "equipo": "PC-02"}))
        await escritor.drain()

        respuesta = await _leer_mensaje(lector)
        self.assertEqual(respuesta["tipo"], "rechazado")
        self.assertEqual(respuesta["motivo"], "token incorrecto")

        await asyncio.sleep(0.05)
        self.assertNotIn("pc-02", self.estado.equipos)

    async def test_se_espera_hola_como_primer_mensaje(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar({"tipo": "ping"}))
        await escritor.drain()

        respuesta = await _leer_mensaje(lector)
        self.assertEqual(respuesta["tipo"], "rechazado")

    async def test_ping_recibe_pong(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar({**HOLA_BASE, "equipo": "PC-03"}))
        await escritor.drain()
        await _leer_mensaje(lector)  # bienvenido

        escritor.write(protocolo.codificar({"tipo": "ping"}))
        await escritor.drain()
        respuesta = await _leer_mensaje(lector)
        self.assertEqual(respuesta, {"tipo": "pong"})

    async def test_visto_queda_en_el_historial(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar({**HOLA_BASE, "equipo": "PC-05"}))
        await escritor.drain()
        await _leer_mensaje(lector)  # bienvenido

        escritor.write(protocolo.codificar({"tipo": "visto", "id": "abc-123"}))
        await escritor.drain()
        await asyncio.sleep(0.05)

        eventos_visto = [e for e in self.estado.historial() if e["tipo"] == "visto"]
        self.assertEqual(len(eventos_visto), 1)
        self.assertEqual(eventos_visto[0]["id_mensaje"], "abc-123")

    async def test_se_desconecta_por_falta_de_latido(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar({**HOLA_BASE, "equipo": "PC-04"}))
        await escritor.drain()
        await _leer_mensaje(lector)  # bienvenido

        await asyncio.sleep(0.05)
        self.assertTrue(self.estado.equipos["pc-04"].conectado)

        # no mandamos nada más: debe superarse timeout_desconexion (0.3s)
        await asyncio.sleep(0.6)
        self.assertFalse(self.estado.equipos["pc-04"].conectado)

    async def test_linea_demasiado_grande_al_saludar_no_tumba_el_servidor(self):
        # regresión: el servidor esperaba asyncio.LimitOverrunError, pero
        # readline() en realidad levanta ValueError -- sin este fix, esto
        # dejaba una excepción sin atrapar en la tarea de la conexión.
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(b"x" * (protocolo.TAMANO_MAXIMO_MENSAJE + 100))
        await escritor.drain()

        # el servidor cierra la conexión en vez de tumbarse
        resto = await asyncio.wait_for(lector.read(), timeout=2)
        self.assertEqual(resto, b"")
        self.assertEqual(self.estado.equipos, {})

        # el servidor sigue vivo: otro agente se puede conectar normal
        lector2, escritor2 = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor2.close)
        escritor2.write(protocolo.codificar({**HOLA_BASE, "equipo": "PC-07"}))
        await escritor2.drain()
        bienvenida = await _leer_mensaje(lector2)
        self.assertEqual(bienvenida["tipo"], "bienvenido")

    async def test_linea_demasiado_grande_en_bucle_mensajes(self):
        lector, escritor = await _conectar(self.servidor_asyncio)
        self.addCleanup(escritor.close)

        escritor.write(protocolo.codificar({**HOLA_BASE, "equipo": "PC-08"}))
        await escritor.drain()
        await _leer_mensaje(lector)  # bienvenido
        await asyncio.sleep(0.05)
        self.assertTrue(self.estado.equipos["pc-08"].conectado)

        escritor.write(b"x" * (protocolo.TAMANO_MAXIMO_MENSAJE + 100))
        await escritor.drain()

        resto = await asyncio.wait_for(lector.read(), timeout=2)
        self.assertEqual(resto, b"")
        self.assertFalse(self.estado.equipos["pc-08"].conectado)

    async def test_desconexion_limpia_al_cerrar_el_cliente(self):
        lector, escritor = await _conectar(self.servidor_asyncio)

        escritor.write(protocolo.codificar({**HOLA_BASE, "equipo": "PC-06"}))
        await escritor.drain()
        await _leer_mensaje(lector)  # bienvenido
        await asyncio.sleep(0.05)
        self.assertTrue(self.estado.equipos["pc-06"].conectado)

        escritor.close()
        await asyncio.sleep(0.05)  # no hace falta esperar el timeout: fue EOF
        self.assertFalse(self.estado.equipos["pc-06"].conectado)


if __name__ == "__main__":
    unittest.main()
