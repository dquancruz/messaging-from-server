"""Chat 1:1 entre clientes: almacén en memoria y persistencia en chat.jsonl."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

registrador = logging.getLogger("servidor.chat")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clave_conversacion(equipo_a: str, equipo_b: str) -> tuple[str, str]:
    """Par ordenado de hostnames que identifica una conversación 1:1."""
    a = equipo_a.strip().lower()
    b = equipo_b.strip().lower()
    return (a, b) if a < b else (b, a)


@dataclass
class MensajeChat:
    id: str
    de: str
    de_usuario: str
    para: str
    texto: str
    cuando: str

    def a_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "de": self.de,
            "de_usuario": self.de_usuario,
            "texto": self.texto,
            "cuando": self.cuando,
        }


class GestorChat:
    """Mensajes de chat por conversación, con límite y escritura a disco."""

    def __init__(
        self,
        archivo_chat: Path | str | None = None,
        limite_por_conversacion: int = 500,
        habilitado: bool = True,
    ) -> None:
        self._mensajes: dict[tuple[str, str], list[MensajeChat]] = {}
        self._limite = limite_por_conversacion
        self._habilitado = habilitado
        self._archivo_chat = Path(archivo_chat) if archivo_chat else None
        self._executor = (
            concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="chat")
            if self._archivo_chat is not None
            else None
        )
        if self._archivo_chat is not None:
            self._cargar_desde_disco()

    def cerrar(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True)

    @property
    def habilitado(self) -> bool:
        return self._habilitado

    def establecer_habilitado(self, valor: bool) -> bool:
        """Cambia el estado del chat. Devuelve True si hubo cambio."""
        if self._habilitado == valor:
            return False
        self._habilitado = valor
        return True

    def registrar_mensaje(
        self,
        *,
        de: str,
        de_usuario: str,
        para: str,
        texto: str,
    ) -> MensajeChat:
        nombre_de = de.strip().lower()
        nombre_para = para.strip().lower()
        mensaje = MensajeChat(
            id=str(uuid.uuid4()),
            de=nombre_de,
            de_usuario=de_usuario,
            para=nombre_para,
            texto=texto,
            cuando=_ahora(),
        )
        clave = clave_conversacion(nombre_de, nombre_para)
        lista = self._mensajes.setdefault(clave, [])
        lista.append(mensaje)
        if len(lista) > self._limite:
            self._mensajes[clave] = lista[-self._limite :]
        if self._archivo_chat is not None:
            self._escribir_en_segundo_plano(mensaje)
        return mensaje

    def historial(
        self,
        origen: str,
        con: str,
        ultimos: int = 50,
    ) -> list[dict[str, str]]:
        clave = clave_conversacion(origen, con)
        mensajes = self._mensajes.get(clave, [])
        if ultimos <= 0:
            return []
        return [m.a_dict() for m in mensajes[-ultimos:]]

    def listar_conversaciones(self) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = []
        for (a, b), mensajes in self._mensajes.items():
            if not mensajes:
                continue
            ultimo = mensajes[-1]
            resultado.append(
                {
                    "equipo_a": a,
                    "equipo_b": b,
                    "mensajes": len(mensajes),
                    "ultimo_cuando": ultimo.cuando,
                }
            )
        return sorted(resultado, key=lambda c: c["ultimo_cuando"], reverse=True)

    def mensajes_conversacion(
        self,
        equipo_a: str,
        equipo_b: str,
        ultimos: int = 50,
    ) -> list[dict[str, str]]:
        clave = clave_conversacion(equipo_a, equipo_b)
        mensajes = self._mensajes.get(clave, [])
        if ultimos <= 0:
            return []
        return [m.a_dict() for m in mensajes[-ultimos:]]

    def _cargar_desde_disco(self) -> None:
        assert self._archivo_chat is not None
        if not self._archivo_chat.exists():
            return
        try:
            lineas = self._archivo_chat.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            registrador.warning("no se pudo leer chat.jsonl: %s", exc)
            return

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            try:
                datos = json.loads(linea)
            except json.JSONDecodeError:
                registrador.warning("línea inválida en chat.jsonl, se ignora")
                continue
            try:
                mensaje = MensajeChat(
                    id=str(datos["id"]),
                    de=str(datos["de"]).strip().lower(),
                    de_usuario=str(datos.get("de_usuario", "")),
                    para=str(datos["para"]).strip().lower(),
                    texto=str(datos["texto"]),
                    cuando=str(datos["cuando"]),
                )
            except (KeyError, TypeError):
                registrador.warning("mensaje inválido en chat.jsonl, se ignora")
                continue
            clave = clave_conversacion(mensaje.de, mensaje.para)
            lista = self._mensajes.setdefault(clave, [])
            lista.append(mensaje)
            if len(lista) > self._limite:
                self._mensajes[clave] = lista[-self._limite :]

    def _escribir_en_segundo_plano(self, mensaje: MensajeChat) -> None:
        registro = {
            "id": mensaje.id,
            "de": mensaje.de,
            "de_usuario": mensaje.de_usuario,
            "para": mensaje.para,
            "texto": mensaje.texto,
            "cuando": mensaje.cuando,
        }
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._escribir_a_disco(registro)
            return
        loop.run_in_executor(self._executor, self._escribir_a_disco, registro)

    def _escribir_a_disco(self, registro: dict[str, str]) -> None:
        assert self._archivo_chat is not None
        try:
            self._archivo_chat.parent.mkdir(parents=True, exist_ok=True)
            with self._archivo_chat.open("a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        except OSError as exc:
            registrador.warning("no se pudo escribir chat.jsonl: %s", exc)
