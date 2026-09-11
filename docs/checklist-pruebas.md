# Checklist de pruebas en la red real — lab.lan

Usa esta tabla **a mano** durante las pruebas en el laboratorio. Marca cada celda con
`✓` (pasa), `✗` (falla) o `—` (no aplica / equipo no disponible).

**Antes de empezar:** el servidor debe estar instalado en DC01 (Fase 5) y los agentes en
cada cliente con el mismo `token` que `C:\CiberMensajeria\config.json`. El panel se abre en
DC01 en `http://localhost:8080`.

| Campo | Valor |
|---|---|
| Fecha | |
| Probado por | |
| Token del servidor (últimos 4 caracteres) | |
| Versión del protocolo | 1 |
| Commit / etiqueta del repositorio | |

---

## Equipos del laboratorio

| Equipo | Sistema | Dirección / nombre | Usuario de prueba |
|---|---|---|---|
| DC01 | Windows Server 2022 | `192.168.1.10` / `dc01.lab.lan` | (servidor + panel) |
| Ubuntu | Ubuntu Desktop LTS | `192.168.1.20` / `daniel-cruz-hp.lab.lan` | `dquan` |
| Debian | Debian 12+ | DHCP | usuario del dominio |
| Win10 / Win11 | Windows 10/11 Pro | DHCP | usuario del dominio |
| Mac | macOS | DHCP | usuario local o del dominio |

---

## Tabla de resultados

Una fila por **máquina cliente** que pruebes. Repite la fila si pruebas con otro usuario
en el mismo equipo.

| Equipo (hostname) | SO | Usuario | 1. Arranque automático | 2. Aparece en panel | 3. Mensaje + Visto | 4. Sesión (contador, aviso 5 min, bloqueo, +15 min) | 5. Reconexión (cable) | 6. Reinicio DC01 | Notas |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |
| | | | | | | | | | |
| | | | | | | | | | |
| | | | | | | | | | |
| | | | | | | | | | |

### Qué significa cada columna

| # | Prueba | Cómo verificarlo |
|---|---|---|
| **1** | El agente arranca solo al iniciar sesión con un usuario del dominio | Cierra sesión, vuelve a entrar (o reinicia el cliente). Sin abrir terminales a mano, el agente debe conectarse al servidor en unos segundos (revisa el log del servidor o espera a que aparezca en el panel). |
| **2** | Aparece en el panel con SO y usuario correctos | En `http://localhost:8080`, la tabla muestra el hostname en minúsculas, el icono del SO correcto (🪟/🐧/🍎), el usuario de la sesión y la IP del cliente. Estado: **Conectado**. |
| **3** | Recibe un mensaje y el «Visto» llega al panel | Selecciona el equipo, envía un aviso de prueba (nivel *Información*). En el cliente aparece la ventana «Cibercafé»; al pulsar **Entendido**, la columna **Visto ✓** del panel muestra la hora. |
| **4** | Contador, aviso de 5 min, bloqueo y «+15 min» | Inicia sesión de **2 minutos** con `avisos_minutos: [1]` en la config del servidor (prueba rápida) o **15 minutos** con la config por defecto `[5, 1]`. Comprueba: contador ⏱ en esquina inferior derecha; aviso automático al llegar al umbral; pantalla de bloqueo al terminar; **+15 min** desbloquea y reinicia el contador. |
| **5** | Desconectar y reconectar el cable de red | Con el agente conectado, desenchufa el cable (o desactiva Wi‑Fi) 30–60 s y vuelve a conectar. El equipo debe volver a **Conectado** en el panel sin reiniciar el cliente (reconexión con espera creciente, tope 30 s). |
| **6** | Reiniciar DC01 | Con varios clientes conectados, reinicia DC01. Tras arrancar el servidor (tarea programada), todos los agentes deben reaparecer en el panel en menos de 2 minutos. |

---

## Procedimiento recomendado (orden sugerido)

### A. Comprobaciones previas en DC01

