# ============================================================
# IPTV CHILE MASTER - ACTUALIZAR LISTA PRINCIPAL
# ============================================================

$ErrorActionPreference = "Stop"

$BASE = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BASE

$PYTHON_CMD = Get-Command python -ErrorAction SilentlyContinue
if (!$PYTHON_CMD) {
    $PYTHON_CMD = Get-Command py -ErrorAction SilentlyContinue
}
if (!$PYTHON_CMD) {
    throw "No se encontró Python en PATH. Instala Python o agrega python.exe al PATH."
}
$PYTHON = $PYTHON_CMD.Source

Write-Host ""
Write-Host "============================================================"
Write-Host "       IPTV CHILE MASTER - ACTUALIZAR LISTA PRINCIPAL"
Write-Host "============================================================"
Write-Host ""

$ORCHESTRATOR = Join-Path $BASE "scripts\ejecutar_actualizacion_principal.py"
if (!(Test-Path $ORCHESTRATOR)) {
    throw "No existe scripts\ejecutar_actualizacion_principal.py"
}

Write-Host "[1/1] Ejecutando alimentador, unificación, sincronización y auditoría de orden..."
& $PYTHON $ORCHESTRATOR
if ($LASTEXITCODE -ne 0) {
    throw "Falló ejecutar_actualizacion_principal.py (código $LASTEXITCODE)."
}

Write-Host ""
Write-Host "============================================================"
Write-Host "ACTUALIZACIÓN LOCAL DE LA LISTA PRINCIPAL TERMINADA"
Write-Host "============================================================"
Write-Host "No se generó ni modificó la lista GOD."
Write-Host "No se modificó el Generador ni las playlists regionales Pluto."
Write-Host "No se hizo commit ni push a main."
Write-Host ""
Write-Host "Cambios locales pendientes de revisión:"
git status --short
