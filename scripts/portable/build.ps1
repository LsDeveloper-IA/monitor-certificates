<#
.SYNOPSIS
    Gera o pacote portatil do Monitor de Certificados para Windows.

.DESCRIPTION
    1. Compila o frontend Next.js em modo de exportacao estatica.
    2. Copia os arquivos gerados para build/portable/web.
    3. Gera o executavel unico com PyInstaller.
    4. Monta a pasta monitor-certificates/ com o exe, o .env.example,
       o LEIA-ME.txt e a pasta storage/.

    O frontend NAO precisa de Node na maquina de destino: os arquivos
    estaticos sao servidos pelo proprio Flask dentro do executavel.

.EXAMPLE
    .\scripts\portable\build.ps1

.EXAMPLE
    .\scripts\portable\build.ps1 -SkipTests -SkipFrontend
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipFrontend,
    [switch]$SkipPyInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Frontend = Join-Path $Raiz 'certificados-frontend'
$BuildPortable = Join-Path $Raiz 'build\portable'
$PastaWeb = Join-Path $BuildPortable 'web'
$Pacote = Join-Path $Raiz 'monitor-certificates'
$PastaApi = Join-Path $Frontend 'src\app\api'
$BackupApi = Join-Path $Raiz 'build\portable-api-backup'
$Spec = Join-Path $Raiz 'scripts\portable\MonitorCertificados.spec'
$ModeloEnv = Join-Path $Raiz 'scripts\portable\env.example'

$Python = Join-Path $Raiz '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $Python) {
    throw "Python nao encontrado. Crie o .venv ou instale o Python 3.11+."
}

function Write-Etapa([string]$Texto) {
    Write-Host ""
    Write-Host "==> $Texto" -ForegroundColor Cyan
}

function Remove-SeExistir([string]$Caminho) {
    if (Test-Path $Caminho) {
        Remove-Item $Caminho -Recurse -Force
    }
}

function Invoke-Checked([string]$Descricao, [scriptblock]$Acao) {
    & $Acao
    if ($LASTEXITCODE -ne 0) {
        throw "$Descricao falhou (codigo $LASTEXITCODE)."
    }
}

Write-Host "Raiz do projeto: $Raiz"
Write-Host "Python: $Python"

# ---------------------------------------------------------------------------
# 1. Testes do backend
# ---------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Etapa "Executando os testes do backend"
    Push-Location $Raiz
    try {
        Invoke-Checked "pytest" { & $Python -m pytest -q }
    }
    finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# 2. Frontend estatico
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $BuildPortable | Out-Null

if (-not $SkipFrontend) {
    Write-Etapa "Compilando o frontend Next.js (export estatico)"

    if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
        throw "node_modules nao encontrado. Execute 'npm install' em certificados-frontend."
    }

    $variaveisAnteriores = @{
        NEXT_STATIC_EXPORT = $env:NEXT_STATIC_EXPORT
        NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN = $env:NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN
    }

    # Os Route Handlers do Next nao podem existir em um build exportado.
    # A pasta e movida temporariamente e restaurada no finally.
    Remove-SeExistir $BackupApi
    if (Test-Path $PastaApi) {
        Move-Item -Path $PastaApi -Destination $BackupApi
    }

    try {
        $env:NEXT_STATIC_EXPORT = '1'
        $env:NEXT_PUBLIC_BOOTSTRAP_CHAVE_ADMIN = '1'

        Push-Location $Frontend
        try {
            Invoke-Checked "next build" { npm run build }
        }
        finally {
            Pop-Location
        }

        $SaidaNext = Join-Path $Frontend 'out'
        if (-not (Test-Path (Join-Path $SaidaNext 'index.html'))) {
            throw "O build estatico nao gerou out/index.html."
        }

        Remove-SeExistir $PastaWeb
        Copy-Item -Path $SaidaNext -Destination $PastaWeb -Recurse -Force
        Write-Host "Frontend copiado para $PastaWeb"
    }
    finally {
        if (Test-Path $BackupApi) {
            if (Test-Path $PastaApi) {
                Remove-SeExistir $PastaApi
            }
            Move-Item -Path $BackupApi -Destination $PastaApi
        }
        foreach ($nome in $variaveisAnteriores.Keys) {
            $valor = $variaveisAnteriores[$nome]
            if ($null -eq $valor) {
                Remove-Item "Env:$nome" -ErrorAction SilentlyContinue
            }
            else {
                Set-Item "Env:$nome" -Value $valor
            }
        }
    }
}
elseif (-not (Test-Path (Join-Path $PastaWeb 'index.html'))) {
    throw "Build do frontend ignorado, mas $PastaWeb nao contem index.html."
}

Copy-Item -Path $ModeloEnv -Destination (Join-Path $BuildPortable '.env.example') -Force

