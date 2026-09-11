(function () {
  "use strict";

  var INTERVALO_MS = 2000;
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
  var estadoEnvio = document.getElementById("estado-envio");
  var usarRespaldo = document.getElementById("usar-respaldo");
  var chatHabilitado = document.getElementById("chat-habilitado");
  var equiposActuales = [];

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

    estadoEnvio.textContent = "Procesando sesión…";
    estadoEnvio.className = "estado-envio";
    return llamarApi(ruta, cuerpo)
      .then(function () {
        estadoEnvio.textContent = "Sesión actualizada para " + equipo;
        estadoEnvio.className = "estado-envio ok";
        actualizarEquipos();
      })
      .catch(function (err) {
        estadoEnvio.textContent = err.message;
        estadoEnvio.className = "estado-envio error";
      });
  }

  function botonesSesion(eq) {
    if (!eq.conectado) {
      return '<span class="sesion-offline">—</span>';
    }

    var nombre = eq.nombre;
    var bloqueado = eq.bloqueado;
    var html =
      '<div class="acciones-sesion">' +
      '<button type="button" class="btn-sesion" data-accion="iniciar" data-equipo="' +
      nombre +
      '" data-minutos="15">15 min</button>' +
      '<button type="button" class="btn-sesion" data-accion="iniciar" data-equipo="' +
      nombre +
      '" data-minutos="30">30 min</button>' +
      '<button type="button" class="btn-sesion" data-accion="iniciar" data-equipo="' +
      nombre +
      '" data-minutos="60">60 min</button>' +
      '<button type="button" class="btn-sesion" data-accion="extender" data-equipo="' +
      nombre +
      '" data-minutos="15">+15 min</button>' +
      '<button type="button" class="btn-sesion btn-terminar" data-accion="terminar" data-equipo="' +
      nombre +
      '">Terminar</button>';

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
      '">Iniciar</button>' +
      "</label></div>";

    return html;
  }

  function renderizarEquipos(equipos) {
    var seleccionPrevios = {};
    document.querySelectorAll(".sel-equipo:checked").forEach(function (cb) {
      seleccionPrevios[cb.getAttribute("data-nombre")] = true;
    });

    equiposActuales = equipos;
    if (!equipos.length) {
      cuerpoEquipos.innerHTML =
        '<tr><td colspan="9" class="vacio">No hay equipos registrados todavía.</td></tr>';
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
        visto = '<span class="visto-hora">' + formatearHora(eq.ultimo_visto) + "</span>";
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
        "<td><strong>" +
        eq.nombre +
        "</strong></td>" +
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
            estadoEnvio.textContent = "Indica minutos válidos.";
            estadoEnvio.className = "estado-envio error";
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

    document.querySelectorAll(".sel-equipo:not(:disabled)").forEach(function (cb) {
      var nombre = cb.getAttribute("data-nombre");
      cb.checked = seleccionarTodos.checked || !!seleccionPrevios[nombre];
    });
  }

  function obtenerSeleccionados() {
    return Array.prototype.slice
      .call(document.querySelectorAll(".sel-equipo:checked"))
      .map(function (cb) {
        return cb.getAttribute("data-nombre");
      });
  }

  function actualizarEquipos() {
    fetch("/api/equipos")
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("No se pudo cargar la lista de equipos");
        }
        return resp.json();
      })
      .then(renderizarEquipos)
      .catch(function (err) {
        cuerpoEquipos.innerHTML =
          '<tr><td colspan="9" class="vacio">Error al cargar equipos: ' +
          err.message +
          "</td></tr>";
      });
  }

  function enviarMensaje(destinos, texto, nivel) {
    estadoEnvio.textContent = "Enviando…";
    estadoEnvio.className = "estado-envio";

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
        estadoEnvio.textContent = textoEstado;
        estadoEnvio.className = "estado-envio ok";
        actualizarEquipos();
      })
      .catch(function (err) {
        estadoEnvio.textContent = err.message;
        estadoEnvio.className = "estado-envio error";
      });
  }

  seleccionarTodos.addEventListener("change", function () {
    document.querySelectorAll(".sel-equipo:not(:disabled)").forEach(function (cb) {
      cb.checked = seleccionarTodos.checked;
    });
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
      estadoEnvio.textContent = usarRespaldo.checked
        ? "Selecciona al menos un equipo conectado o sin agente."
        : "Selecciona al menos un equipo conectado.";
      estadoEnvio.className = "estado-envio error";
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
      })
      .catch(function () {
        chatHabilitado.checked = !deseado;
      });
  });

  actualizarEquipos();
  actualizarEstadoChat();
  setInterval(actualizarEquipos, INTERVALO_MS);
})();
