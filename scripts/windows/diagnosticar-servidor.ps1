<#
.SYNOPSIS
    Diagnostica o "Internal Server Error" no painel e no backend.

.DESCRIPTION
    Execute no servidor Windows (o mesmo dos servicos MonitorFrontend e
    MonitorCertificados). O script:

      - mostra o estado dos servicos e das portas 3000/5000;
      - testa a pagina inicial, a API pelo Next e a API direto no Flask;
      - indica qual camada esta falhando;
      - lista os logs recentes, ocultando chaves e tokens.

    Nada e alterado e nenhum segredo e impresso.

.EXAMPLE
    .\scripts\windows\diagnosticar-servidor.ps1
#>
param(
    [string]$InstallRoot = 'D:\Projetos\monitor-certificates',
    [string]$ServiceDirectory = 'D:\Servicos\MonitorCertificados',
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 5000
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Deploy.Helpers.psm1') -Force

$frontendEnv = Join-Path $InstallRoot 'certificados-frontend\.env.local'
$frontendXml = Join-Path $ServiceDirectory 'MonitorFrontend.xml'
$backendEnv = Join-Path $InstallRoot 'certificados-monitor\.env'
$backendXml = Join-Path $ServiceDirectory 'MonitorCertificados.xml'

function Escrever([string]$Texto, [string]$Cor = 'Gray') {
    Write-Host $Texto -ForegroundColor $Cor
}

function Testar-Http([string]$Descricao, [string]$Url, [hashtable]$Headers = @{}) {
    Escrever ""
    Escrever $Descricao -Cor Cyan
    try {
        $resposta = Invoke-WebRequest -UseBasicParsing -Uri $Url -Headers $Headers -TimeoutSec 15
        Escrever ("  HTTP {0}" -f $resposta.StatusCode) -Cor Green
        return [pscustomobject]@{ Ok = $true; Status = [int]$resposta.StatusCode; Corpo = $resposta.Content }
    }
    catch {
        $status = $null
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        if ($null -eq $status) {
            Escrever "  sem resposta (servico parado ou porta fechada)" -Cor Red
            return [pscustomobject]@{ Ok = $false; Status = 0; Corpo = '' }
        }
        Escrever ("  HTTP {0}" -f $status) -Cor Red
        $corpo = ''
        if ($_.ErrorDetails.Message) { $corpo = [string]$_.ErrorDetails.Message }
        return [pscustomobject]@{ Ok = $false; Status = $status; Corpo = $corpo }
    }
}

function Ocultar-Segredos([string]$Texto) {
    $Texto = [regex]::Replace(
        $Texto,
        '(?im)((?:key|token|senha|password|secret|authorization)[^=:\s]*\s*[=:]\s*)\S+',
        '$1***'
    )
    return [regex]::Replace($Texto, '(?i)Bearer\s+\S+', 'Bearer ***')
}

Escrever "Diagnostico do Monitor de Certificados" -Cor Cyan
Escrever "Instalacao: $InstallRoot"
Escrever "Servicos:   $ServiceDirectory"

Escrever ""
Escrever "Servicos" -Cor Cyan
foreach ($nome in @('MonitorCertificados', 'MonitorFrontend')) {
    $servico = Get-Service $nome -ErrorAction SilentlyContinue
    if (-not $servico) {
        Escrever ("  {0}: NAO INSTALADO" -f $nome) -Cor Red
    }
    elseif ($servico.Status -eq 'Running') {
        Escrever ("  {0}: {1}" -f $nome, $servico.Status) -Cor Green
    }
    else {
        Escrever ("  {0}: {1}" -f $nome, $servico.Status) -Cor Red
    }
}

Escrever ""
Escrever "Portas" -Cor Cyan
foreach ($porta in @($FrontendPort, $BackendPort)) {
    $escuta = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue
    if ($escuta) {
        Escrever ("  {0}: escutando (PID {1})" -f $porta, ($escuta.OwningProcess -join ',')) -Cor Green
    }
    else {
        Escrever ("  {0}: ninguem escutando" -f $porta) -Cor Red
    }
}

$chaveAdmin = ''
if ((Test-Path -LiteralPath $frontendEnv) -or (Test-Path -LiteralPath $frontendXml)) {
    $chaveAdmin = Get-LocalSetting $frontendEnv $frontendXml 'AUTOMACAO_ADMIN_KEY'
}
$cabecalhosAdmin = @{}
if ($chaveAdmin) { $cabecalhosAdmin['X-Admin-Key'] = $chaveAdmin }

$raiz = Testar-Http 'Pagina inicial pelo Next' ("http://127.0.0.1:{0}/" -f $FrontendPort)
$apiNext = Testar-Http 'API de certificados pelo Next' ("http://127.0.0.1:{0}/api/certificados" -f $FrontendPort)
$automacao = Testar-Http 'Automacao pelo Next' ("http://127.0.0.1:{0}/api/automacao/status" -f $FrontendPort) $cabecalhosAdmin
$apiFlask = Testar-Http 'API de certificados direto no Flask' ("http://127.0.0.1:{0}/api/certificados" -f $BackendPort)

Escrever ""
Escrever "Conclusao" -Cor Cyan
if ($raiz.Status -eq 500) {
    Escrever "  O Next esta retornando 500 na pagina inicial: o build do frontend esta" -Cor Red
    Escrever "  quebrado ou foi gerado com dependencias diferentes. Rode:" -Cor Red
    Escrever "    .\scripts\windows\reparar-frontend.ps1" -Cor Yellow
}
elseif ($raiz.Ok -and $apiFlask.Status -eq 0) {
    Escrever "  A pagina abre, mas o Flask nao responde na porta $BackendPort." -Cor Red
    Escrever "  Inicie o MonitorCertificados e veja storage\logs\erro-inicializacao.log." -Cor Yellow
}
elseif ($raiz.Ok -and $apiFlask.Ok -and $apiNext.Status -eq 500) {
    Escrever "  O Flask responde, mas o proxy do Next devolve 500." -Cor Red
    Escrever "  Confira BACKEND_URL no .env.local: use http://127.0.0.1:$BackendPort" -Cor Yellow
    Escrever "  (evite localhost, que pode resolver para IPv6 no Windows)." -Cor Yellow
    Escrever "  Depois rode .\scripts\windows\reparar-frontend.ps1." -Cor Yellow
}
elseif ($raiz.Ok -and $apiFlask.Ok -and $apiNext.Ok) {
    Escrever "  Pagina, backend e proxy estao respondendo. Se o erro aparece em uma" -Cor Green
    Escrever "  acao especifica, veja a mensagem exibida e os logs abaixo." -Cor Green
}
else {
    Escrever "  Nao foi possivel concluir automaticamente. Veja os logs abaixo." -Cor Yellow
}

Escrever ""
Escrever "Logs recentes (segredos ocultados)" -Cor Cyan
$padroes = @(
    (Join-Path $ServiceDirectory '*.log'),
    (Join-Path $InstallRoot 'certificados-frontend\*.log'),
    (Join-Path $InstallRoot 'storage\logs\*.log'),
    (Join-Path $InstallRoot 'storage\runtime\*.log')
)
$logs = @()
foreach ($padrao in $padroes) {
    $logs += @(Get-ChildItem -Path $padrao -File -ErrorAction SilentlyContinue)
}
$logs = $logs | Sort-Object LastWriteTime -Descending | Select-Object -First 6

if (-not $logs) {
    Escrever "  Nenhum log encontrado nos caminhos padrao." -Cor Yellow
}
foreach ($log in $logs) {
    Escrever ""
    Escrever ("  --- {0} ({1:0.0} KB, {2:yyyy-MM-dd HH:mm:ss}) ---" -f $log.FullName, ($log.Length / 1KB), $log.LastWriteTime) -Cor DarkGray
    try {
        $linhas = Get-Content -LiteralPath $log.FullName -Tail 30 -ErrorAction Stop
        foreach ($linha in $linhas) {
            Escrever ("  " + (Ocultar-Segredos $linha))
        }
    }
    catch {
        Escrever "  (nao foi possivel ler o arquivo)" -Cor Red
    }
}

Escrever ""
Escrever "Dica: se a pagina inicial responder 200 mas a API falhar, o problema esta" -Cor Yellow
Escrever "no backend ou no BACKEND_URL. Se a pagina inicial responder 500, o build" -Cor Yellow
Escrever "do frontend precisa ser refeito com reparar-frontend.ps1." -Cor Yellow
Escrever ""
