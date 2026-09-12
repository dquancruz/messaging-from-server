/* Utilidades compartidas entre panel de caja y moderación */
var PanelComun = (function () {
  "use strict";

  function crearIndicadorActualizacion(textoEl, indicadorEl) {
    return {
      marcar: function (ok) {
        var ahora = new Date().toLocaleTimeString("es-MX", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        });
        textoEl.textContent = ok ? "Actualizado " + ahora : "Error de conexión";
        if (indicadorEl) {
          indicadorEl.classList.toggle("error", !ok);
        }
      }
    };
  }

  return {
    crearIndicadorActualizacion: crearIndicadorActualizacion
  };
})();
