(function () {
  "use strict";

  var INTERVALO_MS = 5000;
  var cuerpoConversaciones = document.getElementById("cuerpo-conversaciones");
  var listaMensajes = document.getElementById("lista-mensajes");
  var etiquetaConversacion = document.getElementById("etiqueta-conversacion");
  var conversacionActiva = null;

  function formatearHora(iso) {
    if (!iso) {
      return "—";
    }
    try {
      return new Date(iso).toLocaleTimeString("es-MX", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
    } catch (e) {
      return iso;
    }
  }

  function renderizarConversaciones(conversaciones) {
    if (!conversaciones.length) {
      cuerpoConversaciones.innerHTML =
        '<tr><td colspan="3" class="vacio">No hay conversaciones</td></tr>';
      return;
    }

    cuerpoConversaciones.innerHTML = conversaciones
      .map(function (c) {
        var activa =
          conversacionActiva &&
          conversacionActiva.equipo_a === c.equipo_a &&
          conversacionActiva.equipo_b === c.equipo_b;
        return (
          '<tr class="fila-seleccionable' +
          (activa ? " activa" : "") +
          '" data-a="' +
          c.equipo_a +
          '" data-b="' +
          c.equipo_b +
          '">' +
          "<td>" +
          c.equipo_a +
          " ↔ " +
          c.equipo_b +
          "</td>" +
          "<td>" +
          c.mensajes +
          "</td>" +
          "<td>" +
          formatearHora(c.ultimo_cuando) +
          "</td>" +
          "</tr>"
        );
      })
      .join("");

    cuerpoConversaciones.querySelectorAll(".fila-seleccionable").forEach(function (fila) {
      fila.addEventListener("click", function () {
        conversacionActiva = {
          equipo_a: fila.getAttribute("data-a"),
          equipo_b: fila.getAttribute("data-b")
        };
        etiquetaConversacion.textContent =
          conversacionActiva.equipo_a + " ↔ " + conversacionActiva.equipo_b;
        cargarMensajes();
        actualizarConversaciones();
      });
    });
  }

  function renderizarMensajes(mensajes) {
    if (!mensajes.length) {
      listaMensajes.innerHTML = '<p class="vacio">Sin mensajes en esta conversación</p>';
      return;
    }

    listaMensajes.innerHTML = mensajes
      .map(function (m) {
        return (
          '<article class="mensaje">' +
          '<div class="meta">' +
          formatearHora(m.cuando) +
          " — " +
          m.de +
          (m.de_usuario ? " (" + m.de_usuario + ")" : "") +
          "</div>" +
          '<div class="texto"></div>' +
          "</article>"
        );
      })
      .join("");

    listaMensajes.querySelectorAll(".mensaje").forEach(function (nodo, indice) {
      nodo.querySelector(".texto").textContent = mensajes[indice].texto;
    });
    listaMensajes.scrollTop = listaMensajes.scrollHeight;
  }

  function actualizarConversaciones() {
    fetch("/api/moderacion/conversaciones")
      .then(function (resp) {
        return resp.json();
      })
      .then(renderizarConversaciones)
      .catch(function () {
        cuerpoConversaciones.innerHTML =
          '<tr><td colspan="3" class="vacio">Error al cargar conversaciones</td></tr>';
      });
  }

  function cargarMensajes() {
    if (!conversacionActiva) {
      return;
    }
    var url =
      "/api/moderacion/mensajes?de=" +
      encodeURIComponent(conversacionActiva.equipo_a) +
      "&para=" +
      encodeURIComponent(conversacionActiva.equipo_b) +
      "&ultimos=100";
    fetch(url)
      .then(function (resp) {
        return resp.json();
      })
      .then(renderizarMensajes)
      .catch(function () {
        listaMensajes.innerHTML = '<p class="vacio">Error al cargar mensajes</p>';
      });
  }

  actualizarConversaciones();
  setInterval(function () {
    actualizarConversaciones();
    if (conversacionActiva) {
      cargarMensajes();
    }
  }, INTERVALO_MS);
})();
