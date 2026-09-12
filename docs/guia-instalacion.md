# Guía de instalación — Ciber Mensajería

Esta guía explica cómo instalar el servidor y los agentes en el laboratorio
`lab.lan`. No hace falta saber programar: solo seguir los pasos en orden.

## Resumen

1. Instale el **servidor** en DC01 (Windows Server 2022).
2. Instale el **agente** en cada equipo cliente.

El **token** compartido del laboratorio ya está en el repositorio
(`servidor/config.json` y `agente/config.json`): `lab-lan-ciber-mensajeria`.
Los instaladores lo copian automáticamente; no hace falta pasarlo a mano.

| Componente | Sistema | Script |
|---|---|---|
| Servidor | DC01 (Windows Server) | `instaladores/windows/instalar-servidor.ps1` |
| Agente | Windows 10/11 | `instaladores/windows/instalar-agente.ps1` |
| Agente | Ubuntu / Debian | `instaladores/linux/instalar-agente.sh` |
| Agente | macOS | `instaladores/macos/instalar-agente.sh` |

---

## Requisitos previos

- Red local `192.168.1.0/24` con DNS del dominio `lab.lan`.
- DC01 resuelve como `dc01.lab.lan` (192.168.1.10).
- **Python 3.10 o superior** en cada máquina (solo biblioteca estándar).
- En clientes con escritorio: **tkinter** (incluido en Windows; en Linux:
  paquete `python3-tk`; en macOS: Python de [python.org](https://www.python.org/downloads/)).

---

## 1. Servidor en DC01

### Paso a paso

1. Copie la carpeta del proyecto a DC01 (por ejemplo `C:\Temp\ciber-mensajeria`).
2. Abra **PowerShell como Administrador**.
3. Ejecute:

```powershell
cd C:\Temp\ciber-mensajeria\instaladores\windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\instalar-servidor.ps1
```

4. El script:
   - Comprueba que Python 3.10+ esté instalado.
   - Copia los archivos a `C:\CiberMensajeria\`.
   - Copia la configuración del repositorio (token, contraseñas de caja y moderación).
   - Abre el puerto **TCP 5050** en el firewall (perfiles Dominio y Privado).
   - Crea una tarea programada que arranca el servidor al iniciar Windows.
   - Copia `iniciar-servidor.ps1` para arrancar el servidor manualmente.
   - Crea un acceso directo en el escritorio al panel: `http://localhost:8080`.

5. Al final muestra el token, las contraseñas del panel y la ruta de inicio manual.

> Para actualizar a una versión nueva del proyecto, véase la
> [sección 5](#5-actualizar-a-una-versión-nueva).

### Si falta Python en DC01

1. Descargue el instalador desde https://www.python.org/downloads/
2. Marque **Install for all users** y **Add python.exe to PATH**.
3. Vuelva a ejecutar `instalar-servidor.ps1`.

### Iniciar el servidor manualmente

Si necesita arrancar el servidor en una consola visible (por ejemplo tras
actualizar archivos o para ver errores en pantalla):

```powershell
C:\CiberMensajeria\iniciar-servidor.ps1
```

También puede ejecutarlo desde el repositorio antes de instalar (desarrollo
en DC01):

```powershell
cd C:\ruta\al\proyecto\instaladores\windows
.\iniciar-servidor.ps1 -Destino C:\CiberMensajeria
```

En desarrollo local (cualquier SO):

```bash
python -m servidor --config servidor/config.json
```

### Comprobar que funciona

- Abra el acceso directo **Ciber Mensajería - Panel** en el escritorio de DC01.
- Debe cargar la tabla de equipos (vacía hasta que haya agentes).
- Revise el log en `C:\CiberMensajeria\datos\servidor.log`.

---

## 2. Agente en Windows 10/11

### Paso a paso

1. Copie el proyecto al equipo (o solo la carpeta `instaladores\windows` y el código fuente).
2. Abra **PowerShell como Administrador**.
3. Ejecute:

```powershell
cd C:\ruta\al\proyecto\instaladores\windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\instalar-agente.ps1
```

   Si necesita otro token: `.\instalar-agente.ps1 -Token "otro-token"`.

4. El script:
   - Comprueba Python (intenta instalarlo con `winget` si está disponible).
   - Copia el agente a `C:\Program Files\CiberMensajeria\`.
   - Guarda la configuración en `C:\ProgramData\CiberMensajeria\agente.json`.
   - Crea un acceso directo en la carpeta de **Inicio común** para que arranque con
     **cualquier usuario** del dominio (usa `pythonw.exe`, sin ventana de consola).
   - Inicia el agente en la sesión actual.

### Desinstalar

```powershell
.\desinstalar-agente.ps1
```

---

## 3. Agente en Ubuntu / Debian

### Equipos con escritorio (Ubuntu Desktop, etc.)

1. Copie el proyecto al equipo.
2. Ejecute como root:

```bash
cd /ruta/al/proyecto/instaladores/linux
sudo ./instalar-agente.sh
```

3. El script instala `python3` y `python3-tk`, copia a `/opt/ciber-mensajeria/`,
   guarda la config en `/etc/ciber-mensajeria/agente.json` y registra el autostart
   en `/etc/xdg/autostart/` (aplica a todos los usuarios, incluidos los del dominio).

### Equipos sin escritorio (Debian servidor)

Si no hay entorno gráfico, el instalador detecta el caso y configura un **servicio
systemd** que entrega los avisos con `wall` en todas las terminales.

```bash
sudo ./instalar-agente.sh --modo consola
```

Puede forzar el modo con `--modo grafico` o `--modo consola`.

### Wayland en Ubuntu

Ubuntu usa Wayland por defecto; tkinter funciona vía XWayland. Las ventanas
«siempre encima» pueden no cumplirse al 100 % en Wayland. Esto es una limitación
conocida de XWayland, no del agente.

### Desinstalar

```bash
sudo ./desinstalar-agente.sh
```

---

## 4. Agente en macOS

### Paso a paso

1. Instale **Python 3.10+** desde [python.org](https://www.python.org/downloads/).
   El Python de Apple suele traer Tk antiguo; se recomienda el de python.org.
2. Copie el proyecto al Mac.
3. Ejecute:

```bash
cd /ruta/al/proyecto/instaladores/macos
sudo ./instalar-agente.sh
```

4. El script:
   - Verifica `python3` y `import tkinter`.
   - Copia a `/Library/Application Support/CiberMensajeria/`.
   - Instala `lab.ciber.agente.plist` en `/Library/LaunchAgents/`.
   - Carga el agente con `launchctl` para el usuario actual.

### Desinstalar

```bash
sudo ./desinstalar-agente.sh
```

---

## 5. Actualizar a una versión nueva

Cuando publique una nueva versión del proyecto (número en `VERSION` y entrada en
`CHANGELOG.md`), siga este proceso en el laboratorio.

### Orden recomendado

1. **Servidor** en DC01.
2. **Agentes** en cada equipo cliente.

Así el servidor ya entiende el protocolo nuevo antes de que los clientes se
reconecten. Si solo cambió la interfaz (panel o ventanas), el orden importa
menos, pero conviene mantener siempre servidor primero.

### Qué conservar y qué se sobrescribe

| Ubicación | Se conserva al actualizar solo código | Se sobrescribe al reinstalar con el script |
|---|---|---|
| DC01: `C:\CiberMensajeria\datos\` | Sí (historial, chat, logs) | Sí (el instalador no la borra) |
| DC01: `C:\CiberMensajeria\config.json` | Sí, si copia solo `.py` | Sí (copia del repositorio) |
| Cliente Windows: `C:\ProgramData\CiberMensajeria\agente.json` | Sí, si copia solo `.py` | Sí (valores por defecto del instalador) |
| Cliente Linux: `/etc/ciber-mensajeria/agente.json` | Sí, si copia solo `.py` | Sí |
| Cliente macOS: `…/CiberMensajeria/agente.json` | Sí, si copia solo `.py` | Sí |

Si personalizó un JSON (otra IP de servidor, token distinto, etc.), **guarde una
copia** antes de volver a ejecutar el instalador, o use la actualización manual
de solo código.

### 5.1 Servidor (DC01)

#### Opción A — Reinstalar con el script (la más simple)

Use esta opción si **no** editó `config.json` en DC01 (token y contraseñas del
repositorio le sirven).

1. Copie la nueva versión del repositorio a DC01 (por ejemplo
   `C:\Temp\ciber-mensajeria`).
2. Abra **PowerShell como Administrador**.
3. Ejecute:

```powershell
cd C:\Temp\ciber-mensajeria\instaladores\windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\instalar-servidor.ps1
```

El script actualiza el código, copia de nuevo `config.json` del repositorio,
actualiza `iniciar-servidor.ps1` y **reinicia la tarea programada** del
servidor. La carpeta `C:\CiberMensajeria\datos\` **no se borra**.

#### Opción B — Solo código (conservar `config.json` editado)

1. Copie la nueva versión del repositorio a DC01.
2. En PowerShell (como Administrador), sustituya solo los archivos de programa:

```powershell
$origen = "C:\Temp\ciber-mensajeria"
$destino = "C:\CiberMensajeria"

Copy-Item "$origen\comun\*.py" "$destino\comun\" -Force
Copy-Item "$origen\servidor\*.py" "$destino\servidor\" -Force
Copy-Item "$origen\servidor\panel\*" "$destino\servidor\panel\" -Recurse -Force
Copy-Item "$origen\instaladores\windows\iniciar-servidor.ps1" "$destino\" -Force
```

3. Reinicie el servidor:

```powershell
Stop-ScheduledTask -TaskName "CiberMensajeriaServidor"
Start-ScheduledTask -TaskName "CiberMensajeriaServidor"
```

Para probar antes en consola visible: `C:\CiberMensajeria\iniciar-servidor.ps1`
(detenga antes la tarea programada para no tener dos instancias).

#### Comprobar el servidor

- Panel: http://localhost:8080 (debe cargar sin «Error al cargar equipos»).
- Log: `C:\CiberMensajeria\datos\servidor.log` sin errores recientes.
- Los agentes ya conectados se reconectarán solos tras unos segundos.

### 5.2 Agente en Windows 10/11

#### Opción A — Reinstalar con el script

1. Copie la nueva versión del repositorio al equipo.
2. PowerShell como Administrador:

```powershell
cd C:\ruta\al\proyecto\instaladores\windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\instalar-agente.ps1
```

Regenera `agente.json` con los valores por defecto (token del repositorio).
Reinicia el agente en la sesión actual.

#### Opción B — Solo código

```powershell
$origen = "C:\ruta\al\proyecto"
$destino = "C:\Program Files\CiberMensajeria"

Copy-Item "$origen\agente\*.py" "$destino\agente\" -Force
Copy-Item "$origen\comun\*.py" "$destino\comun\" -Force
```

Cierre el agente (Administrador de tareas → `pythonw.exe` del módulo `agente`) o
cierre sesión y vuelva a entrar; el acceso directo de Inicio lo arrancará de
nuevo.

### 5.3 Agente en Ubuntu / Debian

#### Opción A — Reinstalar con el script

```bash
cd /ruta/al/proyecto/instaladores/linux
sudo ./instalar-agente.sh
```

Si el equipo es sin escritorio, añada `--modo consola` como en la instalación
inicial. Sobrescribe `agente.json` y los scripts en `/opt/ciber-mensajeria/`.

#### Opción B — Solo código

```bash
sudo install -m 644 /ruta/al/proyecto/agente/*.py /opt/ciber-mensajeria/agente/
sudo install -m 644 /ruta/al/proyecto/comun/*.py /opt/ciber-mensajeria/comun/
```

Reinicio según el modo instalado:

- **Escritorio (autostart):** cierre sesión y vuelva a entrar, o ejecute
  `/opt/ciber-mensajeria/ejecutar-agente.sh` como el usuario de la sesión.
- **Consola (systemd):** `sudo systemctl restart ciber-agente`

### 5.4 Agente en macOS

#### Opción A — Reinstalar con el script

```bash
cd /ruta/al/proyecto/instaladores/macos
sudo ./instalar-agente.sh
```

#### Opción B — Solo código

```bash
sudo install -m 644 /ruta/al/proyecto/agente/*.py "/Library/Application Support/CiberMensajeria/agente/"
sudo install -m 644 /ruta/al/proyecto/comun/*.py "/Library/Application Support/CiberMensajeria/comun/"
```

Reinicie el LaunchAgent (sustituya `USUARIO` por el que usa el Mac):

```bash
UID_GUI=$(id -u USUARIO)
sudo launchctl bootout "gui/$UID_GUI" /Library/LaunchAgents/lab.ciber.agente.plist
sudo launchctl bootstrap "gui/$UID_GUI" /Library/LaunchAgents/lab.ciber.agente.plist
```

### 5.5 Publicar una versión nueva (mantenedores)

Antes de desplegar en el laboratorio:

1. Actualice `VERSION` y `CHANGELOG.md`.
2. Si cambió el agente, actualice `VERSION_AGENTE` en `agente/__init__.py` (se
   envía al servidor en cada conexión y queda registrada en el estado interno).
3. Ejecute las pruebas: `python -m unittest discover -s tests -v`.
4. Copie el repositorio (o un tag de GitHub) a DC01 y a los clientes, y siga
   las secciones 5.1–5.4.

---

## 6. Opciones comunes de configuración

Los instaladores crean un JSON con valores por defecto del laboratorio:

| Campo | Valor por defecto |
|---|---|
| `servidor` | `dc01.lab.lan` |
| `servidor_respaldo` | `192.168.1.10` |
| `puerto` | `5050` |
| `token` | `lab-lan-ciber-mensajeria` (del repositorio) |

En Windows el archivo está en `C:\ProgramData\CiberMensajeria\agente.json`.
En Linux: `/etc/ciber-mensajeria/agente.json`.
En macOS: `/Library/Application Support/CiberMensajeria/agente.json`.

Puede editar estos archivos si cambia la IP del servidor (no hace falta
reinstalar).

---

## 7. Chat entre clientes (Fase 8)

Los usuarios pueden mandarse mensajes de texto 1:1 entre equipos con el
agente gráfico (botón **Chat** en la esquina inferior izquierda, o atajo
`Ctrl+Shift+C`).

### Panel de caja

En el panel habitual (`http://localhost:8080`) hay un interruptor **Chat
entre clientes**. Caja puede activarlo o desactivarlo; **no puede leer el
contenido** de las conversaciones.

### Moderación

Para leer conversaciones, abra `http://localhost:8080/moderacion/` con la
cuenta de moderador definida en `servidor/config.json`:

- `usuario_moderador` (por defecto: `moderador`)
- `password_moderador` (contraseña distinta a `password_panel`)

Las contraseñas por defecto del laboratorio están en `servidor/config.json`:

- Panel de caja: `caja-lab`
- Moderación: usuario `moderador`, contraseña `moderador-lab`

### Debian sin escritorio

El modo consola (`wall`) no incluye chat 1:1; solo el agente con interfaz
gráfica (tkinter) puede chatear.

---

## 8. Solución de problemas rápida

| Problema | Qué revisar |
|---|---|
| El agente no aparece en el panel | ¿Resuelve `dc01.lab.lan`? (`ping dc01.lab.lan`) |
| No conecta al servidor | Firewall de DC01: puerto 5050. Desde Windows: `Test-NetConnection dc01.lab.lan -Port 5050`. Desde Linux: `nc -zv dc01.lab.lan 5050` |
| Token rechazado | El token del agente debe coincidir con `C:\CiberMensajeria\config.json` en DC01 |
| `config.json` no es JSON válido: Unexpected UTF-8 BOM | Ocurre al reinstalar el servidor con una versión antigua del instalador: PowerShell escribe el JSON con BOM y Python no lo acepta. **Solución rápida:** abra `C:\CiberMensajeria\config.json` en el Bloc de notas, **Guardar como… → Codificación: UTF-8** (sin la variante «con BOM»). **Solución permanente:** use el instalador actualizado del repositorio (ya escribe UTF-8 sin BOM) o actualice el código del servidor a una versión que lea `utf-8-sig`. |
| Acentos rotos en PowerShell | Los `.ps1` deben tener BOM UTF-8 (ya incluido en el repositorio) |
| Dos ventanas del agente | Solo una instancia por usuario; revise el log en la carpeta de logs del SO |

---

## 9. Desarrollo local (sin instaladores)

Para probar en su máquina sin instalar:

```bash
# Terminal 1 — servidor
python -m servidor --config servidor/config.json

# Terminal 2 — agente
python -m agente --config agente/config.json

# Terminal 3 — simular varios equipos
python herramientas/simular_agentes.py --n 4
```

Panel: http://localhost:8080
