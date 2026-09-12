"""Ventanas del agente: emergentes, contador y pantalla de bloqueo."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from agente.chat import VentanaChat, crear_acceso_chat
from agente.plataforma import bloquear_sistema_nativo, nombre_equipo

registrador = logging.getLogger("agente.ventanas")

TITULO_VENTANA = "Cibercafé"
INTERVALO_COLA_MS = 200
DESPLAZAMIENTO_APILADO = 24
INTERVALO_BLOQUEO_MS = 1000
UMBRAL_ALERTA_SEGUNDOS = 5 * 60

COLORES_NIVEL = {
    "info": {"fondo": "#1565C0", "texto": "#FFFFFF"},
    "aviso": {"fondo": "#F9A825", "texto": "#212121"},
    "critico": {"fondo": "#C62828", "texto": "#FFFFFF"},
}


def _formatear_tiempo(segundos: int) -> str:
    minutos, segs = divmod(max(0, segundos), 60)
    return f"{minutos:02d}:{segs:02d}"


class GestorVentanas:
    """Muestra avisos, contador y bloqueo sin frenar el hilo de red."""

    def __init__(
        self,
        root: tk.Tk,
        cola_ui: queue.Queue,
        cola_red: queue.Queue,
        config: dict | None = None,
        al_cerrar: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.cola_ui = cola_ui
        self.cola_red = cola_red
        self.config = config or {}
        self.al_cerrar = al_cerrar
        self._ventanas_abiertas: list[tk.Toplevel] = []
        self._contador: tk.Toplevel | None = None
        self._etiqueta_contador: tk.Label | None = None
        self._bloqueo: tk.Toplevel | None = None
        self._texto_bloqueo = "Tu tiempo terminó, pasa a caja."
        self._restante_sesion: int | None = None
        self._chat = VentanaChat(root, cola_red, nombre_equipo())
        self._acceso_chat = crear_acceso_chat(root, self._chat.abrir)
        self._posicionar_acceso_chat()
        self.root.bind("<Control-Shift-C>", lambda _e: self._chat.abrir())
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
        elif tipo == "sesion":
            self._actualizar_contador(evento.get("restante"))
        elif tipo == "bloquear":
            texto = evento.get("texto")
            if texto:
                self._texto_bloqueo = texto
            self._mostrar_bloqueo()
        elif tipo == "desbloquear":
            self._ocultar_bloqueo()
        elif tipo == "chat_estado":
            self._chat.establecer_habilitado(bool(evento.get("habilitado")))
        elif tipo == "chat_lista":
            self._chat.actualizar_equipos(evento.get("equipos", []))
        elif tipo == "chat_recibido":
            self._chat.agregar_mensaje(evento.get("mensaje", {}), propio=False)
        elif tipo == "chat_enviado":
            self._chat.confirmar_mensaje(
                str(evento.get("para", "")),
                str(evento.get("id", "")),
                str(evento.get("cuando", "")),
            )
        elif tipo == "chat_rechazado":
            motivo = str(evento.get("motivo", "No se pudo enviar el mensaje."))
            registrador.warning("chat rechazado: %s", motivo)
            self._chat.revertir_pendiente(motivo)
        elif tipo == "chat_historial_respuesta":
            self._chat.establecer_historial(
                str(evento.get("con", "")),
                evento.get("mensajes", []),
            )
        elif tipo == "cerrar":
            self.root.quit()

    def _actualizar_contador(self, restante: int | None) -> None:
        self._restante_sesion = restante
        if restante is None:
            self._ocultar_contador()
            return

        if self._contador is None:
            self._crear_contador()

        texto = f"⏱ {_formatear_tiempo(restante)}"
        color_fondo = "#C62828" if restante < UMBRAL_ALERTA_SEGUNDOS else "#1e293b"
        self._contador.configure(bg=color_fondo)
        if self._etiqueta_contador is not None:
            self._etiqueta_contador.configure(text=texto, bg=color_fondo)
        self._contador.lift()

    def _crear_contador(self) -> None:
        ventana = tk.Toplevel(self.root)
        ventana.title("")
        ventana.overrideredirect(True)
        ventana.attributes("-topmost", True)
        ventana.configure(bg="#1e293b")

        fuente = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        etiqueta = tk.Label(
            ventana,
            text="⏱ 00:00",
            font=fuente,
            bg="#1e293b",
            fg="#FFFFFF",
            padx=16,
            pady=10,
        )
        etiqueta.pack()
        self._contador = ventana
        self._etiqueta_contador = etiqueta
        self._posicionar_contador()

    def _posicionar_acceso_chat(self) -> None:
        ventana = self._acceso_chat
        ventana.update_idletasks()
        alto = ventana.winfo_height()
        if alto <= 1:
            self.root.after(100, self._posicionar_acceso_chat)
            return
        margen = 16
        x = margen
        y = ventana.winfo_screenheight() - alto - margen - 48
        ventana.geometry(f"+{x}+{y}")
        ventana.deiconify()
        ventana.lift()

    def _posicionar_contador(self) -> None:
        if self._contador is None:
            return
        self._contador.update_idletasks()
        ancho = self._contador.winfo_width()
        alto = self._contador.winfo_height()
        margen = 16
        x = self._contador.winfo_screenwidth() - ancho - margen
        y = self._contador.winfo_screenheight() - alto - margen - 48
        self._contador.geometry(f"+{x}+{y}")

    def _ocultar_contador(self) -> None:
        if self._contador is not None:
            self._contador.destroy()
            self._contador = None
            self._etiqueta_contador = None

    def _mostrar_bloqueo(self) -> None:
        self._ocultar_contador()
        if self.config.get("bloqueo_nativo"):
            bloquear_sistema_nativo()

        if self._bloqueo is not None:
            self._actualizar_texto_bloqueo()
            self._bloqueo.lift()
            return

        ventana = tk.Toplevel(self.root)
        ventana.title("")
        ventana.overrideredirect(True)
        ventana.attributes("-topmost", True)
        ventana.configure(bg="#111827")
        ventana.geometry(
            f"{ventana.winfo_screenwidth()}x{ventana.winfo_screenheight()}+0+0"
        )

        fuente_titulo = tkfont.Font(family="Segoe UI", size=36, weight="bold")
        fuente_texto = tkfont.Font(family="Segoe UI", size=22)
        fuente_equipo = tkfont.Font(family="Segoe UI", size=16)

        marco = tk.Frame(ventana, bg="#111827")
        marco.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(
            marco,
            text="Cibercafé",
            font=fuente_titulo,
            bg="#111827",
            fg="#FFFFFF",
        ).pack(pady=(0, 24))

        self._etiqueta_bloqueo = tk.Label(
            marco,
            text=self._texto_bloqueo,
            font=fuente_texto,
            bg="#111827",
            fg="#F9FAFB",
            wraplength=700,
            justify=tk.CENTER,
        )
        self._etiqueta_bloqueo.pack(pady=(0, 16))

        tk.Label(
            marco,
            text=nombre_equipo(),
            font=fuente_equipo,
            bg="#111827",
            fg="#9CA3AF",
        ).pack()

        ventana.protocol("WM_DELETE_WINDOW", lambda: None)
        self._bloqueo = ventana
        self._mantener_bloqueo_arriba()

    def _actualizar_texto_bloqueo(self) -> None:
        if self._bloqueo is None:
            return
        for widget in self._bloqueo.winfo_children():
            for hijo in widget.winfo_children():
                if isinstance(hijo, tk.Label) and hijo.cget("font"):
                    fuente = tkfont.Font(font=hijo.cget("font"))
                    if fuente.cget("size") == 22:
                        hijo.configure(text=self._texto_bloqueo)

    def _mantener_bloqueo_arriba(self) -> None:
        if self._bloqueo is None:
            return
        self._bloqueo.lift()
        self._bloqueo.attributes("-topmost", True)
        self._bloqueo.after(INTERVALO_BLOQUEO_MS, self._mantener_bloqueo_arriba)

    def _ocultar_bloqueo(self) -> None:
        if self._bloqueo is not None:
            self._bloqueo.destroy()
            self._bloqueo = None

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
