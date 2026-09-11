# Plan: Ciber Mensajería multiplataforma

## Estado

- [ ] Fase 0 — Estructura del proyecto
- [ ] Fase 1 — Protocolo y núcleo del servidor
- [ ] Fase 2 — Agente con ventanas emergentes
- [ ] Fase 3 — Panel web del servidor
- [ ] Fase 4 — Sesiones con tiempo (lo "cibercafé")
- [ ] Fase 5 — Instaladores por sistema operativo
- [ ] Fase 6 — Pruebas en la red real
- [ ] Fase 7 — Extras (opcionales)

---

## 1. Objetivo

Replicar cómo funcionaban los cibercafés: desde la computadora de "caja" (el servidor DC01)
se ve qué equipos están encendidos, quién tiene sesión abierta, cuánto tiempo le queda a cada
uno, y se les mandan avisos que aparecen encima de todo en su pantalla. Cuando se acaba el
tiempo, el equipo muestra una pantalla de "Tu tiempo terminó".

Debe funcionar igual en Windows 10/11, Ubuntu, Debian y macOS, con el servidor en
Windows Server 2022.

## 2. Arquitectura (decisiones ya tomadas)

```
                 ┌──────────────── DC01 (Windows Server 2022) ────────────────┐
  Navegador ───► │ Panel web  :8080  ◄──►  Servidor (Python, asyncio)  :5050  │
  (caja)         └──────────────────────────────────▲─────────────────────────┘
                                                    │ TCP, JSON por líneas
               ┌──────────────┬──────────────┬──────┴───────┬──────────────┐
            Agente         Agente         Agente         Agente        Agente
            Win10          Win11          Ubuntu         Debian        macOS
```

- **Servidor** en DC01: escucha a los agentes en TCP 5050 y sirve el panel web en 8080.
  Es la única fuente de verdad: guarda equipos, sesiones, temporizadores e historial.
- **Agente** en cada cliente: programa pequeño que arranca al iniciar sesión el usuario, se
  conecta al servidor, se reconecta solo si se cae la red, y muestra las ventanas.
- **¿Por qué agente y no `msg.exe` + SSH?** Porque así el mismo programa funciona en los tres
  sistemas, los clientes no abren puertos (no hace falta `AllowRemoteRPC`, reglas de
  firewall en cada cliente ni llaves SSH de root), y el servidor sabe en tiempo real quién
  está conectado y si el usuario leyó el aviso. El script anterior queda en `legacy/` como
  plan B.

## 3. Estructura de carpetas

```
ciber-mensajeria/
├── CLAUDE.md
├── PLAN.md
├── README.md
├── .gitattributes
├── comun/
│   └── protocolo.py          # codificar/decodificar mensajes, constantes, versión
├── servidor/
│   ├── __main__.py
│   ├── servidor.py           # asyncio: conexiones de agentes
│   ├── estado.py             # equipos, sesiones, temporizadores, historial
│   ├── panel_http.py         # API + archivos estáticos del panel
│   ├── panel/                # index.html, app.js, estilo.css
│   └── config.json
├── agente/
│   ├── __main__.py
│   ├── agente.py             # conexión, reconexión, cola de eventos
│   ├── ventanas.py           # emergente, cuenta regresiva, pantalla de bloqueo
│   ├── plataforma.py         # detectar SO, usuario, rutas de logs, bloqueo nativo
│   └── config.json
├── instaladores/
│   ├── windows/              # instalar-servidor.ps1, instalar-agente.ps1, desinstalar-agente.ps1
│   ├── linux/                # instalar-agente.sh, desinstalar-agente.sh, ciber-agente.desktop
│   └── macos/                # instalar-agente.sh, desinstalar-agente.sh, lab.ciber.agente.plist
├── herramientas/
│   └── simular_agentes.py    # agentes falsos para probar sin las máquinas
├── tests/
├── docs/                     # protocolo.md, guia-instalacion.md, guion-demo.md
└── legacy/
    └── panel-cibercafe.ps1   # script anterior (msg.exe + SSH). No se modifica.
```

## 4. Protocolo

- TCP, puerto **5050**. Cada mensaje es un objeto JSON en UTF-8 terminado en `\n`.
- Todo mensaje lleva `"tipo"`. Los que requieren respuesta llevan `"id"` (uuid4).
- Latido: el agente manda `ping` cada 15 s. El servidor marca el equipo como desconectado
  si pasan 45 s sin nada.
