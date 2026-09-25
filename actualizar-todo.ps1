# ============================================================
# IPTV CHILE MASTER - ACTUALIZACION TODO EN UNO
# ============================================================

$ErrorActionPreference = "Stop"

# Ir siempre a la carpeta donde está este script
$BASE = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BASE

$PYTHON = "C:\Users\ByD4rk\AppData\Local\Programs\Python\Python313\python.exe"

Write-Host ""
Write-Host "============================================================"
Write-Host "        IPTV CHILE MASTER - ACTUALIZACION COMPLETA"
Write-Host "============================================================"
Write-Host ""

# ------------------------------------------------------------
# Comprobar archivos
# ------------------------------------------------------------

if (!(Test-Path $PYTHON)) {
    Write-Host "ERROR: No se encontró Python:"
    Write-Host $PYTHON
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

if (!(Test-Path "$BASE\scripts\actualizar_principal.py")) {
    Write-Host "ERROR: No existe scripts\actualizar_principal.py"
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

if (!(Test-Path "$BASE\scripts\mega_lista.py")) {
    Write-Host "ERROR: No existe scripts\mega_lista.py"
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

# ============================================================
# 1. ACTUALIZAR LISTA PRINCIPAL
# ============================================================

Write-Host "[1/3] Actualizando lista principal..."
Write-Host ""

& $PYTHON "$BASE\scripts\actualizar_principal.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: actualizar_principal.py fallo."
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

# ============================================================
# 2. GENERAR LISTA GOD
# ============================================================

Write-Host ""
Write-Host "[2/3] Generando lista GOD..."
Write-Host ""

& $PYTHON "$BASE\scripts\mega_lista.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: mega_lista.py fallo."
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

# ============================================================
# 3. SUBIR TODO A GITHUB
# ============================================================

Write-Host ""
Write-Host "[3/3] Guardando cambios en GitHub..."
Write-Host ""

git add .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: git add fallo."
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

# Comprobar si hay cambios
git diff --cached --quiet

if ($LASTEXITCODE -ne 0) {

    git commit -m "Actualizar listas IPTV"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: git commit fallo."
        Read-Host "Pulsa ENTER para cerrar"
        exit 1
    }

} else {

    Write-Host "No hay cambios nuevos para subir."
}

# Traer cambios de GitHub antes de subir
Write-Host ""
Write-Host "Sincronizando con GitHub..."

git pull --rebase origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: git pull --rebase fallo."
    Write-Host "Puede haber un conflicto que necesita revisión."
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

# Subir
Write-Host ""
Write-Host "Subiendo cambios..."

git push origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: git push fallo."
    Read-Host "Pulsa ENTER para cerrar"
    exit 1
}

# ============================================================
# FINAL
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host "          ACTUALIZACION TERMINADA CORRECTAMENTE"
Write-Host "============================================================"
Write-Host ""

git status

Write-Host ""
Write-Host "Todo listo."
Write-Host ""

Read-Host "Pulsa ENTER para cerrar"