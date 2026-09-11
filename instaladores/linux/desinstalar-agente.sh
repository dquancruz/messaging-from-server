#!/bin/bash
# Desinstala el agente de Ciber Mensajería en Linux.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: ejecute como root: sudo $0" >&2
    exit 1
fi

echo "==> Deteniendo servicio systemd (si existe)"
if systemctl is-active ciber-agente.service >/dev/null 2>&1; then
    systemctl disable --now ciber-agente.service
fi
rm -f /etc/systemd/system/ciber-agente.service
systemctl daemon-reload 2>/dev/null || true

echo "==> Quitando autostart gráfico"
rm -f /etc/xdg/autostart/ciber-agente.desktop

echo "==> Eliminando archivos instalados"
rm -rf /opt/ciber-mensajeria
rm -rf /etc/ciber-mensajeria

echo
echo "Desinstalación completada."
echo "Los logs de usuario en ~/.local/state/ciber-agente no se borran."