- Reconexión del agente con espera creciente: 1, 2, 4, 8, 16, 30 s (tope 30).
- Mensajes de más de 64 KB se rechazan.

Agente → servidor:

| tipo | campos |
|---|---|
| `hola` | `token`, `equipo` (hostname en minúsculas), `so` (`windows`/`linux`/`macos`), `version_so`, `usuario`, `version_agente` |
| `visto` | `id` del mensaje que el usuario cerró con "Entendido" |
| `ping` | — |

Servidor → agente:

| tipo | campos |
|---|---|
| `bienvenido` | estado actual: `sesion` (segundos restantes o `null`), `bloqueado` (bool) |
| `rechazado` | `motivo` (token incorrecto, versión incompatible). El servidor cierra la conexión. |
| `mensaje` | `id`, `titulo`, `texto`, `nivel` (`info`/`aviso`/`critico`), `pedir_visto` (bool) |
| `sesion` | `restante` (segundos) o `null` para quitar el contador |
| `bloquear` | `texto` |
| `desbloquear` | — |
| `pong` | — |

Un mismo equipo puede tener varias conexiones (una por usuario con sesión abierta). Los
mensajes a un equipo se mandan a todas sus conexiones. Documenta el protocolo en
`docs/protocolo.md`.

## 5. Fases

### Fase 0 — Estructura del proyecto

- Crear carpetas, `README.md` inicial, `.gitattributes` (`*.ps1 text eol=crlf`,
  `*.sh text eol=lf`, `*.py text eol=lf`), `.gitignore`, `git init`.
- Crear `legacy/` vacía con un `LEAME.txt` que diga que ahí va `panel-cibercafe.ps1`
  (yo lo copio a mano).

**Terminado cuando:** la estructura existe y `python -m unittest` corre sin errores (aunque
todavía no haya pruebas).

### Fase 1 — Protocolo y núcleo del servidor

- `comun/protocolo.py`: codificar y decodificar líneas JSON, validar campos por tipo,
  constantes (puerto, tiempos del latido, versión del protocolo).
- `servidor/servidor.py` con `asyncio.start_server`: aceptar agentes, validar `hola` y token,
  registrar equipo, responder `ping`, detectar desconexiones, limpiar al cerrar.
- `servidor/estado.py`: registro de equipos (nombre, SO, usuario, IP, conectado desde, último
  latido, conexiones activas) y un historial en memoria que también se escribe a
  `historial.jsonl`.
- `servidor/config.json`: `puerto_agentes`, `puerto_panel`, `host_panel` (`127.0.0.1` por
  defecto), `token`, `avisos_minutos` (`[5, 1]`), `texto_fin_sesion`.
- Logs con `logging` a consola y a archivo.
- `herramientas/simular_agentes.py`: levanta N agentes falsos con nombres tipo `PC-01`, SO
  variados, que responden `visto` a los 2 s. Sirve para probar todo sin las máquinas.
- Pruebas: protocolo (mensajes válidos, inválidos, cortados, demasiado grandes) y servidor
  (registro, token malo, desconexión por latido).

**Terminado cuando:** corro el servidor y el simulador, y el log muestra 4 equipos que se
conectan, mandan latidos y se desconectan limpio al cerrar el simulador.

### Fase 2 — Agente con ventanas emergentes

- `agente/agente.py`: la red va en un hilo aparte; la interfaz tkinter en el **hilo
  principal** (obligatorio en macOS). Se comunican con una `queue.Queue` que la interfaz
  revisa con `root.after(200, ...)`. La ventana raíz de tkinter queda oculta.
- `agente/plataforma.py`: detectar SO, versión, hostname y usuario actual; ruta de logs por SO
  (Windows `%LOCALAPPDATA%\CiberMensajeria\logs`, Linux `~/.local/state/ciber-agente`,
  macOS `~/Library/Logs/CiberMensajeria`).
- Configuración: `--config` o la ruta por defecto del SO. Campos: `servidor`
  (`dc01.lab.lan`), `servidor_respaldo` (`192.168.1.10`), `puerto`, `token`. Si el nombre no
  resuelve, usa la IP de respaldo.
- `agente/ventanas.py` → **ventana emergente**: siempre encima, centrada, letra grande, color
  según nivel (azul info, amarillo aviso, rojo crítico), título "Cibercafé", botón
  "Entendido" que manda `visto`, y un sonido (`bell()`). Si llegan varios mensajes, se apilan
  con un pequeño desplazamiento. Nunca bloquea la red.
