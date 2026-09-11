import json
import unittest

from comun import protocolo


class PruebasCodificarDecodificar(unittest.TestCase):
    def test_ida_y_vuelta(self):
        original = {"tipo": "ping"}
        datos = protocolo.codificar(original)
        self.assertTrue(datos.endswith(b"\n"))
        self.assertEqual(protocolo.decodificar_linea(datos), original)

    def test_decodifica_str_ademas_de_bytes(self):
        mensaje = json.dumps({"tipo": "pong"})
        self.assertEqual(protocolo.decodificar_linea(mensaje)["tipo"], "pong")

    def test_tipo_desconocido(self):
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(json.dumps({"tipo": "no-existe"}))

    def test_falta_campo_requerido(self):
        # 'hola' necesita 'token', entre otros campos
        incompleto = {"tipo": "hola", "equipo": "PC-01"}
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.codificar(incompleto)
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(json.dumps(incompleto))

    def test_sin_tipo(self):
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(json.dumps({"texto": "hola"}))

    def test_json_invalido(self):
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea("{esto no es json")

    def test_linea_cortada(self):
        completo = json.dumps(
            {
                "tipo": "mensaje",
                "id": "x",
                "titulo": "t",
                "texto": "hola",
                "nivel": "info",
                "pedir_visto": False,
            }
        )
        cortada = completo[: len(completo) // 2]
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(cortada)

    def test_mensaje_no_es_objeto(self):
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(json.dumps(["tipo", "ping"]))

    def test_linea_vacia(self):
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea("")
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(b"   \n")

    def test_mensaje_demasiado_grande(self):
        gigante = {
            "tipo": "mensaje",
            "id": "x",
            "titulo": "t",
            "texto": "a" * (protocolo.TAMANO_MAXIMO_MENSAJE + 100),
            "nivel": "info",
            "pedir_visto": False,
        }
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.codificar(gigante)

        datos = (json.dumps(gigante) + "\n").encode("utf-8")
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.decodificar_linea(datos)

    def test_codificar_tipo_desconocido(self):
        with self.assertRaises(protocolo.ErrorProtocolo):
            protocolo.codificar({"tipo": "no-existe"})


if __name__ == "__main__":
    unittest.main()
