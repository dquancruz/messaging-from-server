#!/bin/bash
# Instala el agente de Ciber Mensajería en macOS.
#
# Uso:
#   sudo ./instalar-agente.sh --token EL_TOKEN_DEL_SERVIDOR

set -euo pipefail

TOKEN=""
SERVIDOR="dc01.lab.lan"
RESPALDO="192.168.1.10"

log() {
    echo "==> $*"
}

error() {
    echo "ERROR: $*" >&2
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --token)
            TOKEN="${2:-}"
            shift 2
            ;;
        --servidor)
            SERVIDOR="${2:-}"
            shift 2
            ;;
        --respaldo)
            RESPALDO="${2:-}"
            shift 2
            ;;
        -h|--help)
            sed -n '2,5p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *)
            error "opción desconocida: $1"
            ;;
    esac
done

if [ -z "$TOKEN" ]; then
    error "falta --token"
fi

if [ "$(id -u)" -ne 0 ]; then
    error "ejecute como root: sudo $0 --token ..."
fi

RAIZ_PROYECTO="$(cd "$(dirname "$0")/../.." && pwd)"
DESTINO="/Library/Application Support/CiberMensajeria"
CONFIG="$DESTINO/agente.json"
PLANTILLA="$(dirname "$0")/lab.ciber.agente.plist"
PLIST="/Library/LaunchAgents/lab.ciber.agente.plist"

log "Paso 1/4: verificar Python 3.10+ con tkinter"
PYTHON3="$(command -v python3 || true)"
if [ -z "$PYTHON3" ]; then
    error "no se encontró python3. Instale Python desde https://www.python.org/downloads/"
fi

VERSION="$("$PYTHON3" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
MAYOR="$(echo "$VERSION" | cut -d. -f1)"
MENOR="$(echo "$VERSION" | cut -d. -f2)"
if [ "$MAYOR" -lt 3 ] || { [ "$MAYOR" -eq 3 ] && [ "$MENOR" -lt 10 ]; }; then
    error "se requiere Python 3.10 o superior (encontrado: $VERSION)"
fi

if ! "$PYTHON3" -c "import tkinter" 2>/dev/null; then
    error "tkinter no está disponible. Use el instalador de python.org (el Python de Apple suele traer Tk viejo)."
fi

log "Paso 2/4: copiar archivos a $DESTINO"
install -d -m 755 "$DESTINO"
install -d -m 755 "$DESTINO/agente" "$DESTINO/comun"
install -m 644 "$RAIZ_PROYECTO/agente/"*.py "$DESTINO/agente/"
install -m 644 "$RAIZ_PROYECTO/comun/"*.py "$DESTINO/comun/"

log "Paso 3/4: crear configuración"
cat >"$CONFIG" <<EOF
{
  "servidor": "$SERVIDOR",
  "servidor_respaldo": "$RESPALDO",
  "puerto": 5050,
  "token": "$TOKEN",
  "bloqueo_nativo": false
}
EOF
chmod 644 "$CONFIG"

log "Paso 4/4: instalar LaunchAgent"
install -d -m 755 /Library/LaunchAgents
sed "s|__PYTHON3__|$PYTHON3|g" "$PLANTILLA" >"$PLIST"
chmod 644 "$PLIST"

USUARIO_GUI="${SUDO_USER:-$USER}"
UID_GUI="$(id -u "$USUARIO_GUI")"
launchctl bootout "gui/$UID_GUI" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$UID_GUI" "$PLIST"
launchctl enable "gui/$UID_GUI/lab.ciber.agente" 2>/dev/null || true

echo
echo "Instalación completada."
echo "  Archivos: $DESTINO"
echo "  Config:   $CONFIG"
echo "  Python:   $PYTHON3 ($VERSION)"
echo
echo "El agente arrancará al iniciar sesión del usuario $USUARIO_GUI."
