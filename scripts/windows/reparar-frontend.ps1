<#
.SYNOPSIS
    Reconstroi o frontend Next.js instalado no servidor.

.DESCRIPTION
    Corrige o "Internal Server Error" causado por build incompleto, .next
    antigo ou node_modules com versao diferente do package-lock.

    O script:
      1. para o servico MonitorFrontend;
      2. guarda .next e node_modules em uma pasta de backup;
      3. executa npm ci e npm run build na instalacao;
      4. inicia o servico e confirma que a pagina inicial responde 200;
      5. em caso de falha, restaura o backup automaticamente.

    Nao altera .env, .env.local, banco, storage nem os XMLs dos servicos.

.EXAMPLE
    .\scripts\windows\reparar-frontend.ps1

.EXAMPLE
    .\scripts\windows\reparar-frontend.ps1 -InstallRoot 'D:\Projetos\monitor-certificates'
#>
param(
    [string]$InstallRoot = 'D:\Projetos\monitor-certificates',
    [string]$ServiceDirectory = 'D:\Servicos\MonitorCertificados',
    [string]$ServiceName = 'MonitorFrontend',
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 5000
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Deploy.Helpers.psm1') -Force

$frontend = Join-Path $InstallRoot 'certificados-frontend'
$envFile = Join-Path $frontend '.env.local'
$serviceXml = Join-Path $ServiceDirectory "$ServiceName.xml"
$buildLog = $null
$backup = $null

function Escrever([string]$Texto, [string]$Cor = 'Gray') {
    Write-Host $Texto -ForegroundColor $Cor
}

function Executar([string]$Descricao, [string[]]$Argumentos) {
    Escrever ""
    Escrever "==> $Descricao" -Cor Cyan
    & npm.cmd @Argumentos 2>&1 | Tee-Object -FilePath $buildLog -Append
    if ($LASTEXITCODE -ne 0) {
        throw "$Descricao falhou (codigo $LASTEXITCODE). Log: $buildLog"
    }
}

function Aguardar-Http([string]$Url, [int]$Tentativas = 60) {
    for ($i = 0; $i -lt $Tentativas; $i++) {
        try {
            $resposta = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($resposta.StatusCode -eq 200) { return $true }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Mover-ComEspera([string]$Origem, [string]$Destino) {
    for ($i = 0; $i -lt 10; $i++) {
        try {
            Move-Item -LiteralPath $Origem -Destination $Destino -ErrorAction Stop
            return
        }
        catch {
            if ($i -eq 9) { throw }
            Start-Sleep -Seconds 1
        }
    }
}

$servico = Get-Service $ServiceName -ErrorAction SilentlyContinue
if (-not $servico) { throw "Servico $ServiceName nao encontrado." }
if (-not (Test-Path -LiteralPath $frontend -PathType Container)) {
    throw "Pasta do frontend nao encontrada: $frontend"
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd nao encontrado no PATH. Instale Node.js 22 LTS no servidor."
}

$backendUrl = Get-LocalSetting $envFile $serviceXml 'BACKEND_URL'
if (-not $backendUrl) { $backendUrl = "http://127.0.0.1:$BackendPort" }
# No Windows, "localhost" pode resolver para ::1 enquanto o Flask escuta em
# 127.0.0.1. Usar o IP literal evita ECONNREFUSED e o 500 no proxy.
if ($backendUrl -match ('^http://localhost:{0}/?$' -f $BackendPort)) {
    $backendUrl = "http://127.0.0.1:$BackendPort"
}
if ($backendUrl -notmatch ('^http://127\.0\.0\.1:{0}/?$' -f $BackendPort)) {
    throw "BACKEND_URL inesperado: $backendUrl. Use http://127.0.0.1:$BackendPort"
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path (Split-Path -Parent $InstallRoot) "monitor-backup-frontend-$timestamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$buildLog = Join-Path $backup 'build.log'
$nextBuild = Join-Path $frontend '.next'
$nodeModules = Join-Path $frontend 'node_modules'
$backupNext = Join-Path $backup '.next'
$backupModules = Join-Path $backup 'node_modules'
$buildMoved = $false
$modulesMoved = $false
$wasRunning = $servico.Status -eq 'Running'

Escrever "Instalacao: $InstallRoot"
Escrever "Backup:     $backup"
Escrever "BACKEND_URL usado no build: $backendUrl"

try {
    if ($wasRunning) {
        Escrever ""
        Escrever "==> Parando $ServiceName" -Cor Cyan
        Stop-Service $ServiceName -ErrorAction Stop
        (Get-Service $ServiceName).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
    }

    if (Test-Path -LiteralPath $nextBuild) {
        Mover-ComEspera $nextBuild $backupNext
        $buildMoved = $true
    }
    if (Test-Path -LiteralPath $nodeModules) {
        Escrever "==> Movendo node_modules para o backup" -Cor Cyan
        Mover-ComEspera $nodeModules $backupModules
        $modulesMoved = $true
    }

    $anteriores = @{
        BACKEND_URL = $env:BACKEND_URL
        NEXT_STATIC_EXPORT = $env:NEXT_STATIC_EXPORT
        NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN = $env:NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN
        NEXT_TELEMETRY_DISABLED = $env:NEXT_TELEMETRY_DISABLED
    }
    try {
        $env:BACKEND_URL = $backendUrl
        $env:NEXT_TELEMETRY_DISABLED = '1'
        Remove-Item Env:NEXT_STATIC_EXPORT -ErrorAction SilentlyContinue
        Remove-Item Env:NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN -ErrorAction SilentlyContinue

        Push-Location $frontend
        try {
            Executar 'Instalando dependencias (npm ci)' @('ci', '--legacy-peer-deps', '--no-audit', '--no-fund')
            Executar 'Gerando o build de producao (npm run build)' @('run', 'build')
        }
        finally {
            Pop-Location
        }
    }
    finally {
        foreach ($nome in $anteriores.Keys) {
            $valor = $anteriores[$nome]
            if ($null -eq $valor) {
                Remove-Item "Env:$nome" -ErrorAction SilentlyContinue
            }
            else {
                Set-Item "Env:$nome" -Value $valor
            }
        }
    }

    Escrever ""
    Escrever "==> Iniciando $ServiceName" -Cor Cyan
    Start-Service $ServiceName -ErrorAction Stop

    $endereco = "http://127.0.0.1:$FrontendPort/"
    if (-not (Aguardar-Http $endereco)) {
        throw "O frontend nao respondeu 200 em $endereco apos o build."
    }

    Escrever ""
    Escrever "Frontend reconstruido e respondendo em $endereco" -Cor Green
    Escrever "Backup do build anterior: $backupNext" -Cor Green
    if ($modulesMoved) {
        # Os node_modules antigos nao sao mais necessarios apos o build novo.
        Remove-Item -LiteralPath $backupModules -Recurse -Force -ErrorAction SilentlyContinue
    }
    Escrever "Log do build: $buildLog" -Cor Green
}
catch {
    $motivo = $_
    Escrever ""
    Escrever "FALHA: $motivo" -Cor Red
    Escrever "Restaurando a versao anterior..." -Cor Yellow
    try {
        Stop-Service $ServiceName -ErrorAction SilentlyContinue
        (Get-Service $ServiceName).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
        if (Test-Path -LiteralPath $nextBuild) {
            Remove-Item -LiteralPath $nextBuild -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($buildMoved -and (Test-Path -LiteralPath $backupNext)) {
            Mover-ComEspera $backupNext $nextBuild
        }
        if (Test-Path -LiteralPath $nodeModules) {
            Remove-Item -LiteralPath $nodeModules -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($modulesMoved -and (Test-Path -LiteralPath $backupModules)) {
            Mover-ComEspera $backupModules $nodeModules
        }
        if ($wasRunning) { Start-Service $ServiceName -ErrorAction SilentlyContinue }
        Escrever "Versao anterior restaurada. Backup mantido em: $backup" -Cor Yellow
    }
    catch {
        Escrever "A restauracao automatica falhou. Backup: $backup" -Cor Red
    }
    Escrever "Envie o arquivo $buildLog para analise." -Cor Yellow
    throw $motivo
}
