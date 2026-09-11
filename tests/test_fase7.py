import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from servidor.ad import ConsultorAD
from servidor.estado import EstadoServidor
from servidor.respaldo import EnviadorRespaldo


class PruebasHistorialCSV(unittest.TestCase):
    def test_exporta_columnas_esperadas(self):
        estado = EstadoServidor()
        estado.registrar_evento("conectado", equipo="pc-01", usuario="dquan", ip="10.0.0.1", so="linux")
        estado.registrar_evento("mensaje_enviado", equipo="pc-01", id_mensaje="abc-123")

        csv_texto = estado.historial_csv()
        lineas = csv_texto.strip().splitlines()
        self.assertEqual(lineas[0], "cuando,tipo,equipo,usuario,ip,so,id_mensaje,minutos")
        self.assertIn("conectado", lineas[1])
        self.assertIn("pc-01", csv_texto)
        self.assertIn("abc-123", csv_texto)


class PruebasEquiposAD(unittest.TestCase):
    def test_fusiona_equipos_ad_sin_agente(self):
        estado = EstadoServidor()
        estado.registrar_conexion(
            nombre="pc-01",
            so="linux",
            version_so="22.04",
            usuario="dquan",
            version_agente="0.1.0",
            ip="10.0.0.1",
            escritor=mock.Mock(),
        )
        equipos_ad = [
            {"nombre": "pc-02", "so": "windows"},
            {"nombre": "pc-01", "so": "linux"},
        ]
        resultado = estado.obtener_equipos_api(equipos_ad)
        nombres = {e["nombre"] for e in resultado}
        self.assertEqual(nombres, {"pc-01", "pc-02"})
        sin_agente = next(e for e in resultado if e["nombre"] == "pc-02")
        self.assertTrue(sin_agente["sin_agente"])
        self.assertFalse(sin_agente["conectado"])


class PruebasConsultorAD(unittest.TestCase):
    def test_lee_archivo_respaldo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "equipos.json"
            ruta.write_text(
                json.dumps(
                    [
                        {"nombre": "PC-03", "so": "windows"},
                        "pc-04",
                    ]
                ),
                encoding="utf-8",
            )
            consultor = ConsultorAD(
                habilitado=True,
                archivo_respaldo=ruta,
                intervalo_segundos=60,
            )
            equipos = consultor.listar_equipos()
            self.assertEqual(len(equipos), 2)
            self.assertEqual(equipos[0]["nombre"], "pc-03")
            self.assertEqual(equipos[1]["nombre"], "pc-04")


class PruebasEnviadorRespaldo(unittest.TestCase):
    def test_deshabilitado_no_envia(self):
        enviador = EnviadorRespaldo(habilitado=False)
        resultado = enviador.enviar("pc-01", "Hola", "windows")
        self.assertFalse(resultado["ok"])
        self.assertIn("deshabilitado", resultado["error"])

    @mock.patch("servidor.respaldo.subprocess.run")
    @mock.patch("servidor.respaldo.shutil.which", return_value="/usr/bin/msg.exe")
    def test_msg_windows_ok(self, _which, run_mock):
        run_mock.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        enviador = EnviadorRespaldo(habilitado=True, dominio="lab.lan")
        resultado = enviador.enviar("pc-01", "Aviso de prueba", "windows")
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["metodo"], "msg.exe")
        comando = run_mock.call_args[0][0]
        self.assertEqual(comando[0], "msg.exe")
        self.assertIn("pc-01.lab.lan", comando[1])


class PruebasTLS(unittest.TestCase):
    def test_crear_contextos(self):
        from comun.tls import crear_contexto_cliente, crear_contexto_servidor

        with tempfile.TemporaryDirectory() as tmp:
            from subprocess import run

            cert = Path(tmp) / "servidor.pem"
            run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    str(cert),
                    "-out",
                    str(cert),
                    "-days",
                    "1",
                    "-nodes",
                    "-subj",
                    "/CN=localhost",
                ],
                check=True,
                capture_output=True,
            )
            ctx_servidor = crear_contexto_servidor(cert, cert)
            ctx_cliente = crear_contexto_cliente()
            self.assertIsNotNone(ctx_servidor)
            self.assertIsNotNone(ctx_cliente)


if __name__ == "__main__":
    unittest.main()
