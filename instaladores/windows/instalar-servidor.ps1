# Instala el servidor de Ciber Mensajería en DC01 (Windows Server 2022).
#
# Uso (PowerShell como Administrador):
#   .\instalar-servidor.ps1
#
# Copia el proyecto a C:\CiberMensajeria\, genera un token aleatorio,
# abre el puerto 5050 en el firewall y crea una tarea programada.

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

function Write-Paso {
    param([string]$Mensaje)
    Write-Host "==> $Mensaje" -ForegroundColor Cyan
}

function Buscar-Python {
    $comandos = @("python", "py")
    foreach ($cmd in $comandos) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        if ($cmd -eq "py") {
            $version = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Ejecutable = "py"; Argumentos = @("-3"); Version = $version } }
        } else {
            $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Ejecutable = "python"; Argumentos = @(); Version = $version } }
        }
    }
    return $null
}

Write-Paso "Paso 1/6: verificar Python 3.10+"
$python = Buscar-Python
if (-not $python) {
    Write-Host ""
    Write-Host "No se encontró Python 3.10 o superior." -ForegroundColor Red
    Write-Host "Instálelo desde https://www.python.org/downloads/ marcando:"
    Write-Host "  - Install for all users"
    Write-Host "  - Add python.exe to PATH"
    exit 1
}

$partes = $python.Version.Split(".")
$mayor = [int]$partes[0]
$menor = [int]$partes[1]
if ($mayor -lt 3 -or ($mayor -eq 3 -and $menor -lt 10)) {
    Write-Host "Se requiere Python 3.10+ (encontrado: $($python.Version))" -ForegroundColor Red
    exit 1
}
Write-Host "Python $($python.Version) encontrado."

$raizProyecto = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$destino = "C:\CiberMensajeria"
$config = Join-Path $destino "config.json"
$datos = Join-Path $destino "datos"

Write-Paso "Paso 2/6: copiar archivos a $destino"
New-Item -ItemType Directory -Force -Path $destino, (Join-Path $destino "comun"), (Join-Path $destino "servidor"), (Join-Path $destino "servidor\panel"), (Join-Path $destino "servidor\panel\moderacion") | Out-Null

Copy-Item -Path (Join-Path $raizProyecto "comun\*.py") -Destination (Join-Path $destino "comun") -Force
Copy-Item -Path (Join-Path $raizProyecto "servidor\*.py") -Destination (Join-Path $destino "servidor") -Force
Copy-Item -Path (Join-Path $raizProyecto "servidor\panel\*") -Destination (Join-Path $destino "servidor\panel") -Recurse -Force

Write-Paso "Paso 3/6: generar configuración con token aleatorio"
$token = [guid]::NewGuid().ToString("N")
$passwordPanel = [guid]::NewGuid().ToString("N").Substring(0, 16)
$passwordModerador = [guid]::NewGuid().ToString("N").Substring(0, 16)

$configObj = [ordered]@{
    host_agentes               = "0.0.0.0"
    puerto_agentes             = 5050
    host_panel                 = "127.0.0.1"
    puerto_panel               = 8080
    password_panel             = $passwordPanel
    token                      = $token
    avisos_minutos             = @(5, 1)
    texto_fin_sesion           = "Tu tiempo terminó, pasa a caja."
    chat_habilitado            = $true
    usuario_moderador          = "moderador"
    password_moderador       = $passwordModerador
    chat_limite_por_conversacion = 500
}
$jsonConfig = $configObj | ConvertTo-Json -Depth 5
$utf8SinBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($config, $jsonConfig, $utf8SinBom)

Write-Paso "Paso 4/6: regla de firewall (TCP 5050, Dominio y Privado)"
$nombreRegla = "Ciber Mensajeria - Agentes TCP 5050"
$regla = Get-NetFirewallRule -DisplayName $nombreRegla -ErrorAction SilentlyContinue
if ($regla) {
    Remove-NetFirewallRule -DisplayName $nombreRegla
}
New-NetFirewallRule `
    -DisplayName $nombreRegla `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5050 `
    -Profile Domain, Private `
    -Action Allow | Out-Null

Write-Paso "Paso 5/6: tarea programada al iniciar el sistema"
$nombreTarea = "CiberMensajeriaServidor"
$argumentosPython = @($python.Argumentos + @("-m", "servidor", "--config", $config, "--datos", $datos)) -join " "
$accion = New-ScheduledTaskAction -Execute $python.Ejecutable -Argument $argumentosPython -WorkingDirectory $destino
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Unregister-ScheduledTask -TaskName $nombreTarea -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $nombreTarea -Action $accion -Trigger $trigger -Principal $principal -Settings $settings -Description "Servidor de Ciber Mensajeria" | Out-Null
Start-ScheduledTask -TaskName $nombreTarea

Write-Paso "Paso 6/6: acceso directo al panel en el escritorio"
$escritorio = [Environment]::GetFolderPath("Desktop")
$url = Join-Path $escritorio "Ciber Mensajeria - Panel.url"
@"
[InternetShortcut]
URL=http://localhost:8080
"@ | Set-Content -Path $url -Encoding ASCII

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Instalación del servidor completada" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "TOKEN para los agentes (guárdelo):" -ForegroundColor Yellow
Write-Host "  $token" -ForegroundColor White
Write-Host ""
Write-Host "Moderación de chat (usuario: moderador):" -ForegroundColor Yellow
Write-Host "  $passwordModerador" -ForegroundColor White
Write-Host ""
Write-Host "Panel web: http://localhost:8080"
Write-Host "Moderación: http://localhost:8080/moderacion/"
Write-Host "Archivos:  $destino"
Write-Host "Logs:      $datos\servidor.log"
Write-Host ""
Write-Host "Use este token al instalar agentes:"
Write-Host "  .\instalar-agente.ps1 -Token $token"
