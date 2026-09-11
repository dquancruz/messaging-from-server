# Inicia el servidor de Ciber Mensajería en primer plano (consola visible).
#
# Uso:
#   .\iniciar-servidor.ps1
#   .\iniciar-servidor.ps1 -Destino C:\CiberMensajeria

param(
    [string]$Destino = "C:\CiberMensajeria"
)

$ErrorActionPreference = "Stop"

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

$config = Join-Path $Destino "config.json"
$datos = Join-Path $Destino "datos"

if (-not (Test-Path $config)) {
    Write-Host "No se encontró la configuración en $config" -ForegroundColor Red
    Write-Host "Ejecute primero instaladores\windows\instalar-servidor.ps1" -ForegroundColor Yellow
    exit 1
}

$python = Buscar-Python
if (-not $python) {
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

New-Item -ItemType Directory -Force -Path $datos | Out-Null

Write-Host "Iniciando servidor (config=$config, datos=$datos)..." -ForegroundColor Cyan
Write-Host "Panel web: http://localhost:8080" -ForegroundColor Green
Write-Host "Pulse Ctrl+C para detener." -ForegroundColor DarkGray
Write-Host ""

Set-Location $Destino
$argumentos = @($python.Argumentos + @("-m", "servidor", "--config", $config, "--datos", $datos))
& $python.Ejecutable @argumentos
