<#
.SYNOPSIS
    Testa o executavel portatil em uma pasta temporaria.

.DESCRIPTION
    Copia o MonitorCertificados.exe para uma pasta vazia, inicia o programa,
    aguarda o servidor responder e valida:
      - a pagina inicial e os arquivos estaticos;
      - a criacao do .env com as chaves geradas;
      - o endpoint de configuracao local da chave administrativa;
      - leitura de certificados e uma escrita autenticada.

    O navegador nao e aberto durante o teste.

.EXAMPLE
    .\scripts\portable\testar-pacote.ps1

.EXAMPLE
    .\scripts\portable\testar-pacote.ps1 -Executavel .\monitor-certificates\MonitorCertificados.exe -Keep
#>
[CmdletBinding()]
param(
    [string]$Executavel = "",
    [switch]$Keep
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Executavel) {
    $Executavel = Join-Path $Raiz 'build\portable\dist\MonitorCertificados.exe'
}
$Executavel = (Resolve-Path $Executavel).Path

$Pasta = Join-Path $env:TEMP ("monitor-smoke-" + [guid]::NewGuid().ToString('N'))
$LogSaida = Join-Path $Pasta 'saida.log'
$LogErro = Join-Path $Pasta 'erro.log'
$Processo = $null

function Falhar([string]$Mensagem) {
    throw "FALHA: $Mensagem"
}

function Obter-Json([string]$Url, [hashtable]$Cabecalhos = @{}) {
    $resposta = Invoke-WebRequest -Uri $Url -Headers $Cabecalhos -UseBasicParsing -TimeoutSec 20
    return @{
        Status = [int]$resposta.StatusCode
        Texto = $resposta.Content
    }
}

try {
    New-Item -ItemType Directory -Force -Path $Pasta | Out-Null
    Copy-Item -Path $Executavel -Destination (Join-Path $Pasta 'MonitorCertificados.exe')
    Write-Host "Pasta de teste: $Pasta"

    $env:MONITOR_NO_BROWSER = '1'
    Remove-Item Env:FLASK_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:STORAGE_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:MONITOR_WEB_DIR -ErrorAction SilentlyContinue

    $Processo = Start-Process `
        -FilePath (Join-Path $Pasta 'MonitorCertificados.exe') `
        -WorkingDirectory $Pasta `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $LogSaida `
        -RedirectStandardError $LogErro

    $endereco = $null
    $limite = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $limite) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $LogSaida) {
            $conteudo = Get-Content $LogSaida -Raw -ErrorAction SilentlyContinue
            if ($conteudo -match 'Endereco:\s+(http://127\.0\.0\.1:\d+)') {
                $endereco = $Matches[1]
                break
            }
        }
        if ($Processo.HasExited) {
            $erro = if (Test-Path $LogErro) { Get-Content $LogErro -Raw } else { '' }
            Falhar "o executavel encerrou antes de iniciar.`n$erro"
        }
    }
    if (-not $endereco) {
        $saida = if (Test-Path $LogSaida) { Get-Content $LogSaida -Raw } else { '' }
        Falhar "o servidor nao iniciou em 120s.`n$saida"
    }
    Write-Host "Servidor: $endereco"

    # Aguarda a primeira resposta HTTP.
    $inicio = Get-Date
    while ($true) {
        try {
            $inicial = Obter-Json "$endereco/"
            break
        }
        catch {
            if (((Get-Date) - $inicio).TotalSeconds -gt 60) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
    if ($inicial.Status -ne 200 -or $inicial.Texto -notmatch 'Monitor de Certificados') {
        Falhar "a pagina inicial nao foi servida corretamente."
    }
    Write-Host "OK  pagina inicial e frontend estatico"

    $envFile = Join-Path $Pasta '.env'
    if (-not (Test-Path $envFile)) { Falhar "o .env nao foi criado." }
    $envTexto = Get-Content $envFile -Raw
    $linhasComMarcador = Get-Content $envFile | Where-Object {
        $_ -notmatch '^\s*#' -and $_ -match '__GERAR_[A-Z_]+__'
    }
    if ($linhasComMarcador) {
        Falhar "o .env ainda contem marcadores de chave: $($linhasComMarcador -join ', ')"
    }
    $chaveAdmin = ([regex]::Match($envTexto, '(?m)^AUTOMACAO_ADMIN_KEY=(.+)$')).Groups[1].Value.Trim()
    if (-not $chaveAdmin) { Falhar "AUTOMACAO_ADMIN_KEY nao foi gerada no .env." }
    Write-Host "OK  .env criado e chaves geradas"

    $config = Obter-Json "$endereco/api/configuracao/chave-admin"
    $dadosConfig = $config.Texto | ConvertFrom-Json
    if ($dadosConfig.chave -ne $chaveAdmin) {
        Falhar "a chave devolvida pelo endpoint nao corresponde ao .env."
    }
    Write-Host "OK  chave administrativa local"

    $certificados = Obter-Json "$endereco/api/certificados"
    if ($certificados.Status -ne 200) { Falhar "GET /api/certificados retornou $($certificados.Status)." }
    Write-Host "OK  leitura de certificados"

    $cabecalhos = @{ 'X-Admin-Key' = $chaveAdmin }
    $status = Obter-Json "$endereco/api/automacao/status" $cabecalhos
    if ($status.Status -ne 200) { Falhar "GET /api/automacao/status retornou $($status.Status)." }
    Write-Host "OK  rota administrativa autenticada"

    $corpo = @{
        nome_empresa = 'Empresa Teste Portatil'
        cpf_cnpj     = '12345678000190'
        tipo         = 'PJ'
        data_vencimento = '2027-12-31'
        responsavel  = 'Teste'
    } | ConvertTo-Json
    $criado = Invoke-WebRequest `
        -Uri "$endereco/api/certificados" `
        -Method Post `
        -Headers $cabecalhos `
        -ContentType 'application/json' `
        -Body $corpo `
        -UseBasicParsing `
        -TimeoutSec 20
    if ([int]$criado.StatusCode -notin 200, 201) {
        Falhar "POST /api/certificados retornou $($criado.StatusCode)."
    }
    Write-Host "OK  escrita de certificado autenticada"

    $statusSemChave = 0
    try {
        $semChave = Invoke-WebRequest `
            -Uri "$endereco/api/certificados" `
            -Method Post `
            -ContentType 'application/json' `
            -Body $corpo `
            -UseBasicParsing `
            -TimeoutSec 20
        $statusSemChave = [int]$semChave.StatusCode
    }
    catch {
        if ($_.Exception.Response) {
            $statusSemChave = [int]$_.Exception.Response.StatusCode
        }
        else {
            throw
        }
    }
    if ($statusSemChave -ne 401) {
        Falhar "escrita sem chave deveria retornar 401, retornou $statusSemChave."
    }
    Write-Host "OK  escrita sem chave bloqueada (401)"

    Write-Host ""
    Write-Host "Todos os testes do pacote passaram." -ForegroundColor Green
}
finally {
    if ($Processo -and -not $Processo.HasExited) {
        Stop-Process -Id $Processo.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
    }
    if (-not $Keep) {
        Remove-Item $Pasta -Recurse -Force -ErrorAction SilentlyContinue
    }
    else {
        Write-Host "Arquivos preservados em: $Pasta"
    }
    Remove-Item Env:MONITOR_NO_BROWSER -ErrorAction SilentlyContinue
}
