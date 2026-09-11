import tempfile
import unittest
from pathlib import Path

from servidor.estado import EstadoServidor


class ConexionFalsa:
    """Reemplaza un asyncio.StreamWriter en pruebas que no abren sockets
    de verdad."""


class PruebasHistorial(unittest.TestCase):
    def test_historial_ultimos_cero_devuelve_vacio(self):
        # regresión: self._historial[-0:] es todo el historial, no nada
        estado = EstadoServidor()
        estado.registrar_evento("conectado", equipo="pc-01")
        self.assertEqual(estado.historial(ultimos=0), [])
        self.assertEqual(estado.historial(ultimos=-5), [])
        self.assertEqual(len(estado.historial(ultimos=100)), 1)

    def test_historial_se_recarga_al_reiniciar(self):
        # regresión: el docstring promete que historial.jsonl sobrevive un
        # reinicio, pero __init__ no lo leía de vuelta
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "historial.jsonl"

            primero = EstadoServidor(archivo_historial=archivo)
            primero.registrar_evento("conectado", equipo="pc-01")
            primero.registrar_evento("desconectado", equipo="pc-01")
            primero.cerrar()  # espera a que termine de escribir a disco

            segundo = EstadoServidor(archivo_historial=archivo)
            try:
                eventos = segundo.historial()
                self.assertEqual(len(eventos), 2)
                self.assertEqual(eventos[0]["tipo"], "conectado")
                self.assertEqual(eventos[1]["tipo"], "desconectado")
            finally:
                segundo.cerrar()

    def test_historial_archivo_inexistente_no_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "no-existe" / "historial.jsonl"
            estado = EstadoServidor(archivo_historial=archivo)
            try:
                self.assertEqual(estado.historial(), [])
            finally:
                estado.cerrar()


class PruebasRegistroDeEquipos(unittest.TestCase):
    def test_conexion_registra_y_se_puede_quitar(self):
        estado = EstadoServidor()
        id_conexion = estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="127.0.0.1",
            escritor=ConexionFalsa(),
        )
        self.assertIn("pc-01", estado.equipos)
        self.assertTrue(estado.equipos["pc-01"].conectado)

        estado.quitar_conexion("pc-01", id_conexion)
        self.assertFalse(estado.equipos["pc-01"].conectado)

    def test_dos_conexiones_del_mismo_equipo(self):
        estado = EstadoServidor()
        id1 = estado.registrar_conexion(
            nombre="pc-01", so="linux", version_so="22.04", usuario="ana",
            version_agente="0.1.0", ip="127.0.0.1", escritor=ConexionFalsa(),
        )
        estado.registrar_conexion(
            nombre="pc-01", so="linux", version_so="22.04", usuario="beto",
            version_agente="0.1.0", ip="127.0.0.1", escritor=ConexionFalsa(),
        )
        self.assertEqual(estado.equipos["pc-01"].a_dict()["conexiones_activas"], 2)

        estado.quitar_conexion("pc-01", id1)
        self.assertTrue(estado.equipos["pc-01"].conectado)  # queda la de beto


if __name__ == "__main__":
    unittest.main()