- Solo una instancia del agente por usuario (un archivo de bloqueo o un socket local).
- Pruebas: la lógica de reconexión y el manejo de mensajes, sin abrir ventanas.

**Terminado cuando:** con servidor y agente corriendo en mi laptop, mando un `mensaje` (por
ahora con un script de prueba) y aparece la ventana; al dar "Entendido" el log del servidor
registra el `visto`; si apago el servidor, el agente se reconecta solo al volver a encenderlo.

### Fase 3 — Panel web del servidor

- `servidor/panel_http.py` con `http.server.ThreadingHTTPServer` en un hilo. Para hablar con
  el bucle de asyncio usa `asyncio.run_coroutine_threadsafe`.
- Por defecto escucha solo en `127.0.0.1` (se abre desde el propio DC01). Si `host_panel` es
  `0.0.0.0`, exige contraseña (autenticación básica, contraseña en `config.json`).
- API JSON:
  - `GET /api/equipos` — lista con estado, SO, usuario, IP, tiempo restante, bloqueado
  - `POST /api/mensaje` — `{destinos: [...] | "todos", texto, nivel}`
  - `GET /api/historial` — últimos 100 eventos
  - (las rutas de sesiones se agregan en la Fase 4)
- Panel (`index.html`, `app.js`, `estilo.css`, sin frameworks ni CDN, porque la red del
  laboratorio puede no tener internet): tabla de equipos que se actualiza cada 2 s, ícono por
  SO, casillas para elegir uno o varios, "Seleccionar todos", caja de texto, selector de
  nivel, botones de mensajes rápidos ("Te quedan 5 minutos", "Te queda 1 minuto", "Tu tiempo
  terminó, pasa a caja"), y una columna "Visto ✓" con la hora en que el usuario confirmó.
- Diseño limpio y legible en un proyector: letra grande, buen contraste.

**Terminado cuando:** con el simulador corriendo, desde el navegador veo los equipos, mando un
mensaje a dos de ellos y la columna "Visto" se llena.

### Fase 4 — Sesiones con tiempo

- En `estado.py`, sesiones por equipo: hora de fin, minutos asignados, avisos ya enviados.
  Un bucle revisa cada segundo.
- Avisos automáticos según `avisos_minutos` (por defecto a los 5 y 1 minutos).
- Al llegar a cero: el servidor manda `bloquear` con `texto_fin_sesion`.
- API: `POST /api/sesion/iniciar {equipo, minutos}`, `/api/sesion/extender {equipo, minutos}`
  (extender también desbloquea), `/api/sesion/terminar {equipo}`,
  `/api/desbloquear {equipo}`.
- Si un agente se reconecta, el `bienvenido` le devuelve el tiempo restante y si está bloqueado.
- Agente → **contador**: ventanita siempre encima en la esquina inferior derecha con
  "⏱ 12:34", que se pone roja con menos de 5 minutos. Solo se ve si hay sesión.
- Agente → **pantalla de bloqueo**: pantalla completa, siempre encima, sin barra de título, que
  ignora el botón de cerrar y se vuelve a subir cada segundo. Muestra el texto y el nombre del
  equipo. Se quita con `desbloquear`. Hay que ser honestos en la documentación: es un bloqueo
  "de cibercafé", no una medida de seguridad real.
- Opcional en config del agente, `bloqueo_nativo: false`: si es `true`, además bloquea con el
  sistema (Windows `rundll32.exe user32.dll,LockWorkStation`, Linux `loginctl lock-session`,
  macOS `pmset displaysleepnow`).
- Panel: botones por equipo para iniciar 15/30/60 min o una cantidad libre, "+15 min",
  "Terminar" y "Desbloquear"; columna con cuenta regresiva.
- Pruebas: temporizador con reloj simulado (sin esperar minutos reales), avisos que no se
  repitan, extender, reconexión a mitad de sesión.

**Terminado cuando:** inicio una sesión de 2 minutos en mi laptop con `avisos_minutos: [1]`,
veo el contador, recibo el aviso al minuto, se bloquea al terminar y con "+15 min" se
desbloquea.

### Fase 5 — Instaladores

Todos los instaladores piden permisos de administrador, muestran lo que hacen paso a paso en
español, y tienen su desinstalador.

**Servidor (DC01)** — `instaladores/windows/instalar-servidor.ps1`:
- Verificar Python 3.10+ (si falta, explicar cómo instalarlo desde python.org marcando "para
  todos los usuarios" y "agregar al PATH").
- Copiar a `C:\CiberMensajeria\`, generar un token aleatorio en `config.json` y mostrarlo en
  pantalla para usarlo en los agentes.
- Regla de firewall: TCP 5050 entrante, perfiles Dominio y Privado.
- Tarea programada "al iniciar el sistema" como SYSTEM que corre el servidor.
- Acceso directo en el escritorio a `http://localhost:8080`.

**Agente Windows** — `instaladores/windows/instalar-agente.ps1 -Token XXX`:
- Verificar Python (intentar `winget` si existe; si no, explicar).
- Copiar a `C:\Program Files\CiberMensajeria\`, config en `C:\ProgramData\CiberMensajeria\`.
- Acceso directo en la carpeta de Inicio **común** (`ProgramData\...\StartUp`) que ejecuta
  `pythonw.exe` (sin ventana de consola), para que arranque con **cualquier** usuario del
  dominio. Arrancarlo ya para la sesión actual.

**Agente Linux (Ubuntu/Debian)** — `instaladores/linux/instalar-agente.sh --token XXX`:
- `apt install python3 python3-tk`.
- Copiar a `/opt/ciber-mensajeria/`, config en `/etc/ciber-mensajeria/agente.json`.
- Autoarranque en `/etc/xdg/autostart/ciber-agente.desktop`, que aplica a todos los usuarios,
  incluidos los del dominio como `dquan@lab.lan`.
- Revisar que funcione en Wayland (Ubuntu usa XWayland para tkinter; documentar si "siempre
  encima" no se respeta del todo).
- **Si Debian no tiene escritorio**: modo consola. Si no hay `DISPLAY` ni `WAYLAND_DISPLAY`, el
  agente corre como servicio systemd de root y entrega los avisos con `wall` a todas las
  terminales. El instalador detecta el caso y lo configura.

**Agente macOS** — `instaladores/macos/instalar-agente.sh --token XXX`:
- Verificar `python3 -c "import tkinter"`. Recomendar el Python de python.org (el de Apple
  trae un Tk viejo).
- Copiar a `/Library/Application Support/CiberMensajeria/`.
- LaunchAgent en `/Library/LaunchAgents/lab.ciber.agente.plist` con `RunAtLoad` y
  `KeepAlive`, y cargarlo con `launchctl bootstrap gui/$(id -u)`.

**Terminado cuando:** `docs/guia-instalacion.md` explica cada instalador en pasos que se
puedan seguir sin saber programar, y cada script pasa una revisión de sintaxis
(`bash -n`, y el analizador de PowerShell si está disponible).

### Fase 6 — Pruebas en la red real

Generar `docs/checklist-pruebas.md` con una tabla para marcar a mano, por cada equipo:

- El agente arranca solo al iniciar sesión con un usuario del dominio.
- Aparece en el panel con SO y usuario correctos.
- Recibe un mensaje y el "Visto" llega al panel.
- Contador, aviso de 5 min, bloqueo y "+15 min" funcionan.
- Si desconecto el cable y lo vuelvo a conectar, se reconecta solo.
- Si reinicio DC01, todos vuelven a aparecer.

Incluir una sección de solución de problemas: el agente no resuelve `dc01.lab.lan` (revisar
DNS del cliente), el firewall de DC01 bloquea el 5050 (`Test-NetConnection dc01 -Port 5050`
desde Windows, `nc -zv dc01.lab.lan 5050` desde Linux/Mac), acentos rotos en PowerShell (BOM).

Generar `docs/guion-demo.md`: guion de 5 minutos para la presentación.

### Fase 7 — Extras (solo si sobra tiempo; preguntar antes)

- **Integración con Active Directory**: el servidor consulta `Get-ADComputer` y muestra en el
  panel los equipos del dominio que no tienen agente, en gris.
- **Envío de respaldo**: para equipos sin agente, usar `msg.exe` (Windows) o SSH
  (Linux/macOS), reutilizando la lógica de `legacy/panel-cibercafe.ps1`.
- **Despliegue por GPO** del agente en los Windows del dominio.
- **Ejecutable** del agente con PyInstaller para no instalar Python en los clientes (hay que
  compilarlo en cada SO).
- **TLS** en la conexión agente-servidor con un certificado propio.
- Exportar el historial a CSV desde el panel.