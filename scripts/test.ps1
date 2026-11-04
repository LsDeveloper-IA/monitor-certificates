# Executa a suite de testes do repositorio com um unico pytest.
#
# Uso:
#   .\scripts\test.ps1
#   .\scripts\test.ps1 -Python C:\caminho\python.exe
#   .\scripts\test.ps1 -Extra @("-k", "config")
#
# Os caminhos de teste e as opcoes do pytest ficam no pyproject.toml da raiz.

[CmdletBinding()]
param(
    [string]$Python = "",
    [string[]]$Extra = @()
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

if (-not $Python) {
    $venv = Join-Path $raiz ".venv\Scripts\python.exe"
    $Python = if (Test-Path $venv) { $venv } else { "python" }
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== pytest ===" -ForegroundColor Cyan
Push-Location $raiz
$anterior = $ErrorActionPreference
try {
    # Avisos do Python vao para stderr; nao devem abortar a execucao.
    $ErrorActionPreference = "Continue"
    & $Python -m pytest @Extra
    $codigo = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $anterior
    Pop-Location
}

if ($codigo -ne 0) {
    Write-Host "Suite de testes falhou." -ForegroundColor Red
    exit $codigo
}

Write-Host "Suite de testes passou." -ForegroundColor Green
exit 0
