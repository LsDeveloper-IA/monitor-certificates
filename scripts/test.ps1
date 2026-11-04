# Executa todas as suites de teste do repositorio.
#
# Uso:
#   .\scripts\test.ps1
#   .\scripts\test.ps1 -Python C:\caminho\python.exe
#
# O script continua apos uma suite falhar para mostrar todos os resultados e
# termina com codigo 1 se qualquer suite falhar.

[CmdletBinding()]
param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

if (-not $Python) {
    $venv = Join-Path $raiz ".venv\Scripts\python.exe"
    $Python = if (Test-Path $venv) { $venv } else { "python" }
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$suites = @(
    @{
        Nome = "backend"
        Pasta = "certificados-monitor"
        Argumentos = @("-m", "unittest", "discover", "-s", "tests")
    },
    @{
        Nome = "automacao-sieg"
        Pasta = "automacao-sieg"
        Argumentos = @("-m", "unittest", "discover", "-s", "tests")
    },
    @{
        Nome = "Auto_NC"
        Pasta = "Auto_NC"
        Argumentos = @("-m", "unittest", "discover", "-s", "tests")
    },
    @{
        Nome = "sieg_comum"
        Pasta = "."
        Argumentos = @("-m", "unittest", "discover", "-s", "sieg_comum/tests")
    }
)

$falhas = @()
$inicio = Get-Date

foreach ($suite in $suites) {
    Write-Host ""
    Write-Host ("=== {0} ===" -f $suite.Nome) -ForegroundColor Cyan
    Push-Location (Join-Path $raiz $suite.Pasta)
    $anterior = $ErrorActionPreference
    try {
        # Avisos do Python vao para stderr; nao devem abortar a execucao.
        $ErrorActionPreference = "Continue"
        $argumentos = $suite.Argumentos
        & $Python @argumentos
        $codigo = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $anterior
        Pop-Location
    }
    if ($codigo -ne 0) {
        $falhas += $suite.Nome
    }
}

$duracao = (Get-Date) - $inicio
Write-Host ""
if ($falhas.Count -gt 0) {
    Write-Host ("Falhas: {0}" -f ($falhas -join ", ")) -ForegroundColor Red
    exit 1
}

Write-Host ("Todas as suites passaram em {0:N1}s." -f $duracao.TotalSeconds) -ForegroundColor Green
exit 0
