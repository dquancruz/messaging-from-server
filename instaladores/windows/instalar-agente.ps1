# Instala el agente de Ciber Mensajería en Windows 10/11.
#
# Uso (PowerShell como Administrador):
#   .\instalar-agente.ps1
#   .\instalar-agente.ps1 -Token OTRO_TOKEN

#Requires -RunAsAdministrator

param(
    [string]$Token = "",

    [string]$Servidor = "dc01.lab.lan",
    [string]$Respaldo = "192.168.1.10"
)

$ErrorActionPreference = "Stop"

function Write-Paso {
    param([string]$Mensaje)
    Write-Host "==> $Mensaje" -ForegroundColor Cyan
}

function Buscar-Python {
    $candidatos = @()
    $comandos = @("python", "py")
    foreach ($cmd in $comandos) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        if ($cmd -eq "py") {
            $rutaPy = & py -3 -c "import sys; print(sys.executable)" 2>$null
            $version = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $candidatos += @{ Ejecutable = $rutaPy.Trim(); Launcher = "py"; ArgumentosLauncher = @("-3"); Version = $version }
            }
        } else {
            $rutaPy = & python -c "import sys; print(sys.executable)" 2>$null
            $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $candidatos += @{ Ejecutable = $rutaPy.Trim(); Launcher = "python"; ArgumentosLauncher = @(); Version = $version }
            }
        }
    }
    return $candidatos
}

function Instalar-PythonConWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { return $false }
    Write-Host "Intentando instalar Python con winget..."
    & winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    return ($LASTEXITCODE -eq 0)
}

$raizProyecto = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Token) {
    $configAgenteOrigen = Join-Path $raizProyecto "agente\config.json"
    if (-not (Test-Path $configAgenteOrigen)) {
        Write-Host "No se encontró $configAgenteOrigen y no se pasó -Token." -ForegroundColor Red
        exit 1
    }
    $Token = (Get-Content -Path $configAgenteOrigen -Raw | ConvertFrom-Json).token
    Write-Host "Usando token del repositorio: $Token"
}

Write-Paso "Paso 1/5: verificar Python 3.10+"
$python = Buscar-Python | Select-Object -First 1
if (-not $python) {
    if (-not (Instalar-PythonConWinget)) {
        Write-Host ""
        Write-Host "No se encontró Python 3.10+." -ForegroundColor Red
        Write-Host "Opciones:"
        Write-Host "  1. Instale Python desde https://www.python.org/downloads/"
        Write-Host "  2. Si tiene winget: winget install Python.Python.3.12"
        exit 1
    }
    $python = Buscar-Python | Select-Object -First 1
}

$partes = $python.Version.Split(".")
$mayor = [int]$partes[0]
$menor = [int]$partes[1]
if ($mayor -lt 3 -or ($mayor -eq 3 -and $menor -lt 10)) {
    Write-Host "Se requiere Python 3.10+ (encontrado: $($python.Version))" -ForegroundColor Red
    exit 1
}

$pythonw = Join-Path (Split-Path $python.Ejecutable -Parent) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Host "No se encontró pythonw.exe junto a Python." -ForegroundColor Red
    exit 1
}
Write-Host "Python $($python.Version) en $($python.Ejecutable)"

$destino = "C:\Program Files\CiberMensajeria"
$configDir = "C:\ProgramData\CiberMensajeria"
$config = Join-Path $configDir "agente.json"

Write-Paso "Paso 2/5: copiar archivos a $destino"
New-Item -ItemType Directory -Force -Path $destino, (Join-Path $destino "agente"), (Join-Path $destino "comun") | Out-Null
Copy-Item -Path (Join-Path $raizProyecto "agente\*.py") -Destination (Join-Path $destino "agente") -Force
Copy-Item -Path (Join-Path $raizProyecto "comun\*.py") -Destination (Join-Path $destino "comun") -Force

Write-Paso "Paso 3/5: crear configuración en $config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$configObj = [ordered]@{
    servidor          = $Servidor
    servidor_respaldo = $Respaldo
    puerto            = 5050
    token             = $Token
    bloqueo_nativo    = $false
}
$configObj | ConvertTo-Json -Depth 5 | Set-Content -Path $config -Encoding UTF8

Write-Paso "Paso 4/5: acceso directo en Inicio común (todos los usuarios)"
$inicioComun = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"
New-Item -ItemType Directory -Force -Path $inicioComun | Out-Null
$vbs = Join-Path $inicioComun "CiberMensajeriaAgente.vbs"
$argumentos = "--config `"$config`""
@"
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "$destino"
sh.Run """$pythonw"" -m agente $argumentos", 0, False
"@ | Set-Content -Path $vbs -Encoding ASCII

Write-Paso "Paso 5/5: iniciar agente en la sesión actual"
Start-Process -FilePath $pythonw -ArgumentList @("-m", "agente", "--config", $config) -WorkingDirectory $destino -WindowStyle Hidden

Write-Host ""
Write-Host "Instalación del agente completada." -ForegroundColor Green
Write-Host "  Archivos: $destino"
Write-Host "  Config:   $config"
Write-Host "  Arranque: $vbs"
Write-Host ""
Write-Host "El agente se iniciará automáticamente al iniciar sesión cualquier usuario del equipo."
