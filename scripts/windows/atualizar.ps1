param(
    [string]$InstallRoot = 'D:\Projetos\monitor-certificates',
    [string]$ServiceDirectory = 'D:\Servicos\MonitorCertificados'
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Deploy.Helpers.psm1') -Force
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$target = (Resolve-Path -LiteralPath $InstallRoot).Path
if ($source.TrimEnd('\') -eq $target.TrimEnd('\')) {
    throw 'O runner deve usar uma pasta separada da instalacao em uso.'
}
$backend = Join-Path $target 'certificados-monitor'
$frontend = Join-Path $target 'certificados-frontend'
$backendEnv = Join-Path $backend '.env'
$frontendEnv = Join-Path $frontend '.env.local'
$python = Join-Path $backend '.venv\Scripts\python.exe'
foreach ($file in @($backendEnv, $frontendEnv, $python)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Arquivo necessario ausente: $file" }
}
foreach ($name in @('MonitorCertificados', 'MonitorFrontend')) {
    if ((Get-Service $name).Status -ne 'Running') { throw "O servico $name deve estar funcionando antes da atualizacao." }
}
$key = Get-LocalSetting $backendEnv (Join-Path $ServiceDirectory 'MonitorCertificados.xml') 'AUTOMACAO_EXECUTION_KEY'
if (-not $key) { throw 'Chave interna ausente na instalacao.' }
$headers = @{ 'X-Automation-Key' = $key }

function Assert-Idle {
    foreach ($action in @('status', 'sieg-status')) {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/automacao/$action" -Headers $headers -TimeoutSec 10
        if ($status.executando) { throw 'Existe uma automacao executando. Tente atualizar depois que terminar.' }
    }
}
function Invoke-Native([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Comando falhou: $Command (codigo $LASTEXITCODE)" }
}
function Wait-Http([string]$Uri, [hashtable]$RequestHeaders = @{}) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -Headers $RequestHeaders -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw "O servico nao respondeu depois da atualizacao: $Uri"
}

Assert-Idle
$tracked = @(& git -C $source -c core.quotepath=false ls-files)
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel listar os arquivos versionados.' }
$files = @($tracked | Where-Object { Test-DeployablePath $_ })
if ($files.Count -lt 10) { throw 'Pacote de atualizacao incompleto.' }
# Build na copia do runner, enquanto a instalacao atual continua disponivel.
$buildDir = Join-Path $source 'certificados-frontend'
if (Test-Path -LiteralPath (Join-Path $buildDir '.env.local')) {
    throw 'O checkout do runner deve estar sem .env.local. Mantenha segredos somente na instalacao.'
}
$backendUrl = Get-LocalSetting $frontendEnv (Join-Path $ServiceDirectory 'MonitorFrontend.xml') 'BACKEND_URL'
if ($backendUrl -notmatch '^http://(127\.0\.0\.1|localhost):5000/?$') { throw 'BACKEND_URL deve apontar para o backend local na porta 5000.' }
$previousUrl = $env:BACKEND_URL
try {
    $env:BACKEND_URL = $backendUrl
    Push-Location $buildDir
    try {
        Invoke-Native 'npm.cmd' @('ci', '--legacy-peer-deps', '--no-audit', '--no-fund')
        Invoke-Native 'npm.cmd' @('run', 'build')
    } finally { Pop-Location }
} finally { $env:BACKEND_URL = $previousUrl }

Assert-Idle
$revision = (& git -C $source rev-parse HEAD).Trim()
$backup = Join-Path (Split-Path -Parent $target) ('monitor-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $revision.Substring(0, 7))
New-Item -ItemType Directory -Path $backup | Out-Null
$existing = @()
$newFiles = @()
$wasStopped = $false
$buildMoved = $false
try {
    Stop-Service MonitorFrontend -ErrorAction Stop
    (Get-Service MonitorFrontend).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
    Assert-Idle
    Stop-Service MonitorCertificados -ErrorAction Stop
    $wasStopped = $true
    (Get-Service MonitorCertificados).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
    foreach ($relative in $files) {
        $dest = Get-SafeChildPath $target $relative
        $saved = Get-SafeChildPath $backup $relative
        if (Test-Path -LiteralPath $dest) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
            Copy-Item -LiteralPath $dest -Destination $saved
            $existing += $relative
        } else { $newFiles += $relative }
    }
    $liveBuild = Join-Path $frontend '.next'
    if (Test-Path -LiteralPath $liveBuild) {
        Move-Item -LiteralPath $liveBuild -Destination (Join-Path $backup 'frontend-build')
        $buildMoved = $true
    }
    foreach ($relative in $files) {
        $dest = Get-SafeChildPath $target $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath (Get-SafeChildPath $source $relative) -Destination $dest -Force
    }
    Invoke-Native $python @('-m', 'pip', 'install', '-r', (Join-Path $backend 'requirements.txt'))
    Push-Location $frontend
    try { Invoke-Native 'npm.cmd' @('ci', '--legacy-peer-deps', '--no-audit', '--no-fund') }
    finally { Pop-Location }
    Copy-Item -LiteralPath (Join-Path $buildDir '.next') -Destination $liveBuild -Recurse
    Start-Service MonitorCertificados
    Wait-Http 'http://127.0.0.1:5000/api/automacao/status' $headers
    Start-Service MonitorFrontend
    Wait-Http 'http://127.0.0.1:3000'
    $admin = Get-LocalSetting $frontendEnv (Join-Path $ServiceDirectory 'MonitorFrontend.xml') 'AUTOMACAO_ADMIN_KEY'
    Wait-Http 'http://127.0.0.1:3000/api/automacao/status' @{ 'X-Admin-Key' = $admin }
    [IO.File]::WriteAllText((Join-Path $backup 'commit-instalado.txt'), $revision)
    Write-Host "Atualizacao concluida: $revision. Backup em $backup"
} catch {
    $reason = $_
    if ($wasStopped) {
        Write-Warning 'Falha na atualizacao. Recuperando os arquivos da versao anterior.'
        try {
            Stop-Service MonitorFrontend -ErrorAction SilentlyContinue
            Stop-Service MonitorCertificados -ErrorAction SilentlyContinue
            (Get-Service MonitorFrontend).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
            (Get-Service MonitorCertificados).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(60))
            foreach ($relative in $existing) {
                Copy-Item -LiteralPath (Get-SafeChildPath $backup $relative) -Destination (Get-SafeChildPath $target $relative) -Force
            }
            foreach ($relative in $newFiles) {
                $dest = Get-SafeChildPath $target $relative
                if (Test-Path -LiteralPath $dest -PathType Leaf) { Remove-Item -LiteralPath $dest }
            }
            if ($buildMoved) {
                if (Test-Path -LiteralPath $liveBuild) {
                    Move-Item -LiteralPath $liveBuild -Destination (Join-Path $backup 'build-com-falha')
                }
                Move-Item -LiteralPath (Join-Path $backup 'frontend-build') -Destination $liveBuild
            }
            Invoke-Native $python @('-m', 'pip', 'install', '-r', (Join-Path $backend 'requirements.txt'))
            Push-Location $frontend
            try { Invoke-Native 'npm.cmd' @('ci', '--legacy-peer-deps', '--no-audit', '--no-fund') }
            finally { Pop-Location }
            Start-Service MonitorCertificados
            Start-Service MonitorFrontend
            Write-Warning 'Versao anterior restaurada. Confira os servicos e o log do workflow.'
        } catch { Write-Warning "Recuperacao automatica incompleta. Backup: $backup. Confira os servicos." }
    } else { Start-Service MonitorFrontend -ErrorAction SilentlyContinue }
    throw $reason
}