1. Servidor en ejecución: en DC01, el log de `C:\CiberMensajeria\logs\` (o la consola si
   lo lanzaste a mano) muestra «escuchando en 0.0.0.0:5050».
2. Panel accesible: abre `http://localhost:8080` en el navegador de DC01.
3. Firewall: regla entrante TCP **5050** (perfiles Dominio y Privado) activa.

### B. Por cada cliente (columnas 1–3)

1. Inicia sesión con un usuario del dominio (`dquan` en Ubuntu, otro en Windows, etc.).
2. Espera ~15 s y refresca el panel (se actualiza solo cada 2 s).
3. Envía un mensaje de prueba y confirma **Visto ✓**.

### C. Sesión con tiempo (columna 4) — un cliente basta

Para no esperar 15 minutos en clase, usa una sesión corta:

1. En `C:\CiberMensajeria\config.json`, temporalmente:
   ```json
   "avisos_minutos": [1]
   ```
2. Reinicia el servicio del servidor (o el proceso Python).
3. En el panel: **Iniciar sesión → 2 min** (o el botón equivalente).
4. Observa contador → aviso al minuto 1 → bloqueo al minuto 2.
5. Pulsa **+15 min** y comprueba desbloqueo.
6. Restaura `"avisos_minutos": [5, 1]` cuando termines.

### D. Resiliencia (columnas 5–6)

- Columna 5: prueba en **un** cliente con cable de red.
- Columna 6: con **al menos dos** clientes conectados, reinicia DC01 una sola vez.

---

## Solución de problemas

### El agente no conecta / no resuelve `dc01.lab.lan`

| Síntoma | Qué revisar |
|---|---|
| El log del agente dice error de conexión o «no se pudo resolver» | DNS del cliente. Debe resolver el dominio `lab.lan` (DC01 es DNS del dominio). |
| `ping dc01.lab.lan` falla desde el cliente | Revisa que el cliente esté unido al dominio y use DC01 (`192.168.1.10`) como DNS. |
| El nombre no resuelve pero la IP sí | El agente usa `servidor_respaldo` en su config (`192.168.1.10`). Verifica que esté en `agente.json` / `config.json` del cliente. |
| `nslookup dc01.lab.lan` en Windows devuelve otra IP | Registro DNS incorrecto en AD; corrige el registro A de `dc01`. |

**Comandos útiles**

```powershell
# Windows (cliente o DC01)
nslookup dc01.lab.lan
ping dc01.lab.lan
```

```bash
# Linux / macOS
getent hosts dc01.lab.lan
ping -c 3 dc01.lab.lan
```

### El firewall de DC01 bloquea el puerto 5050

| Síntoma | Qué revisar |
|---|---|
| El agente intenta conectar pero hace timeout | Regla de firewall en DC01: TCP **5050** entrante, perfiles **Dominio** y **Privado**. |
| Funciona en DC01 pero no desde otros equipos | El servidor escucha en `0.0.0.0:5050` (`host_agentes` en config). No debe estar solo en `127.0.0.1`. |

**Comandos útiles**

```powershell
# Desde un cliente Windows
Test-NetConnection dc01.lab.lan -Port 5050
```

```bash
# Desde Linux o macOS
nc -zv dc01.lab.lan 5050
# o, si nc no está instalado:
timeout 3 bash -c 'echo >/dev/tcp/dc01.lab.lan/5050' && echo OK || echo FALLO
```

Si `Test-NetConnection` muestra `TcpTestSucceeded : False`, el problema es red o firewall
en DC01, no el agente.

### Token incorrecto

| Síntoma | Qué revisar |
|---|---|
| El agente se conecta y se desconecta al instante | El log del servidor muestra `rechazado` / token incorrecto. El `token` del agente debe coincidir **exactamente** con `C:\CiberMensajeria\config.json`. |
| Reinstalaste el servidor y generó token nuevo | Vuelve a instalar o reconfigurar cada agente con el token nuevo. |

### El equipo no aparece en el panel

| Síntoma | Qué revisar |
|---|---|
| Nunca aparece | Agente no arrancó (revisa autostart / tarea / `.desktop` / LaunchAgent). |
| Aparece como **Desconectado** | Sin latido > 45 s: red caída, proceso del agente cerrado o firewall. |
| Aparece con usuario «—» | Sesión sin usuario detectado (p. ej. Debian en consola con `wall`). |