# ---------------------------------------------------------------------------
# 3. Executavel com PyInstaller
# ---------------------------------------------------------------------------
if (-not $SkipPyInstaller) {
    Write-Etapa "Gerando o executavel com PyInstaller"

    & $Python -m PyInstaller --version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller nao esta instalado. Execute: `"$Python`" -m pip install pyinstaller"
    }

    $Dist = Join-Path $BuildPortable 'dist'
    $Work = Join-Path $BuildPortable 'work'
    Remove-SeExistir $Dist
    Remove-SeExistir $Work

    Push-Location $Raiz
    try {
        Invoke-Checked "PyInstaller" {
            & $Python -m PyInstaller `
                --noconfirm --clean `
                --distpath $Dist `
                --workpath $Work `
                $Spec
        }
    }
    finally {
        Pop-Location
    }

    $ExecutavelGerado = Join-Path $Dist 'MonitorCertificados.exe'
    if (-not (Test-Path $ExecutavelGerado)) {
        throw "PyInstaller nao gerou $ExecutavelGerado."
    }
}
else {
    $ExecutavelGerado = Join-Path $BuildPortable 'dist\MonitorCertificados.exe'
    if (-not (Test-Path $ExecutavelGerado)) {
        throw "Build do executavel ignorado, mas $ExecutavelGerado nao existe."
    }
}

# ---------------------------------------------------------------------------
# 4. Monta a pasta final
# ---------------------------------------------------------------------------
Write-Etapa "Montando a pasta $Pacote"

New-Item -ItemType Directory -Force -Path $Pacote | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Pacote 'storage') | Out-Null

Copy-Item -Path $ExecutavelGerado -Destination (Join-Path $Pacote 'MonitorCertificados.exe') -Force
Copy-Item -Path $ModeloEnv -Destination (Join-Path $Pacote '.env.example') -Force

$LeiaMe = @'
Monitor de Certificados - pacote portatil
==========================================

COMO USAR
---------
1. Extraia esta pasta inteira para um local fixo
   (ex.: C:\MonitorCertificados). Nao execute direto de dentro de um ZIP.
2. Clique duas vezes em MonitorCertificados.exe.
3. O navegador abre automaticamente em http://127.0.0.1:5000.
4. Mantenha a janela preta aberta enquanto usar o sistema.
   Para encerrar, feche a janela ou pressione Ctrl+C.

Na primeira execucao sao criados:
  .env      -> configuracao (com chaves geradas automaticamente)
  storage\  -> banco de dados, historicos, logs e segredos

O programa usa a porta 5000. Se ela estiver ocupada, tenta as
portas seguintes (5001 a 5099) e informa o endereco na janela.

CONFIGURACAO
------------
Abra o arquivo .env em um editor de texto (Notepad++) e preencha
as integracoes que for usar:
  - ODBC_DSN / ODBC_USUARIO / ODBC_SENHA (banco de clientes)
  - EMAIL_REMETENTE e credenciais OAuth do Gmail
  - WHATSCONTABIL_URL / WHATSCONTABIL_TOKEN
  - GOOGLE_DRIVE_* (pastas e credenciais)
  - CONTHABIL_EMAIL / CONTHABIL_SENHA
Reinicie o executavel depois de alterar o .env.

A chave administrativa e preenchida automaticamente no painel.
Para consulta-la, veja AUTOMACAO_ADMIN_KEY no .env.

AUTOMACOES (OPCIONAL)
---------------------
O painel funciona sem Python instalado. Para executar as automacoes
(SIEG, Auto NC e Conthabil) a maquina precisa de:
  1. Python 3.11 ou superior no PATH (ou MONITOR_PYTHON_EXE no .env).
  2. As dependencias de cada automacao:
       pip install -r automacoes\sieg\requirements.txt
       pip install -r automacoes\auto_nc\requirements.txt
       pip install -r automacoes\conthabil\requirements.txt
  3. O Chromium do Playwright:
       python -m playwright install chromium
As pastas das automacoes e seus .env precisam estar ao lado do executavel
(mesma pasta deste LEIA-ME), na estrutura do projeto: automacoes\.
As credenciais e tokens ficam em storage\secrets\ e sao criados
conforme a configuracao de cada integracao.

BACKUP
------
Copie a pasta storage\ periodicamente. Ela contem o banco
(storage\database\app.db), historicos e configuracoes sensiveis.
Nao apague essa pasta ao atualizar o programa.

ATUALIZACAO
-----------
Substitua apenas MonitorCertificados.exe e .env.example.
Preserve .env e storage\ para nao perder dados.

PROBLEMAS COMUNS
----------------
- "Falha ao iniciar": veja storage\logs\erro-inicializacao.log.
- Porta ocupada: feche o outro programa ou altere FLASK_PORT no .env.
- Antivirus bloqueando: libere o MonitorCertificados.exe.
'@
Set-Content -Path (Join-Path $Pacote 'LEIA-ME.txt') -Value $LeiaMe -Encoding UTF8

$TamanhoMb = [math]::Round(
    ((Get-ChildItem $Pacote -Recurse -File | Measure-Object Length -Sum).Sum / 1MB),
    2
)

Write-Host ""
Write-Host "Pacote gerado com sucesso: $Pacote" -ForegroundColor Green
Write-Host "Tamanho: $TamanhoMb MB"
Get-ChildItem $Pacote -Force | Select-Object Mode, Name, Length

exit 0
