#!/bin/bash
# Desinstala el agente de Ciber Mensajería en macOS.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: ejecute como root: sudo $0" >&2
    exit 1
fi

PLIST="/Library/LaunchAgents/lab.ciber.agente.plist"
DESTINO="/Library/Application Support/CiberMensajeria"

echo "==> Deteniendo LaunchAgent"
USUARIO_GUI="${SUDO_USER:-$USER}"
UID_GUI="$(id -u "$USUARIO_GUI")"
launchctl bootout "gui/$UID_GUI" "$PLIST" 2>/dev/null || true

echo "==> Eliminando archivos"
rm -f "$PLIST"
rm -rf "$DESTINO"

echo
echo "Desinstalación completada."
