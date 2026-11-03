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
$SYNC = Join-Path $BASE "scripts\sincronizar_complementos.py"

if (!(Test-Path $ORCHESTRATOR)) {
    throw "No existe scripts\ejecutar_actualizacion_principal.py"
}
if (!(Test-Path $SYNC)) {
    throw "No existe scripts\sincronizar_complementos.py"
}

Write-Host "[1/2] Ejecutando alimentador principal y validaciones..."
& $PYTHON $ORCHESTRATOR
if ($LASTEXITCODE -ne 0) {
    throw "Falló ejecutar_actualizacion_principal.py (código $LASTEXITCODE)."
}

Write-Host ""
Write-Host "[2/2] Reconciliando MAGNA, IPTVSV y Pluto LATAM/ES/MX..."
& $PYTHON $SYNC
if ($LASTEXITCODE -ne 0) {
    throw "Falló sincronizar_complementos.py (código $LASTEXITCODE)."
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
