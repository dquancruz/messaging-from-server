#!/bin/bash
# Instala el agente de Ciber Mensajería en Ubuntu/Debian.
#
# Uso (como root):
#   sudo ./instalar-agente.sh
#   sudo ./instalar-agente.sh --token OTRO_TOKEN
#
# Opciones:
#   --token TOKEN     Token compartido con el servidor (por defecto: agente/config.json)
#   --servidor HOST   Nombre del servidor (por defecto: dc01.lab.lan)
#   --respaldo IP     IP de respaldo (por defecto: 192.168.1.10)
#   --modo grafico    Forzar instalación con ventanas (autostart)
#   --modo consola    Forzar instalación sin escritorio (systemd + wall)

set -euo pipefail

TOKEN=""
SERVIDOR="dc01.lab.lan"
RESPALDO="192.168.1.10"
MODO=""

log() {
    echo "==> $*"
}

error() {
    echo "ERROR: $*" >&2
    exit 1
}

uso() {
    sed -n '2,12p' "$0" | sed 's/^# //'
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
        --modo)
            MODO="${2:-}"
            shift 2
            ;;
        -h|--help)
            uso
            ;;
        *)
            error "opción desconocida: $1 (use --help)"
            ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    error "ejecute este script como root: sudo $0"
fi

RAIZ_PROYECTO="$(cd "$(dirname "$0")/../.." && pwd)"

if [ -z "$TOKEN" ]; then
    CONFIG_AGENTE_ORIGEN="$RAIZ_PROYECTO/agente/config.json"
    if [ ! -f "$CONFIG_AGENTE_ORIGEN" ]; then
        error "falta --token y no se encontró $CONFIG_AGENTE_ORIGEN"
    fi
    TOKEN=$(python3 -c "import json; print(json.load(open('$CONFIG_AGENTE_ORIGEN'))['token'])")
    log "Usando token del repositorio: $TOKEN"
fi
DESTINO="/opt/ciber-mensajeria"
CONFIG_DIR="/etc/ciber-mensajeria"
CONFIG="$CONFIG_DIR/agente.json"
AUTOSTART="/etc/xdg/autostart/ciber-agente.desktop"
SERVICIO="/etc/systemd/system/ciber-agente.service"

tiene_escritorio() {
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        return 0
    fi
    if command -v dpkg >/dev/null 2>&1; then
        if dpkg -l 2>/dev/null | grep -qE 'ubuntu-desktop|gnome-shell|xfce4|plasma-desktop|lxde|mate-desktop'; then
            return 0
        fi
    fi
    return 1
}

elegir_modo() {
    case "$MODO" in
        grafico|consola)
            echo "$MODO"
            return
            ;;
        "")
            ;;
        *)
            error "--modo debe ser 'grafico' o 'consola'"
            ;;
    esac

    if tiene_escritorio; then
        echo "grafico"
    else
        echo "consola"
    fi
}

MODO_INSTALACION="$(elegir_modo)"

log "Paso 1/5: instalar dependencias del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
if [ "$MODO_INSTALACION" = "grafico" ]; then
    apt-get install -y python3 python3-tk
else
    apt-get install -y python3
fi

log "Paso 2/5: copiar archivos a $DESTINO"
install -d -m 755 "$DESTINO"
install -d -m 755 "$DESTINO/agente" "$DESTINO/comun"
install -m 644 "$RAIZ_PROYECTO/agente/"*.py "$DESTINO/agente/"
install -m 644 "$RAIZ_PROYECTO/comun/"*.py "$DESTINO/comun/"

cat >"$DESTINO/ejecutar-agente.sh" <<'EOF'
#!/bin/sh
cd /opt/ciber-mensajeria
export PYTHONPATH=/opt/ciber-mensajeria
exec python3 -m agente --config /etc/ciber-mensajeria/agente.json
EOF
chmod 755 "$DESTINO/ejecutar-agente.sh"

cat >"$DESTINO/ejecutar-agente-consola.sh" <<'EOF'
#!/bin/sh
cd /opt/ciber-mensajeria
export PYTHONPATH=/opt/ciber-mensajeria
exec python3 -m agente.consola --config /etc/ciber-mensajeria/agente.json
EOF
chmod 755 "$DESTINO/ejecutar-agente-consola.sh"

log "Paso 3/5: crear configuración en $CONFIG"
install -d -m 755 "$CONFIG_DIR"
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

log "Paso 4/5: configurar arranque automático (modo: $MODO_INSTALACION)"
if [ "$MODO_INSTALACION" = "grafico" ]; then
    install -d -m 755 /etc/xdg/autostart
    install -m 644 "$(dirname "$0")/ciber-agente.desktop" "$AUTOSTART"
    if systemctl is-enabled ciber-agente.service >/dev/null 2>&1; then
        systemctl disable --now ciber-agente.service || true
        rm -f "$SERVICIO"
        systemctl daemon-reload || true
    fi
else
    rm -f "$AUTOSTART"
    cat >"$SERVICIO" <<EOF
[Unit]
Description=Agente Ciber Mensajería (modo consola)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$DESTINO/ejecutar-agente-consola.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now ciber-agente.service
fi

log "Paso 5/5: iniciar agente para la sesión actual (si hay escritorio)"
if [ "$MODO_INSTALACION" = "grafico" ]; then
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        if command -v runuser >/dev/null 2>&1 && [ -n "${SUDO_USER:-}" ]; then
            runuser -u "$SUDO_USER" -- "$DESTINO/ejecutar-agente.sh" &
            log "Agente iniciado en segundo plano para el usuario $SUDO_USER"
        else
            log "Inicie sesión de nuevo o ejecute: $DESTINO/ejecutar-agente.sh"
        fi
    else
        log "El autostart se aplicará al iniciar sesión gráfica de cada usuario"
    fi
    echo
    echo "Nota sobre Wayland: en Ubuntu con Wayland, tkinter usa XWayland."
    echo "Las ventanas 'siempre encima' pueden no respetarse al 100%."
else
    log "Servicio systemd activo. Los avisos se muestran con 'wall' en las terminales."
fi

echo
echo "Instalación completada."
echo "  Archivos: $DESTINO"
echo "  Config:   $CONFIG"
echo "  Modo:     $MODO_INSTALACION"
