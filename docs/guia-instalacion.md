# Guía de instalación — Ciber Mensajería

Esta guía explica cómo instalar el servidor y los agentes en el laboratorio
`lab.lan`. No hace falta saber programar: solo seguir los pasos en orden.

## Resumen

1. Instale el **servidor** en DC01 (Windows Server 2022).
2. Copie el **token** que muestra el instalador.
3. Instale el **agente** en cada equipo cliente con ese token.

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
   - Genera un **token aleatorio** y lo muestra en pantalla.
   - Abre el puerto **TCP 5050** en el firewall (perfiles Dominio y Privado).
   - Crea una tarea programada que arranca el servidor al iniciar Windows.
   - Crea un acceso directo en el escritorio al panel: `http://localhost:8080`.

5. **Guarde el token** en un lugar seguro. Lo necesitará para cada agente.

> **Actualizar a una versión nueva:** volver a ejecutar `instalar-servidor.ps1`
> **sobrescribe** `C:\CiberMensajeria\config.json` con un token y contraseñas
> nuevos. Si ya tiene agentes instalados, anote el token actual antes de
> actualizar, o edite solo los archivos `.py` sin volver a correr el instalador
> completo.

### Si falta Python en DC01

1. Descargue el instalador desde https://www.python.org/downloads/
2. Marque **Install for all users** y **Add python.exe to PATH**.
3. Vuelva a ejecutar `instalar-servidor.ps1`.

### Comprobar que funciona

- Abra el acceso directo **Ciber Mensajería - Panel** en el escritorio de DC01.
- Debe cargar la tabla de equipos (vacía hasta que haya agentes).
- Revise el log en `C:\CiberMensajeria\datos\servidor.log`.

---

## 2. Agente en Windows 10/11

### Paso a paso

1. Copie el proyecto al equipo (o solo la carpeta `instaladores\windows` y el código fuente).
2. Abra **PowerShell como Administrador**.
3. Ejecute (sustituya el token por el del servidor):

```powershell
cd C:\ruta\al\proyecto\instaladores\windows
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\instalar-agente.ps1 -Token "PEGUE_AQUI_EL_TOKEN"
```

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
sudo ./instalar-agente.sh --token "PEGUE_AQUI_EL_TOKEN"
```

3. El script instala `python3` y `python3-tk`, copia a `/opt/ciber-mensajeria/`,
   guarda la config en `/etc/ciber-mensajeria/agente.json` y registra el autostart
   en `/etc/xdg/autostart/` (aplica a todos los usuarios, incluidos los del dominio).

### Equipos sin escritorio (Debian servidor)

Si no hay entorno gráfico, el instalador detecta el caso y configura un **servicio
systemd** que entrega los avisos con `wall` en todas las terminales.

```bash
sudo ./instalar-agente.sh --token "PEGUE_AQUI_EL_TOKEN" --modo consola
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
sudo ./instalar-agente.sh --token "PEGUE_AQUI_EL_TOKEN"
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

## 5. Opciones comunes de configuración

Los instaladores crean un JSON con valores por defecto del laboratorio:

| Campo | Valor por defecto |
|---|---|
| `servidor` | `dc01.lab.lan` |
| `servidor_respaldo` | `192.168.1.10` |
| `puerto` | `5050` |
| `token` | el que generó / pasó el instalador |

En Windows el archivo está en `C:\ProgramData\CiberMensajeria\agente.json`.
En Linux: `/etc/ciber-mensajeria/agente.json`.
En macOS: `/Library/Application Support/CiberMensajeria/agente.json`.

Puede editar estos archivos si cambia la IP del servidor (no hace falta
reinstalar).

---

## 6. Chat entre clientes (Fase 8)

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

El instalador del servidor genera una contraseña aleatoria para el
moderador y la muestra en pantalla junto con el token de agentes.

### Debian sin escritorio

El modo consola (`wall`) no incluye chat 1:1; solo el agente con interfaz
gráfica (tkinter) puede chatear.

---

## 7. Solución de problemas rápida

| Problema | Qué revisar |
|---|---|
| El agente no aparece en el panel | ¿Resuelve `dc01.lab.lan`? (`ping dc01.lab.lan`) |
| No conecta al servidor | Firewall de DC01: puerto 5050. Desde Windows: `Test-NetConnection dc01.lab.lan -Port 5050`. Desde Linux: `nc -zv dc01.lab.lan 5050` |
| Token rechazado | El token del agente debe coincidir con `C:\CiberMensajeria\config.json` en DC01 |
| `config.json` no es JSON válido: Unexpected UTF-8 BOM | Ocurre al reinstalar el servidor con una versión antigua del instalador: PowerShell escribe el JSON con BOM y Python no lo acepta. **Solución rápida:** abra `C:\CiberMensajeria\config.json` en el Bloc de notas, **Guardar como… → Codificación: UTF-8** (sin la variante «con BOM»). **Solución permanente:** use el instalador actualizado del repositorio (ya escribe UTF-8 sin BOM) o actualice el código del servidor a una versión que lea `utf-8-sig`. |
| Acentos rotos en PowerShell | Los `.ps1` deben tener BOM UTF-8 (ya incluido en el repositorio) |
| Dos ventanas del agente | Solo una instancia por usuario; revise el log en la carpeta de logs del SO |

---

## 8. Desarrollo local (sin instaladores)

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
