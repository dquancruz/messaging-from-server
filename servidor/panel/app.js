(function () {
  "use strict";

  var INTERVALO_ACTUALIZACION_MS = 2000;

  var iconosSO = {
    windows: "🪟",
    linux: "🐧",
    macos: "🍎"
  };

  var cuerpoEquipos = document.getElementById("cuerpo-equipos");
  var seleccionarTodos = document.getElementById("seleccionar-todos");
  var formMensaje = document.getElementById("form-mensaje");
  var campoTexto = document.getElementById("texto");
  var campoNivel = document.getElementById("nivel");
  var usarRespaldo = document.getElementById("usar-respaldo");
  var chatHabilitado = document.getElementById("chat-habilitado");
  var btnActualizar = document.getElementById("btn-actualizar-equipos");
  var btnEnviar = document.getElementById("btn-enviar");
  var seleccionContador = document.getElementById("seleccion-contador");
  var badgeSeleccion = document.getElementById("badge-seleccion");
  var textoActualizacion = document.getElementById("texto-actualizacion");
  var indicadorActualizacion = document.getElementById("indicador-actualizacion");
  var contenedorToasts = document.getElementById("contenedor-toasts");
  var statConectados = document.getElementById("stat-conectados");
  var statSesiones = document.getElementById("stat-sesiones");
  var statBloqueados = document.getElementById("stat-bloqueados");
  var statTotal = document.getElementById("stat-total");

  var equiposActuales = [];
  var actualizando = false;

  function formatearHora(iso) {
    if (!iso) {
      return "";
    }
    try {
      var fecha = new Date(iso);
      return fecha.toLocaleTimeString("es-MX", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
    } catch (e) {
      return iso;
    }
  }

  function formatearTiempo(segundos) {
    if (segundos === null || segundos === undefined) {
      return "—";
    }
    var minutos = Math.floor(segundos / 60);
    var segs = segundos % 60;
    return String(minutos).padStart(2, "0") + ":" + String(segs).padStart(2, "0");
  }

  function claseTiempo(segundos) {
    if (segundos === null || segundos === undefined) {
      return "";
    }
    if (segundos <= 0) {
      return "tiempo-agotado";
    }
    if (segundos < 300) {
      return "tiempo-bajo";
    }
    return "tiempo-ok";
  }

  function mostrarToast(mensaje, tipo) {
    var toast = document.createElement("div");
    toast.className = "toast " + (tipo || "info");
    toast.textContent = mensaje;
    contenedorToasts.appendChild(toast);
    setTimeout(function () {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      toast.style.transition = "opacity 0.3s, transform 0.3s";
      setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, 4000);
  }

  function actualizarEstadisticas(equipos) {
    var conectados = 0;
    var sesiones = 0;
    var bloqueados = 0;

    equipos.forEach(function (eq) {
      if (eq.conectado && !eq.sin_agente) {
        conectados += 1;
      }
      if (eq.tiempo_restante !== null && eq.tiempo_restante !== undefined && eq.tiempo_restante > 0) {
        sesiones += 1;
      }
      if (eq.bloqueado) {
        bloqueados += 1;
      }
    });

    statConectados.textContent = conectados;
    statSesiones.textContent = sesiones;
    statBloqueados.textContent = bloqueados;
    statTotal.textContent = equipos.length;
  }

  function marcarActualizacion(ok) {
    var ahora = new Date().toLocaleTimeString("es-MX", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
    textoActualizacion.textContent = ok ? "Actualizado " + ahora : "Error de conexión";
    indicadorActualizacion.classList.toggle("error", !ok);
  }

  function actualizarContadorSeleccion() {
    var n = obtenerSeleccionados().length;
    var texto = n === 0
      ? "Ningún equipo seleccionado"
      : n === 1
        ? "1 equipo seleccionado"
        : n + " equipos seleccionados";

    seleccionContador.textContent = texto;
    seleccionContador.classList.toggle("activa", n > 0);

    if (n > 0) {
      badgeSeleccion.textContent = n + " sel.";
      badgeSeleccion.hidden = false;
    } else {
      badgeSeleccion.hidden = true;
    }
  }

  function llamarApi(ruta, cuerpo) {
    return fetch(ruta, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo)
    }).then(function (resp) {
      return resp.json().then(function (datos) {
        if (!resp.ok) {
          throw new Error(datos.error || "Error en la petición");
        }
        return datos;
      });
    });
  }

  function accionSesion(equipo, accion, minutos) {
    var cuerpo = { equipo: equipo };
    var ruta;
    if (accion === "iniciar") {
      ruta = "/api/sesion/iniciar";
      cuerpo.minutos = minutos;
    } else if (accion === "extender") {
      ruta = "/api/sesion/extender";
      cuerpo.minutos = minutos;
    } else if (accion === "terminar") {
      ruta = "/api/sesion/terminar";
    } else if (accion === "desbloquear") {
      ruta = "/api/desbloquear";
    } else {
      return Promise.reject(new Error("acción desconocida"));
    }

    return llamarApi(ruta, cuerpo)
      .then(function () {
        mostrarToast("Sesión actualizada para " + equipo, "ok");
        return actualizarEquipos();
      })
      .catch(function (err) {
        mostrarToast(err.message, "error");
      });
  }

  function botonesSesion(eq) {
    if (!eq.conectado) {
      return '<span class="sesion-offline">Sin conexión</span>';
    }

    var nombre = eq.nombre;
    var bloqueado = eq.bloqueado;
    var html =
      '<div class="acciones-sesion">' +
      '<button type="button" class="btn-sesion" data-accion="iniciar" data-equipo="' +
      nombre +
      '" data-minutos="15">15′</button>' +
      '<button type="button" class="btn-sesion" data-accion="iniciar" data-equipo="' +
      nombre +
      '" data-minutos="30">30′</button>' +
      '<button type="button" class="btn-sesion" data-accion="iniciar" data-equipo="' +
      nombre +
      '" data-minutos="60">60′</button>' +
      '<button type="button" class="btn-sesion" data-accion="extender" data-equipo="' +
      nombre +
      '" data-minutos="15">+15′</button>' +
      '<button type="button" class="btn-sesion btn-terminar" data-accion="terminar" data-equipo="' +
      nombre +
      '">Fin</button>';

    if (bloqueado) {
      html +=
        '<button type="button" class="btn-sesion btn-desbloquear" data-accion="desbloquear" data-equipo="' +
        nombre +
        '">Desbloquear</button>';
    }

    html +=
      '<label class="minutos-libres">' +
      '<input type="number" min="1" max="480" value="20" class="input-minutos" data-equipo="' +
      nombre +
      '">' +
      '<button type="button" class="btn-sesion" data-accion="iniciar-libre" data-equipo="' +
      nombre +
      '">▶</button>' +
      "</label></div>";

    return html;
  }

  function sincronizarSeleccionarTodos() {
    var habilitados = document.querySelectorAll(".sel-equipo:not(:disabled)");
    var marcados = document.querySelectorAll(".sel-equipo:not(:disabled):checked");
    seleccionarTodos.checked = habilitados.length > 0 && habilitados.length === marcados.length;
    actualizarContadorSeleccion();
  }

  function resaltarFilasSeleccionadas() {
    document.querySelectorAll("#cuerpo-equipos tr").forEach(function (fila) {
      var cb = fila.querySelector(".sel-equipo");
      if (cb) {
        fila.classList.toggle("fila-seleccionada", cb.checked);
      }
    });
  }

  function renderizarEquipos(equipos) {
    var seleccionPrevios = new Set(obtenerSeleccionados());
    equiposActuales = equipos;
    actualizarEstadisticas(equipos);

    if (!equipos.length) {
      cuerpoEquipos.innerHTML =
        '<tr><td colspan="9" class="vacio">' +
        '<span class="vacio-icono" aria-hidden="true">🖥</span>' +
        "No hay equipos registrados todavía.</td></tr>";
      actualizarContadorSeleccion();
      return;
    }

    var filas = equipos.map(function (eq) {
      var icono = iconosSO[eq.so] || "💻";
      var usuarios = (eq.usuarios || []).join(", ") || "—";
      var sinAgente = !!eq.sin_agente;
      var claseFila = sinAgente ? "sin-agente" : (eq.conectado ? "" : "desconectado");
      var estado;
      if (sinAgente) {
        estado = '<span class="estado-badge sin-agente">Sin agente</span>';
      } else if (eq.bloqueado) {
        estado = '<span class="estado-badge bloqueado">Bloqueado</span>';
      } else if (eq.conectado) {
        estado = '<span class="estado-badge conectado">Conectado</span>';
      } else {
        estado = '<span class="estado-badge desconectado">Desconectado</span>';
      }

      var visto;
      if (eq.ultimo_visto) {
        visto = '<span class="visto-hora">✓ ' + formatearHora(eq.ultimo_visto) + "</span>";
      } else if (eq.ultimo_mensaje_id && eq.conectado) {
        visto = '<span class="visto-pendiente">Esperando…</span>';
      } else {
        visto = "—";
      }

      var seleccionable = eq.conectado || (sinAgente && usarRespaldo.checked);
      var deshabilitado = seleccionable ? "" : " disabled";
      var tiempo = formatearTiempo(eq.tiempo_restante);

      return (
        '<tr class="' + claseFila + '">' +
        '<td class="col-sel"><input type="checkbox" class="sel-equipo" data-nombre="' +
        eq.nombre +
        '"' +
        deshabilitado +
        "></td>" +
        '<td class="col-so"><span class="icono-so" title="' +
        eq.so +
        '">' +
        icono +
        "</span></td>" +
        '<td><span class="nombre-equipo">' +
        eq.nombre +
        "</span></td>" +
        "<td>" +
        usuarios +
        "</td>" +
        "<td>" +
        (eq.ip || "—") +
        "</td>" +
        '<td class="col-tiempo ' +
        claseTiempo(eq.tiempo_restante) +
        '">' +
        tiempo +
        "</td>" +
        "<td>" +
        estado +
        "</td>" +
        "<td>" +
        visto +
        "</td>" +
        '<td class="col-sesion">' +
        botonesSesion(eq) +
        "</td>" +
        "</tr>"
      );
    });

    cuerpoEquipos.innerHTML = filas.join("");

    document.querySelectorAll(".btn-sesion").forEach(function (boton) {
      boton.addEventListener("click", function () {
        var equipo = boton.getAttribute("data-equipo");
        var accion = boton.getAttribute("data-accion");
        var minutos = parseInt(boton.getAttribute("data-minutos") || "0", 10);
        if (accion === "iniciar-libre") {
          var input = document.querySelector('.input-minutos[data-equipo="' + equipo + '"]');
          minutos = parseInt(input.value, 10);
          if (!minutos || minutos <= 0) {
            mostrarToast("Indica minutos válidos.", "error");
            return;
          }
          accionSesion(equipo, "iniciar", minutos);
          return;
        }
        if (accion === "terminar" || accion === "desbloquear") {
          accionSesion(equipo, accion);
        } else {
          accionSesion(equipo, accion, minutos);
        }
      });
    });

    document.querySelectorAll(".sel-equipo").forEach(function (cb) {
      var nombre = cb.getAttribute("data-nombre");
      if (!cb.disabled && (seleccionPrevios.has(nombre) || seleccionarTodos.checked)) {
        cb.checked = true;
      }
      cb.addEventListener("change", function () {
        sincronizarSeleccionarTodos();
        resaltarFilasSeleccionadas();
      });
    });

    sincronizarSeleccionarTodos();
    resaltarFilasSeleccionadas();
  }

  function obtenerSeleccionados() {
    return Array.prototype.slice
      .call(document.querySelectorAll(".sel-equipo:checked"))
      .map(function (cb) {
        return cb.getAttribute("data-nombre");
      });
  }

  function actualizarEquipos() {
    if (actualizando) {
      return Promise.resolve();
    }
    actualizando = true;

    return fetch("/api/equipos")
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("No se pudo cargar la lista de equipos");
        }
        return resp.json();
      })
      .then(function (equipos) {
        renderizarEquipos(equipos);
        marcarActualizacion(true);
      })
      .catch(function (err) {
        cuerpoEquipos.innerHTML =
          '<tr><td colspan="9" class="vacio">' +
          '<span class="vacio-icono" aria-hidden="true">⚠</span>' +
          "Error al cargar equipos: " + err.message + "</td></tr>";
        marcarActualizacion(false);
      })
      .finally(function () {
        actualizando = false;
      });
  }

  function enviarMensaje(destinos, texto, nivel) {
    btnEnviar.disabled = true;

    return fetch("/api/mensaje", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        destinos: destinos,
        texto: texto,
        nivel: nivel,
        usar_respaldo: usarRespaldo.checked
      })
    })
      .then(function (resp) {
        return resp.json().then(function (datos) {
          if (!resp.ok) {
            throw new Error(datos.error || "Error al enviar");
          }
          return datos;
        });
      })
      .then(function (datos) {
        var textoEstado =
          "Enviado a " + datos.enviados + " equipo(s): " + (datos.equipos || []).join(", ");
        if (datos.respaldo && datos.respaldo.length) {
          var okRespaldo = datos.respaldo.filter(function (r) { return r.ok; });
          var falloRespaldo = datos.respaldo.filter(function (r) { return !r.ok; });
          if (okRespaldo.length) {
            textoEstado += ". Respaldo OK: " + okRespaldo.map(function (r) { return r.equipo; }).join(", ");
          }
          if (falloRespaldo.length) {
            textoEstado += ". Respaldo falló: " + falloRespaldo.map(function (r) { return r.equipo; }).join(", ");
          }
        }
        mostrarToast(textoEstado, "ok");
        return actualizarEquipos();
      })
      .catch(function (err) {
        mostrarToast(err.message, "error");
      })
      .finally(function () {
        btnEnviar.disabled = false;
      });
  }

  seleccionarTodos.addEventListener("change", function () {
    document.querySelectorAll(".sel-equipo:not(:disabled)").forEach(function (cb) {
      cb.checked = seleccionarTodos.checked;
    });
    sincronizarSeleccionarTodos();
    resaltarFilasSeleccionadas();
  });

  usarRespaldo.addEventListener("change", function () {
    renderizarEquipos(equiposActuales);
  });

  document.querySelectorAll(".atajo").forEach(function (boton) {
    boton.addEventListener("click", function () {
      campoTexto.value = boton.getAttribute("data-texto");
      campoNivel.value = boton.getAttribute("data-nivel");
      campoTexto.focus();
    });
  });

  formMensaje.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var seleccionados = obtenerSeleccionados();
    if (!seleccionados.length) {
      mostrarToast(
        usarRespaldo.checked
          ? "Selecciona al menos un equipo conectado o sin agente."
          : "Selecciona al menos un equipo conectado.",
        "error"
      );
      return;
    }
    enviarMensaje(seleccionados, campoTexto.value.trim(), campoNivel.value);
  });

  function actualizarEstadoChat() {
    fetch("/api/chat/estado")
      .then(function (resp) { return resp.json(); })
      .then(function (datos) {
        chatHabilitado.checked = !!datos.habilitado;
      })
      .catch(function () {
        /* ignorar si el servidor aún no tiene chat */
      });
  }

  chatHabilitado.addEventListener("change", function () {
    var deseado = chatHabilitado.checked;
    fetch("/api/chat/habilitar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ habilitado: deseado })
    })
      .then(function (resp) {
        return resp.json().then(function (datos) {
          if (!resp.ok) {
            throw new Error(datos.error || "Error al cambiar el chat");
          }
          return datos;
        });
      })
      .then(function (datos) {
        chatHabilitado.checked = !!datos.habilitado;
        mostrarToast(
          datos.habilitado ? "Chat entre clientes activado" : "Chat entre clientes desactivado",
          "ok"
        );
      })
      .catch(function () {
        chatHabilitado.checked = !deseado;
        mostrarToast("No se pudo cambiar el estado del chat", "error");
      });
  });

  btnActualizar.addEventListener("click", function () {
    btnActualizar.disabled = true;
    actualizarEquipos().finally(function () {
      btnActualizar.disabled = false;
    });
  });

  actualizarEquipos();
  actualizarEstadoChat();
  setInterval(actualizarEquipos, INTERVALO_ACTUALIZACION_MS);
})();
