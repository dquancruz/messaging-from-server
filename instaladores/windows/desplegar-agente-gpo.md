# Desplegar el agente con una GPO de inicio de sesión

Este documento describe cómo instalar el agente en todos los equipos Windows
del dominio `lab.lan` sin ir máquina por máquina.

## Requisitos previos

1. El servidor ya está instalado en DC01 y tienes el **token** del agente.
2. Los equipos Windows están unidos al dominio.
3. Tienes permisos para crear GPOs en el dominio.

## Paso 1 — Carpeta compartida en DC01

1. Copia el proyecto (o al menos `instaladores/windows/instalar-agente.ps1` y
   el código del agente) a una carpeta compartida, por ejemplo:
   `\\dc01.lab.lan\CiberMensajeria$`
2. Da permiso de lectura a **Equipos del dominio** (`Domain Computers`).

## Paso 2 — Script de inicio de sesión

Crea `\\dc01.lab.lan\CiberMensajeria$\gpo-iniciar-agente.ps1`:

```powershell
# GPO: ejecutar al iniciar sesión cualquier usuario del dominio
$Token = "PEGA-AQUI-EL-TOKEN"
$Instalador = "\\dc01.lab.lan\CiberMensajeria$\instaladores\windows\instalar-agente.ps1"
if (-not (Test-Path "C:\Program Files\CiberMensajeria\agente\__main__.py")) {
    & powershell.exe -ExecutionPolicy Bypass -File $Instalador -Token $Token
}
```

Sustituye el token por el que generó `instalar-servidor.ps1`.

## Paso 3 — Crear la GPO

1. En **Administrador del servidor** → **Herramientas** → **Administración de directivas de grupo**.
2. Clic derecho en el dominio `lab.lan` → **Crear un objeto de directiva de grupo en este dominio y enlazarlo aquí**.
3. Nombre sugerido: `Ciber Mensajería — Agente`.
4. Edita la GPO:
   - **Configuración del equipo** no es necesaria.
   - **Configuración de usuario** → **Directivas** → **Plantillas administrativas** → **Sistema** → **Scripts** → **Iniciar sesión** → **Agregar** → ruta del `.ps1` en la carpeta compartida.
5. Enlaza la GPO al OU donde están los equipos de alumnos (o al dominio entero).

## Paso 4 — Probar

1. En un Windows de prueba: `gpupdate /force` y cierra sesión.
2. Inicia sesión con un usuario del dominio.
3. Comprueba en el panel del servidor que el equipo aparece conectado.

## Solución de problemas

| Síntoma | Qué revisar |
|---|---|
| No arranca el script | En el visor de eventos del cliente, origen **Microsoft-Windows-GroupPolicy** |
| Python no instalado | Ejecuta `instalar-agente.ps1` una vez a mano en ese equipo |
| Token incorrecto | El agente se conecta pero el servidor lo rechaza; revisa `config.json` en `C:\ProgramData\CiberMensajeria\` |
