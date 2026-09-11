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

  function renderizarEquipos(equipos) {
    equiposActuales = equipos;
    if (!equipos.length) {
      cuerpoEquipos.innerHTML =
        '<tr><td colspan="7" class="vacio">No hay equipos registrados todavía.</td></tr>';
      return;
    }

    var filas = equipos.map(function (eq) {
      var icono = iconosSO[eq.so] || "💻";
      var usuarios = (eq.usuarios || []).join(", ") || "—";
      var claseFila = eq.conectado ? "" : "desconectado";
      var estado = eq.conectado
        ? '<span class="estado-badge conectado">Conectado</span>'
        : '<span class="estado-badge desconectado">Desconectado</span>';

      var visto;
      if (eq.ultimo_visto) {
        visto = '<span class="visto-hora">' + formatearHora(eq.ultimo_visto) + "</span>";
      } else if (eq.ultimo_mensaje_id && eq.conectado) {
        visto = '<span class="visto-pendiente">Esperando…</span>';
      } else {
        visto = "—";
      }

      var deshabilitado = eq.conectado ? "" : " disabled";

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
        "<td>" +
        estado +
        "</td>" +
        "<td>" +
        visto +
        "</td>" +
        "</tr>"
      );
    });

    cuerpoEquipos.innerHTML = filas.join("");

    if (seleccionarTodos.checked) {
      document.querySelectorAll(".sel-equipo:not(:disabled)").forEach(function (cb) {
        cb.checked = true;
      });
    }
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
          '<tr><td colspan="7" class="vacio">Error al cargar equipos: ' +
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
      body: JSON.stringify({ destinos: destinos, texto: texto, nivel: nivel })
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
        estadoEnvio.textContent =
          "Enviado a " + datos.enviados + " equipo(s): " + (datos.equipos || []).join(", ");
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
      estadoEnvio.textContent = "Selecciona al menos un equipo conectado.";
      estadoEnvio.className = "estado-envio error";
      return;
    }
    enviarMensaje(seleccionados, campoTexto.value.trim(), campoNivel.value);
  });

  actualizarEquipos();
  setInterval(actualizarEquipos, INTERVALO_MS);
})();
