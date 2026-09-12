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


class RelojSimulado:
    def __init__(self, inicio: float = 0.0) -> None:
        self._tiempo = inicio

    def ahora(self) -> float:
        return self._tiempo

    def avanzar(self, segundos: float) -> None:
        self._tiempo += segundos


class PruebasGestorSesiones(unittest.TestCase):
    def setUp(self):
        self.reloj = RelojSimulado()
        self.estado = EstadoServidor(
            avisos_minutos=[5, 1],
            texto_fin_sesion="Tu tiempo terminó.",
            reloj=self.reloj.ahora,
        )
        self.estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="127.0.0.1",
            escritor=object(),
        )

    def test_iniciar_y_tiempo_restante(self):
        self.estado.iniciar_sesion("pc-01", 30)
        self.assertEqual(self.estado.sesiones.tiempo_restante("pc-01"), 30 * 60)
        self.reloj.avanzar(60)
        self.assertEqual(self.estado.sesiones.tiempo_restante("pc-01"), 29 * 60)

    def test_avisos_no_se_repiten(self):
        self.estado.iniciar_sesion("pc-01", 6)
        self.reloj.avanzar(60)
        acciones = self.estado.revisar_sesiones()
        avisos = [a for a in acciones if a.mensaje["tipo"] == "mensaje"]
        self.assertEqual(len(avisos), 1)
        self.assertIn("5 minutos", avisos[0].mensaje["texto"])

        acciones2 = self.estado.revisar_sesiones()
        avisos2 = [a for a in acciones2 if a.mensaje["tipo"] == "mensaje"]
        self.assertEqual(len(avisos2), 0)

    def test_extender_desbloquea_y_suma_tiempo(self):
        self.estado.iniciar_sesion("pc-01", 10)
        self.reloj.avanzar(10 * 60)
        self.estado.sesiones._bloqueados["pc-01"] = True
        self.estado.extender_sesion("pc-01", 15)
        self.assertFalse(self.estado.sesiones.esta_bloqueado("pc-01"))
        self.assertEqual(self.estado.sesiones.tiempo_restante("pc-01"), 15 * 60)

    def test_al_cero_manda_bloquear(self):
        self.estado.iniciar_sesion("pc-01", 1)
        self.reloj.avanzar(61)
        acciones = self.estado.revisar_sesiones()
        tipos = [a.mensaje["tipo"] for a in acciones]
        self.assertIn("bloquear", tipos)
        self.assertTrue(self.estado.sesiones.esta_bloqueado("pc-01"))


class PruebasServidorSesiones(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.reloj = RelojSimulado()
        self.estado = EstadoServidor(
            avisos_minutos=[1],
            texto_fin_sesion="Tu tiempo terminó.",
            reloj=self.reloj.ahora,
        )
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

    async def _conectar(self):
        host, puerto = self.servidor_asyncio.sockets[0].getsockname()[:2]
        return await asyncio.open_connection(host, puerto)

    async def test_bienvenido_incluye_sesion_activa(self):
        lector, escritor = await self._conectar()
        self.addCleanup(escritor.close)
        escritor.write(protocolo.codificar(HOLA_BASE))
        await escritor.drain()
        await lector.readline()
        await asyncio.sleep(0.05)

        self.estado.sesiones.iniciar("pc-01", 2)

        lector2, escritor2 = await self._conectar()
        self.addCleanup(escritor2.close)
        escritor2.write(protocolo.codificar(HOLA_BASE))
        await escritor2.drain()

        linea = await asyncio.wait_for(lector2.readline(), timeout=2)
        bienvenida = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(bienvenida["tipo"], "bienvenido")
        self.assertEqual(bienvenida["sesion"], 120)
        self.assertFalse(bienvenida["bloqueado"])

    async def test_iniciar_sesion_envia_contador(self):
        lector, escritor = await self._conectar()
        self.addCleanup(escritor.close)
        escritor.write(protocolo.codificar(HOLA_BASE))
        await escritor.drain()
        await lector.readline()
        await asyncio.sleep(0.05)

        await self.servidor.iniciar_sesion("pc-01", 2)

        linea = await asyncio.wait_for(lector.readline(), timeout=2)
        mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(mensaje, {"tipo": "desbloquear"})

        linea = await asyncio.wait_for(lector.readline(), timeout=2)
        mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(mensaje["tipo"], "sesion")
        self.assertEqual(mensaje["restante"], 120)

    def test_reconexion_a_mitad_de_sesion(self):
        self.estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="127.0.0.1",
            escritor=object(),
        )
        self.estado.iniciar_sesion("pc-01", 5)
        self.reloj.avanzar(120)
        self.assertEqual(self.estado.sesiones.tiempo_restante("pc-01"), 180)

    async def test_aviso_automatico_y_bloqueo(self):
        self.estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="127.0.0.1",
            escritor=object(),
        )
        self.estado.iniciar_sesion("pc-01", 2)

        self.reloj.avanzar(65)
        acciones = self.estado.revisar_sesiones()
        self.assertTrue(any(a.mensaje["tipo"] == "mensaje" for a in acciones))

        self.reloj.avanzar(60)
        acciones_fin = self.estado.revisar_sesiones()
        tipos = [a.mensaje["tipo"] for a in acciones_fin]
        self.assertIn("bloquear", tipos)
        self.assertTrue(self.estado.sesiones.esta_bloqueado("pc-01"))

    async def test_extender_desbloquea(self):
        lector, escritor = await self._conectar()
        self.addCleanup(escritor.close)
        escritor.write(protocolo.codificar(HOLA_BASE))
        await escritor.drain()
        await lector.readline()
        await asyncio.sleep(0.05)

        self.estado.sesiones._bloqueados["pc-01"] = True
        self.estado.sesiones._texto_bloqueo["pc-01"] = "Bloqueado"

        await self.servidor.extender_sesion("pc-01", 15)
        mensajes = []
        for _ in range(2):
            linea = await asyncio.wait_for(lector.readline(), timeout=2)
            mensajes.append(protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE))

        tipos = [m["tipo"] for m in mensajes]
        self.assertIn("desbloquear", tipos)
        self.assertIn("sesion", tipos)

    async def test_desbloquear_envia_mensaje_al_agente(self):
        lector, escritor = await self._conectar()
        self.addCleanup(escritor.close)
        escritor.write(protocolo.codificar(HOLA_BASE))
        await escritor.drain()
        await lector.readline()
        await asyncio.sleep(0.05)

        self.estado.sesiones._bloqueados["pc-01"] = True
        await self.servidor.desbloquear_equipo("pc-01")

        linea = await asyncio.wait_for(lector.readline(), timeout=2)
        mensaje = protocolo.decodificar_linea(linea, protocolo.TIPOS_SERVIDOR_AGENTE)
        self.assertEqual(mensaje["tipo"], "desbloquear")
        self.assertFalse(self.estado.sesiones.esta_bloqueado("pc-01"))

    async def test_desbloquear_falla_si_no_hay_conexion(self):
        from servidor.estado import Equipo

        self.estado.equipos["pc-01"] = Equipo(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            version_agente="0.1.0",
        )
        self.estado.sesiones._bloqueados["pc-01"] = True
        with self.assertRaisesRegex(ValueError, "no conectado"):
            await self.servidor.desbloquear_equipo("pc-01")
        self.assertTrue(self.estado.sesiones.esta_bloqueado("pc-01"))


if __name__ == "__main__":
    unittest.main()
