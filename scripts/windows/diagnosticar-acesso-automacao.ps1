<#
.SYNOPSIS
    Diagnostica o erro "Acesso nao autorizado" ao iniciar automacoes.

.DESCRIPTION
    Executa na maquina do servidor (a mesma dos servicos
    MonitorCertificados e MonitorFrontend).

    O script NAO imprime nem altera chaves. Ele apenas informa:
      - se a chave interna existe no backend e no frontend;
      - se as duas chaves sao iguais;
      - qual camada esta recusando a requisicao (Flask ou Next).

.EXAMPLE
    .\scripts\windows\diagnosticar-acesso-automacao.ps1
#>
param(
    [string]$InstallRoot = 'D:\Projetos\monitor-certificates',
    [string]$ServiceDirectory = 'D:\Servicos\MonitorCertificados'
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Deploy.Helpers.psm1') -Force

$backendEnv = Join-Path $InstallRoot 'certificados-monitor\.env'
$frontendEnv = Join-Path $InstallRoot 'certificados-frontend\.env.local'
$backendXml = Join-Path $ServiceDirectory 'MonitorCertificados.xml'
$frontendXml = Join-Path $ServiceDirectory 'MonitorFrontend.xml'

foreach ($arquivo in @($backendEnv, $frontendEnv)) {
    if (-not (Test-Path -LiteralPath $arquivo -PathType Leaf)) {
        throw "Arquivo de configuracao ausente: $arquivo"
    }
}

$chaveBackend = Get-LocalSetting $backendEnv $backendXml 'AUTOMACAO_EXECUTION_KEY'
$chaveFrontend = Get-LocalSetting $frontendEnv $frontendXml 'AUTOMACAO_EXECUTION_KEY'
$adminFrontend = Get-LocalSetting $frontendEnv $frontendXml 'AUTOMACAO_ADMIN_KEY'

function Descrever-Chave([string]$Nome, [string]$Valor) {
    if (-not $Valor) {
        Write-Host ("  {0}: AUSENTE" -f $Nome) -ForegroundColor Red
    }
    else {
        Write-Host ("  {0}: configurada ({1} caracteres)" -f $Nome, $Valor.Length) -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Configuracao local" -ForegroundColor Cyan
Descrever-Chave 'Backend  AUTOMACAO_EXECUTION_KEY' $chaveBackend
Descrever-Chave 'Frontend AUTOMACAO_EXECUTION_KEY' $chaveFrontend
Descrever-Chave 'Frontend AUTOMACAO_ADMIN_KEY' $adminFrontend

$chavesIguais = $chaveBackend -and $chaveFrontend -and ($chaveBackend -ceq $chaveFrontend)
if ($chavesIguais) {
    Write-Host "  Chave interna do backend e do frontend: IGUAIS" -ForegroundColor Green
}
else {
    Write-Host "  Chave interna do backend e do frontend: DIFERENTES" -ForegroundColor Red
}

function Testar-Requisicao([string]$Descricao, [string]$Url, [hashtable]$Headers) {
    Write-Host ""
    Write-Host $Descricao -ForegroundColor Cyan
    try {
        $resposta = Invoke-WebRequest -UseBasicParsing -Uri $Url -Headers $Headers -TimeoutSec 10
        Write-Host ("  HTTP {0}" -f $resposta.StatusCode) -ForegroundColor Green
        return $resposta
    }
    catch {
        $status = $null
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        if ($null -eq $status) {
            Write-Host '  HTTP sem resposta' -ForegroundColor Red
        }
        else {
            Write-Host ("  HTTP {0}" -f $status) -ForegroundColor Red
        }
        if ($_.ErrorDetails.Message) {
            try {
                $corpo = $_.ErrorDetails.Message | ConvertFrom-Json
                if ($corpo.erro) { Write-Host ("  Mensagem: {0}" -f $corpo.erro) }
            }
            catch { }
        }
        return $null
    }
}

Write-Host ""
Write-Host "Testes de acesso" -ForegroundColor Cyan
if ($chaveBackend) {
    $null = Testar-Requisicao `
        'Flask direto (127.0.0.1:5000) com a chave do backend' `
        'http://127.0.0.1:5000/api/automacao/status' `
        @{ 'X-Automation-Key' = $chaveBackend }
}

if ($adminFrontend) {
    $null = Testar-Requisicao `
        'Next (127.0.0.1:3000) com a chave administrativa' `
        'http://127.0.0.1:3000/api/automacao/status' `
        @{ 'X-Admin-Key' = $adminFrontend }
}
else {
    $null = Testar-Requisicao `
        'Next (127.0.0.1:3000) sem chave administrativa' `
        'http://127.0.0.1:3000/api/automacao/status' `
        @{}
}

Write-Host ""
if ($chavesIguais) {
    Write-Host 'As chaves internas estao alinhadas. Se o erro continuar, confira se os dois servicos foram reiniciados depois da ultima alteracao no .env.' -ForegroundColor Yellow
}
else {
    Write-Host 'CORRECAO IMEDIATA: copie o valor de AUTOMACAO_EXECUTION_KEY do certificados-monitor\.env' -ForegroundColor Yellow
    Write-Host 'para certificados-frontend\.env.local (mesmo valor, sem aspas) e reinicie o servico MonitorFrontend.' -ForegroundColor Yellow
    Write-Host 'A versao mais recente do sistema dispensa esse alinhamento (proxy local autenticado).' -ForegroundColor Yellow
}
Write-Host ""
