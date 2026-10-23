$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonProyecto = Join-Path $PSScriptRoot '.venv-cellpose\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProyecto)) {
    $pythonProyecto = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonProyecto)) {
    throw 'Falta instalar el entorno Python. Consulta README.md.'
}
$env:CELLPOSE_LOCAL_MODELS_PATH = Join-Path $PSScriptRoot 'data\models'
& $pythonProyecto -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
