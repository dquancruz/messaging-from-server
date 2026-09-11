"""Manda un mensaje de prueba a equipos conectados vía el panel web.

Requiere que el servidor esté corriendo con el panel en ``puerto_panel``
(8080 por defecto en ``servidor/config.json``).

Uso:
    python herramientas/enviar_mensaje.py --destinos todos --texto "Hola"
    python herramientas/enviar_mensaje.py --destinos pc-01 --texto "Prueba" --nivel aviso
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comun import protocolo  # noqa: E402


def _enviar(
    host: str,
    puerto: int,
    destinos: list[str] | str,
    texto: str,
    nivel: str,
) -> dict:
    cuerpo = json.dumps(
        {"destinos": destinos, "texto": texto, "nivel": nivel},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{puerto}/api/mensaje",
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enviar un mensaje de prueba a agentes")
    parser.add_argument(
        "--destinos",
        nargs="+",
        required=True,
        help="nombres de equipo o 'todos'",
    )
    parser.add_argument("--texto", required=True)
    parser.add_argument("--nivel", choices=("info", "aviso", "critico"), default="info")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=protocolo.PUERTO_PANEL_POR_DEFECTO)
    args = parser.parse_args(argv)

    destinos: list[str] | str
    if len(args.destinos) == 1 and args.destinos[0] == "todos":
        destinos = "todos"
    else:
        destinos = [d.strip().lower() for d in args.destinos]

    try:
        respuesta = _enviar(args.host, args.puerto, destinos, args.texto, args.nivel)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Error: no se pudo conectar al panel ({exc})", file=sys.stderr)
        return 1

    if "error" in respuesta:
        print(f"Error: {respuesta['error']}", file=sys.stderr)
        return 1

    print(f"Mensaje enviado a {respuesta.get('enviados', 0)} equipo(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
