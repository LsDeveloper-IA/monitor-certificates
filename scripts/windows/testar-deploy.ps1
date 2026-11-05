$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Deploy.Helpers.psm1') -Force
$privateFiles = @(
    'certificados-monitor/.env',
    'certificados-monitor/.env.20261019.bak',
    'certificados-frontend/.env.local',
    'certificados-frontend/.env.production.local',
    'storage/secrets/backend/credentials.json',
    'storage/secrets/backend/token_drive_relatorios.json',
    'storage/secrets/backend/token.pickle',
    'storage/database/app.db',
    'storage/runtime/agendador_automacao.json',
    'storage/automation_engine/dados/alertas_enviados.sqlite3',
    'storage/automation_engine/planilhas/relatorio.xlsx',
    'storage/automation_engine/certificados/cliente.pfx',
    'certificados-frontend/node_modules/next/package.json',
    'certificados-frontend/.next/server/app/page.js',
    'certificados-monitor/../fora.py',
    'certificados-monitor/../../fora.py',
    'automacoes/sieg/main.py',
    'automacoes/auto_nc/main.py',
    'automacoes/sieg_comum/drive.py'
)
foreach ($path in $privateFiles) {
    if (Test-DeployablePath $path) { throw "Arquivo privado aceito: $path" }
}
foreach ($path in @('certificados-monitor/src/main.py', 'certificados-monitor/requirements.txt', 'certificados-monitor/.env.example', 'config/__init__.py', 'config/validacao.py', 'certificados-frontend/src/app/page.tsx', 'certificados-frontend/package-lock.json')) {
    if (-not (Test-DeployablePath $path)) { throw "Arquivo publico rejeitado: $path" }
    $null = Get-SafeChildPath $PSScriptRoot $path
}
foreach ($file in @('atualizar.ps1', 'Deploy.Helpers.psm1', 'testar-deploy.ps1', 'diagnosticar-acesso-automacao.ps1', 'diagnosticar-servidor.ps1', 'reparar-frontend.ps1')) {
    $parseTokens = $null
    $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file), [ref]$parseTokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
}
# Verifica precedencia do XML: as chaves do servico nao podem ser trocadas pelo .env.
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('monitor-deploy-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
try {
    $envFile = Join-Path $fixture 'fixture.env'
    $xmlFile = Join-Path $fixture 'fixture.xml'
    [IO.File]::WriteAllText($envFile, "KEY=arquivo`r`nOTHER=preservado")
    [IO.File]::WriteAllText($xmlFile, '<service><env name="KEY" value="servico"/></service>')
    if ((Get-LocalSetting $envFile $xmlFile 'KEY') -ne 'servico') { throw 'Precedencia do XML incorreta.' }
    if ((Get-LocalSetting $envFile $xmlFile 'OTHER') -ne 'preservado') { throw 'Leitura do .env incorreta.' }
} finally {
    Remove-Item -LiteralPath $envFile, $xmlFile -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fixture
}
Write-Host 'Protecao de arquivos privados, precedencia de chaves e sintaxe dos scripts: OK.'
