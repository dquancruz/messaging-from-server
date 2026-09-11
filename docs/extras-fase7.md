# Fase 7 — Extras opcionales

Funciones adicionales del panel y del servidor. Todas son opcionales y se
activan en `servidor/config.json`.

## Integración con Active Directory

Muestra en el panel (en gris, etiqueta **Sin agente**) los equipos del
dominio que aún no tienen el agente conectado.

En DC01, con el módulo Active Directory instalado:

```json
"ad_habilitado": true,
"ad_dominio": "lab.lan",
"ad_filtro": "*",
"ad_intervalo_segundos": 300
```

El servidor ejecuta `Get-ADComputer` cada 5 minutos (configurable) y fusiona
la lista con los equipos que ya tienen agente.

Para desarrollo o pruebas sin AD, usa un archivo JSON:

```json
"ad_habilitado": true,
"ad_archivo_respaldo": "servidor/equipos-ad-ejemplo.json"
```

## Envío de respaldo (msg.exe / SSH)

Si un equipo no tiene agente, el panel puede mandar el aviso por métodos
alternativos (la misma idea que `legacy/panel-cibercafe.ps1`):

- **Windows:** `msg.exe` hacia `equipo.lab.lan`
- **Linux / macOS:** SSH con `wall` (requiere acceso sin contraseña desde DC01)

Activar en `config.json`:

```json
"respaldo_habilitado": true,
"respaldo_ssh_usuario": "root"
```

En el panel, marca **Usar envío de respaldo** y selecciona equipos sin agente.
Los resultados aparecen en el mensaje de confirmación y en el historial como
`mensaje_respaldo`.

Requisitos en el laboratorio:

- En Windows: el servicio Mensajes (`msg.exe`) y permisos de red hacia los
  clientes.
- En Linux: clave SSH de DC01 en los equipos destino, o configuración
  equivalente.

## Exportar historial a CSV

Desde el panel: botón **Exportar historial CSV**, o abre directamente
`http://localhost:8080/api/historial.csv`.

Columnas: `cuando`, `tipo`, `equipo`, `usuario`, `ip`, `so`, `id_mensaje`,
`minutos`.

## TLS en la conexión agente ↔ servidor

Opcional. Genera un certificado en DC01 (ejemplo con OpenSSL):

```powershell
openssl req -x509 -newkey rsa:2048 -keyout C:\CiberMensajeria\tls.pem -out C:\CiberMensajeria\tls.pem -days 3650 -nodes -subj "/CN=dc01.lab.lan"
```

Servidor (`config.json`):

```json
"tls_habilitado": true,
"tls_certificado": "C:/CiberMensajeria/tls.pem",
"tls_clave": "C:/CiberMensajeria/tls.pem"
```

Agente (`agente.json`):

```json
"tls_habilitado": true
```

Sin `tls_ca`, el agente acepta certificados autofirmados (adecuado para red
local). Para validación estricta, copia el `.pem` a los clientes y define
`tls_ca` con la ruta al archivo.

## Despliegue del agente por GPO

Ver `instaladores/windows/desplegar-agente-gpo.md`.

## Ejecutable con PyInstaller

Ver `instaladores/construir-ejecutable.md`. Hay que compilar en cada sistema
operativo destino (Windows, Linux, macOS).
