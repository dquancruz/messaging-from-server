import unittest

from servidor.estado import EstadoServidor


class ConexionFalsa:
    pass


class PruebasVisto(unittest.TestCase):
    def test_registrar_mensaje_y_visto(self):
        estado = EstadoServidor()
        estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="192.168.1.20",
            escritor=ConexionFalsa(),
        )
        estado.registrar_mensaje_enviado("pc-01", "msg-001")
        equipo = estado.equipos["pc-01"]
        self.assertEqual(equipo.ultimo_mensaje_id, "msg-001")
        self.assertIsNone(equipo.ultimo_visto)

        estado.registrar_visto("pc-01", "msg-001")
        self.assertIsNotNone(equipo.ultimo_visto)

    def test_visto_de_otro_id_no_actualiza_hora(self):
        estado = EstadoServidor()
        estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="127.0.0.1",
            escritor=ConexionFalsa(),
        )
        estado.registrar_mensaje_enviado("pc-01", "msg-nuevo")
        estado.registrar_visto("pc-01", "msg-viejo")
        self.assertIsNone(estado.equipos["pc-01"].ultimo_visto)

    def test_obtener_equipos_api(self):
        estado = EstadoServidor()
        estado.registrar_conexion(
            nombre="pc-01",
            so="windows",
            version_so="11",
            usuario="ana",
            version_agente="0.1.0",
            ip="10.0.0.5",
            escritor=ConexionFalsa(),
        )
        api = estado.obtener_equipos_api()
        self.assertEqual(api[0]["nombre"], "pc-01")
        self.assertEqual(api[0]["ip"], "10.0.0.5")
        self.assertFalse(api[0]["bloqueado"])
        self.assertIsNone(api[0]["tiempo_restante"])


if __name__ == "__main__":
    unittest.main()
