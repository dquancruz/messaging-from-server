"""Ventana de chat 1:1 del agente."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont
from agente.chat_util import (
    MARCA_ENVIANDO,
    confirmar_mensaje_en_historial,
    fusionar_historial_con_pendientes,
    indice_interlocutor,
    revertir_pendiente_en_historial,
)

LIMITE_TEXTO = 2000


class VentanaChat:
    """Interfaz para chatear con otros equipos conectados."""

    def __init__(
        self,
        root: tk.Tk,
        cola_red: queue.Queue,
        nombre_local: str,
    ) -> None:
        self.root = root
        self.cola_red = cola_red
        self.nombre_local = nombre_local.strip().lower()
        self._ventana: tk.Toplevel | None = None
        self._habilitado = True
        self._equipos: list[dict] = []
        self._interlocutor: str | None = None
        self._mensajes_por_interlocutor: dict[str, list[dict]] = {}
        self._lista_equipos: tk.Listbox | None = None
        self._historial: tk.Text | None = None
        self._entrada: tk.Text | None = None
        self._etiqueta_estado: tk.Label | None = None
        self._boton_enviar: tk.Button | None = None

    def abrir(self) -> None:
        if self._ventana is not None and self._ventana.winfo_exists():
            self._ventana.lift()
            self._ventana.focus_force()
            return

        ventana = tk.Toplevel(self.root)
        ventana.title("Chat — Cibercafé")
        ventana.geometry("720x520")
        ventana.minsize(560, 400)

        fuente = tkfont.Font(family="Segoe UI", size=12)
        fuente_historial = tkfont.Font(family="Segoe UI", size=11)

        marco = tk.Frame(ventana, padx=12, pady=12)
        marco.pack(fill=tk.BOTH, expand=True)

        self._etiqueta_estado = tk.Label(
            marco,
            text="",
            font=fuente,
            fg="#b45309",
            anchor=tk.W,
        )
        self._etiqueta_estado.pack(fill=tk.X, pady=(0, 8))

        cuerpo = tk.PanedWindow(marco, orient=tk.HORIZONTAL, sashwidth=4)
        cuerpo.pack(fill=tk.BOTH, expand=True)

        panel_izq = tk.Frame(cuerpo)
        tk.Label(panel_izq, text="Equipos conectados", font=fuente).pack(anchor=tk.W)
        self._lista_equipos = tk.Listbox(panel_izq, font=fuente, height=16, exportselection=False)
        self._lista_equipos.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self._lista_equipos.bind("<<ListboxSelect>>", self._al_seleccionar_equipo)
        cuerpo.add(panel_izq, minsize=180)

        panel_der = tk.Frame(cuerpo)
        tk.Label(panel_der, text="Conversación", font=fuente).pack(anchor=tk.W)
        self._historial = tk.Text(
            panel_der,
            font=fuente_historial,
            state=tk.DISABLED,
            wrap=tk.WORD,
            height=16,
        )
        self._historial.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        marco_entrada = tk.Frame(panel_der)
        marco_entrada.pack(fill=tk.X)
        self._entrada = tk.Text(marco_entrada, font=fuente, height=3, wrap=tk.WORD)
        self._entrada.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._entrada.bind("<Control-Return>", self._al_enviar)
        self._boton_enviar = tk.Button(
            marco_entrada,
            text="Enviar",
            font=fuente,
            command=self._al_enviar,
            padx=12,
        )
        self._boton_enviar.pack(side=tk.RIGHT, padx=(8, 0))
        cuerpo.add(panel_der, minsize=320)

        self._ventana = ventana
        self._actualizar_lista_equipos()
        self._actualizar_estado_ui()
        if self._interlocutor:
            self._mostrar_historial(self._interlocutor)

    def establecer_habilitado(self, habilitado: bool) -> None:
        self._habilitado = habilitado
        if habilitado:
            self._limpiar_error_envio()
        self._actualizar_estado_ui()

    def actualizar_equipos(self, equipos: list[dict]) -> None:
        self._equipos = [
            e
            for e in equipos
            if str(e.get("nombre", "")).strip().lower() != self.nombre_local
        ]
        self._actualizar_lista_equipos()

    def agregar_mensaje(self, mensaje: dict, propio: bool = False) -> None:
        interlocutor = mensaje.get("de") if not propio else mensaje.get("para")
        if not interlocutor:
            return
        clave = str(interlocutor).strip().lower()
        historial = self._mensajes_por_interlocutor.setdefault(clave, [])
        historial.append(mensaje)
        if self._ventana is not None and self._ventana.winfo_exists():
            if self._interlocutor == clave:
                self._mostrar_historial(clave)
            self._ventana.bell()

    def establecer_historial(self, interlocutor: str, mensajes: list[dict]) -> None:
        clave = interlocutor.strip().lower()
        local = self._mensajes_por_interlocutor.get(clave, [])
        self._mensajes_por_interlocutor[clave] = fusionar_historial_con_pendientes(
            mensajes, local, self.nombre_local
        )
        if self._interlocutor == clave:
            self._mostrar_historial(clave)

    def confirmar_mensaje(self, para: str, id_mensaje: str, cuando: str) -> bool:
        """Actualiza el último mensaje optimista con la confirmación del servidor."""
        clave = para.strip().lower()
        historial = self._mensajes_por_interlocutor.setdefault(clave, [])
        if not confirmar_mensaje_en_historial(
            historial, self.nombre_local, id_mensaje, cuando
        ):
            return False
        self._limpiar_error_envio()
        if self._interlocutor == clave:
            self._mostrar_historial(clave)
        return True

    def revertir_pendiente(self, motivo: str, para: str | None = None) -> bool:
        """Quita el último mensaje optimista y muestra el motivo del rechazo."""
        clave = (para or self._interlocutor or "").strip().lower()
        if not clave:
            return False
        historial = self._mensajes_por_interlocutor.setdefault(clave, [])
        if not revertir_pendiente_en_historial(historial, self.nombre_local):
            return False
        self._mostrar_error_envio(motivo)
        if self._interlocutor == clave:
            self._mostrar_historial(clave)
        return True

    def _actualizar_lista_equipos(self) -> None:
        if self._lista_equipos is None:
            return
        self._lista_equipos.delete(0, tk.END)
        for equipo in self._equipos:
            nombre = equipo.get("nombre", "")
            usuario = equipo.get("usuario", "")
            etiqueta = nombre
            if usuario:
                etiqueta += f" ({usuario})"
            if not equipo.get("conectado", False):
                etiqueta += " [desconectado]"
            self._lista_equipos.insert(tk.END, etiqueta)

        indice = indice_interlocutor(self._equipos, self._interlocutor)
        if indice is not None:
            self._lista_equipos.selection_set(indice)
            self._lista_equipos.see(indice)

    def _al_seleccionar_equipo(self, _evento: object) -> None:
        if self._lista_equipos is None:
            return
        seleccion = self._lista_equipos.curselection()
        if not seleccion:
            return
        indice = seleccion[0]
        if indice >= len(self._equipos):
            return
        interlocutor = str(self._equipos[indice].get("nombre", "")).strip().lower()
        self._interlocutor = interlocutor
        self.cola_red.put({"tipo": "chat_historial", "con": interlocutor, "ultimos": 50})
        self._mostrar_historial(interlocutor)

    def _mostrar_historial(self, interlocutor: str) -> None:
        if self._historial is None:
            return
        clave = interlocutor.strip().lower()
        mensajes = self._mensajes_por_interlocutor.get(clave, [])
        self._historial.configure(state=tk.NORMAL)
        self._historial.delete("1.0", tk.END)
        for mensaje in mensajes:
            de = mensaje.get("de", "")
            usuario = mensaje.get("de_usuario", "")
            texto = mensaje.get("texto", "")
            cuando = mensaje.get("cuando", "")
            etiqueta = de
            if usuario:
                etiqueta += f" ({usuario})"
            self._historial.insert(tk.END, f"[{cuando}] {etiqueta}:\n{texto}\n\n")
        self._historial.configure(state=tk.DISABLED)
        self._historial.see(tk.END)

    def _mostrar_error_envio(self, motivo: str) -> None:
        if self._etiqueta_estado is None:
            return
        texto = motivo.strip() if motivo else "No se pudo enviar el mensaje."
        self._etiqueta_estado.configure(text=texto)

    def _limpiar_error_envio(self) -> None:
        if self._etiqueta_estado is None:
            return
        if self._habilitado:
            self._etiqueta_estado.configure(text="")

    def _actualizar_estado_ui(self) -> None:
        if self._etiqueta_estado is None:
            return
        if not self._habilitado:
            self._etiqueta_estado.configure(
                text="El chat está desactivado por caja. No puedes enviar mensajes."
            )
        habilitar = self._habilitado
        if self._entrada is not None:
            self._entrada.configure(state=tk.NORMAL if habilitar else tk.DISABLED)
        if self._boton_enviar is not None:
            self._boton_enviar.configure(state=tk.NORMAL if habilitar else tk.DISABLED)

    def _al_enviar(self, _evento: object | None = None) -> None:
        if not self._habilitado or self._entrada is None:
            return "break"
        if not self._interlocutor:
            return "break"
        texto = self._entrada.get("1.0", tk.END).strip()
        if not texto or len(texto) > LIMITE_TEXTO:
            return "break"
        self.cola_red.put(
            {
                "tipo": "chat_enviar",
                "destino": self._interlocutor,
                "texto": texto,
            }
        )
        self.agregar_mensaje(
            {
                "de": self.nombre_local,
                "de_usuario": "",
                "para": self._interlocutor,
                "texto": texto,
                "cuando": MARCA_ENVIANDO,
            },
            propio=True,
        )
        self._entrada.delete("1.0", tk.END)
        return "break"


def crear_acceso_chat(root: tk.Misc, abrir) -> tk.Toplevel:
    """Botón flotante para abrir el chat (ventana propia, no en la raíz oculta)."""
    ventana = tk.Toplevel(root)
    ventana.title("")
    ventana.overrideredirect(True)
    ventana.attributes("-topmost", True)
    ventana.configure(bg="#2563eb")

    tk.Button(
        ventana,
        text="Chat",
        font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
        command=abrir,
        padx=10,
        pady=6,
        bg="#2563eb",
        fg="#ffffff",
        activebackground="#1d4ed8",
        activeforeground="#ffffff",
        relief=tk.FLAT,
        cursor="hand2",
        borderwidth=0,
        highlightthickness=0,
    ).pack()

    return ventana
