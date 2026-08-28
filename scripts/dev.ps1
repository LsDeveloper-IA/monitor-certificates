$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot "certificados-monitor"
$frontendDir = Join-Path $projectRoot "certificados-frontend"
$runtimeDir = Join-Path $backendDir "runtime"
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$nextExe = Join-Path $frontendDir "node_modules\.bin\next.cmd"

if (-not (Test-Path -LiteralPath $nextExe)) {
    throw "Dependências do frontend não encontradas. Execute npm install em certificados-frontend."
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$backendStdout = Join-Path $runtimeDir "backend.stdout.log"
$backendStderr = Join-Path $runtimeDir "backend.stderr.log"

$backendProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @(
        "-m", "flask", "--app", "src.main", "run",
        "--host", "127.0.0.1", "--port", "5000",
        "--no-debugger", "--no-reload"
    ) `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendStdout `
    -RedirectStandardError $backendStderr `
    -PassThru

$backendReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:5000/api/certificados" `
            -TimeoutSec 1
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {
        if ($backendProcess.HasExited) {
            break
        }
        Start-Sleep -Milliseconds 250
    }
}

if (-not $backendReady) {
    $details = if (Test-Path -LiteralPath $backendStderr) {
        (Get-Content -Tail 15 -LiteralPath $backendStderr) -join [Environment]::NewLine
    } else {
        "Nenhum detalhe foi registrado."
    }
    throw "O backend não iniciou na porta 5000.`n$details"
}

Write-Host "Backend pronto em http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "Frontend iniciando em http://localhost:3000" -ForegroundColor Green

try {
    Push-Location $frontendDir
    & $nextExe dev --turbopack
} finally {
    Pop-Location
    if (-not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force
    }
}
