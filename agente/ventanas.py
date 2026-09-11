"""Ventanas emergentes del agente (tkinter en el hilo principal)."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

registrador = logging.getLogger("agente.ventanas")

TITULO_VENTANA = "Cibercafé"
INTERVALO_COLA_MS = 200
DESPLAZAMIENTO_APILADO = 24

COLORES_NIVEL = {
    "info": {"fondo": "#1565C0", "texto": "#FFFFFF"},
    "aviso": {"fondo": "#F9A825", "texto": "#212121"},
    "critico": {"fondo": "#C62828", "texto": "#FFFFFF"},
}


class GestorVentanas:
    """Muestra avisos encima de todo sin bloquear el hilo de red."""

    def __init__(
        self,
        root: tk.Tk,
        cola_ui: queue.Queue,
        cola_red: queue.Queue,
        al_cerrar: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.cola_ui = cola_ui
        self.cola_red = cola_red
        self.al_cerrar = al_cerrar
        self._ventanas_abiertas: list[tk.Toplevel] = []
        self._programar_revision_cola()

    def _programar_revision_cola(self) -> None:
        self.root.after(INTERVALO_COLA_MS, self._revisar_cola)

    def _revisar_cola(self) -> None:
        try:
            while True:
                evento = self.cola_ui.get_nowait()
                self._procesar_evento(evento)
        except queue.Empty:
            pass
        self._programar_revision_cola()

    def _procesar_evento(self, evento: dict) -> None:
        tipo = evento.get("tipo")
        if tipo == "mostrar_mensaje":
            self._mostrar_emergente(evento["mensaje"])
        elif tipo == "cerrar":
            self.root.quit()

    def _mostrar_emergente(self, mensaje: dict) -> None:
        nivel = mensaje.get("nivel", "info")
        colores = COLORES_NIVEL.get(nivel, COLORES_NIVEL["info"])
        indice = len(self._ventanas_abiertas)
        desplazamiento = indice * DESPLAZAMIENTO_APILADO

        ventana = tk.Toplevel(self.root)
        ventana.title(TITULO_VENTANA)
        ventana.configure(bg=colores["fondo"])
        ventana.attributes("-topmost", True)
        ventana.resizable(False, False)

        marco = tk.Frame(ventana, bg=colores["fondo"], padx=28, pady=24)
        marco.pack(fill=tk.BOTH, expand=True)

        fuente_titulo = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        fuente_texto = tkfont.Font(family="Segoe UI", size=14)

        titulo = mensaje.get("titulo") or TITULO_VENTANA
        tk.Label(
            marco,
            text=titulo,
            font=fuente_titulo,
            bg=colores["fondo"],
            fg=colores["texto"],
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 12))

        tk.Label(
            marco,
            text=mensaje.get("texto", ""),
            font=fuente_texto,
            bg=colores["fondo"],
            fg=colores["texto"],
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 20))

        def cerrar(mandar_visto: bool) -> None:
            if mandar_visto:
                self.cola_red.put({"tipo": "visto", "id": mensaje["id"]})
            if ventana in self._ventanas_abiertas:
                self._ventanas_abiertas.remove(ventana)
            ventana.destroy()

        pedir_visto = bool(mensaje.get("pedir_visto"))
        texto_boton = "Entendido" if pedir_visto else "Cerrar"
        tk.Button(
            marco,
            text=texto_boton,
            font=fuente_texto,
            command=lambda: cerrar(pedir_visto),
            padx=16,
            pady=6,
        ).pack(anchor=tk.E)

        ventana.update_idletasks()
        ancho = max(ventana.winfo_width(), 420)
        alto = ventana.winfo_height()
        pantalla_ancho = ventana.winfo_screenwidth()
        pantalla_alto = ventana.winfo_screenheight()
        x = (pantalla_ancho - ancho) // 2 + desplazamiento
        y = (pantalla_alto - alto) // 2 + desplazamiento
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

        ventana.bell()
        ventana.lift()
        ventana.focus_force()
        self._ventanas_abiertas.append(ventana)

    def iniciar(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar_ventana_raiz)
        self.root.mainloop()

    def _al_cerrar_ventana_raiz(self) -> None:
        if self.al_cerrar is not None:
            self.al_cerrar()
        self.root.quit()
