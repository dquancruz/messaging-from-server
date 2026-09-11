"""Manda un mensaje de prueba a equipos conectados vía el puerto admin local.

Requiere que el servidor esté corriendo con ``puerto_admin`` habilitado
(5051 por defecto en ``servidor/config.json``).

Uso:
    python herramientas/enviar_mensaje.py --destinos todos --texto "Hola"
    python herramientas/enviar_mensaje.py --destinos pc-01 --texto "Prueba" --nivel aviso
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from servidor.admin import PUERTO_ADMIN_POR_DEFECTO  # noqa: E402


async def _enviar(
    host: str,
    puerto: int,
    destinos: list[str] | str,
    texto: str,
    titulo: str,
    nivel: str,
    pedir_visto: bool,
) -> dict:
    lector, escritor = await asyncio.open_connection(host, puerto)
    comando = {
        "accion": "mensaje",
        "destinos": destinos,
        "titulo": titulo,
        "texto": texto,
        "nivel": nivel,
        "pedir_visto": pedir_visto,
    }
    escritor.write((json.dumps(comando, ensure_ascii=False) + "\n").encode("utf-8"))
    await escritor.drain()
    linea = await lector.readline()
    escritor.close()
    await escritor.wait_closed()
    if not linea:
        raise ConnectionError("el servidor admin no respondió")
    return json.loads(linea.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enviar un mensaje de prueba a agentes")
    parser.add_argument(
        "--destinos",
        nargs="+",
        required=True,
        help="nombres de equipo o 'todos'",
    )
    parser.add_argument("--texto", required=True)
    parser.add_argument("--titulo", default="Cibercafé")
    parser.add_argument("--nivel", choices=("info", "aviso", "critico"), default="info")
    parser.add_argument("--pedir-visto", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=PUERTO_ADMIN_POR_DEFECTO)
    args = parser.parse_args(argv)

    destinos: list[str] | str
    if len(args.destinos) == 1 and args.destinos[0] == "todos":
        destinos = "todos"
    else:
        destinos = [d.strip().lower() for d in args.destinos]

    try:
        respuesta = asyncio.run(
            _enviar(
                args.host,
                args.puerto,
                destinos,
                args.texto,
                args.titulo,
                args.nivel,
                args.pedir_visto,
            )
        )
    except (ConnectionError, OSError) as exc:
        print(f"Error: no se pudo conectar al admin ({exc})", file=sys.stderr)
        return 1

    if not respuesta.get("ok"):
        print(f"Error: {respuesta.get('error', 'desconocido')}", file=sys.stderr)
        return 1

    print(f"Mensaje enviado a {respuesta.get('enviados', 0)} conexión(es).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