### Mensaje enviado pero no hay ventana en el cliente

| Síntoma | Qué revisar |
|---|---|
| Panel dice «Esperando…» en Visto pero no hay ventana | En Linux sin `DISPLAY`: modo consola (`wall`). En escritorio: tkinter no instalado (`python3-tk` en Debian/Ubuntu). |
| Ventana detrás de otras apps (Linux Wayland) | Limitación documentada: «siempre encima» puede no cumplirse al 100 % en Wayland/XWayland. |
| En Windows no hay ventana | El agente debe correr con `pythonw.exe` en la sesión del usuario, **no** como servicio de Windows. |

### «Visto ✓» no se actualiza

| Síntoma | Qué revisar |
|---|---|
| El usuario cerró la ventana pero el panel sigue en «Esperando…» | Conexión perdida antes de enviar `visto`; revisa logs del agente. |
| La hora no coincide | El panel muestra hora local del navegador en DC01; es normal un desfase de segundos. |

### `config.json` con BOM tras actualizar el servidor

| Síntoma | Qué revisar |
|---|---|
| Al arrancar: `Error de configuración: 'config.json' no es JSON válido: Unexpected UTF-8 BOM` | Suele aparecer **después de reinstalar** el servidor con `instalar-servidor.ps1` de una versión antigua: `Set-Content -Encoding UTF8` en PowerShell 5.1 escribe el JSON con marca BOM (`\xEF\xBB\xBF`) y `json.load()` de Python falla. El servidor funcionaba antes porque el `config.json` anterior no tenía BOM. |
| Mismo error al instalar agentes en Windows | El instalador del agente también genera `agente.json`; aplica la misma corrección. |

**Cómo arreglarlo sin reinstalar:**

1. Abre `C:\CiberMensajeria\config.json` en el Bloc de notas.
2. **Archivo → Guardar como…**
3. En **Codificación**, elige **UTF-8** (no «UTF-8 con BOM» ni «Unicode»).
4. Guarda y vuelve a ejecutar: `py -m servidor --config config.json`

Alternativa en PowerShell (quita el BOM sin cambiar el contenido):

```powershell
$ruta = "C:\CiberMensajeria\config.json"
$texto = Get-Content -Path $ruta -Raw
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ruta, $texto, $utf8)
```

**Prevención:** usa el instalador actual del repositorio (escribe UTF-8 sin BOM) o actualiza el código del servidor/agente (lee con `utf-8-sig`, que acepta ambos formatos).

### Acentos rotos en PowerShell (instaladores)

| Síntoma | Qué revisar |
|---|---|
| Caracteres como `Ã©` en lugar de `é` al ejecutar `.ps1` | Los scripts deben estar en **UTF-8 con BOM** y CRLF (`.gitattributes` del repo). Vuelve a copiar desde el repositorio sin reconvertir encoding. |
| Error de sintaxis raro en comentarios en español | Abre el `.ps1` en un editor que muestre BOM; si falta, añade BOM UTF-8 y guarda. |

### Logs útiles

| Ubicación | Qué buscar |
|---|---|
| DC01: `C:\CiberMensajeria\logs\` | Conexiones `hola`, rechazos, envío de mensajes, sesiones. |
| Windows cliente: `%LOCALAPPDATA%\CiberMensajeria\logs\` | Reconexión, errores de red, mensajes recibidos. |
| Linux: `~/.local/state/ciber-agente/` | Igual que arriba. |
| macOS: `~/Library/Logs/CiberMensajeria/` | Igual que arriba. |

---

## Criterio de éxito de la Fase 6

La fase se considera **superada** cuando:

- Al menos **un cliente de cada SO disponible** (Windows, Linux y, si hay, macOS) pasa las
  columnas **1–4**.
- La columna **5** pasa en al menos un cliente.
- La columna **6** pasa con el servidor reiniciado y **dos o más** clientes que vuelven solos.

Si Debian solo tiene consola (sin escritorio), documenta en **Notas** que los avisos llegan
por `wall` y marca la columna 3 como `✓` si `wall` muestra el texto.
