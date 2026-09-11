# Desinstala el agente de Ciber Mensajería en Windows.

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "==> Deteniendo procesos del agente"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*-m agente*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "==> Quitando acceso directo de Inicio"
$vbs = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup\CiberMensajeriaAgente.vbs"
if (Test-Path $vbs) { Remove-Item $vbs -Force }

Write-Host "==> Eliminando archivos instalados"
$destino = "C:\Program Files\CiberMensajeria"
$configDir = "C:\ProgramData\CiberMensajeria"
if (Test-Path $destino) { Remove-Item $destino -Recurse -Force }
if (Test-Path $configDir) { Remove-Item $configDir -Recurse -Force }

Write-Host ""
Write-Host "Desinstalación completada."
Write-Host "Los logs en %LOCALAPPDATA%\CiberMensajeria no se borran."
