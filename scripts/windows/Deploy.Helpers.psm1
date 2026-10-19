Set-StrictMode -Version Latest

function Test-DeployablePath([string]$Path) {
    $p = $Path.Replace('\', '/')
    if ($p -notmatch '^(certificados-monitor|certificados-frontend)/') { return $false }
    if ($p -match '(^|/)(\.\.?)(/|$)') { return $false }
    if ($p -match '(?i)(^|/)(runtime|dados|planilhas|relatorios|logs|database|node_modules|\.next|\.git|\.vercel|__pycache__|\.venv|venv)(/|$)') { return $false }
    $name = ($p -split '/')[-1]
    if ($name -match '(?i)^(\.env($|\.)|credentials.*\.json$|token.*\.(json|pickle)$)' -and $name -ne '.env.example') { return $false }
    if ($p -match '(?i)\.(db|sqlite3?|pfx|p12|pem|key|pdf|xlsx?|pyc|log|bak)$') { return $false }
    return $true
}

function Get-SafeChildPath([string]$Root, [string]$RelativePath) {
    if (-not (Test-DeployablePath $RelativePath)) { throw "Caminho privado ou fora da aplicacao: $RelativePath" }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $full = [IO.Path]::GetFullPath((Join-Path $Root $RelativePath))
    if (-not $full.StartsWith($base, [StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho fora da instalacao.' }
    return $full
}

function Get-LocalSetting([string]$EnvFile, [string]$XmlFile, [string]$Name) {
    $value = ''
    foreach ($line in [IO.File]::ReadAllLines($EnvFile)) {
        if ($line -match ('^\s*' + [regex]::Escape($Name) + '\s*=(.*)$')) {
            $value = $Matches[1].Trim().Trim([char]34).Trim([char]39)
        }
    }
    if (Test-Path -LiteralPath $XmlFile) {
        [xml]$xml = [IO.File]::ReadAllText($XmlFile)
        foreach ($item in @($xml.SelectNodes('/service/env'))) {
            if ($item.GetAttribute('name') -eq $Name) { $value = $item.GetAttribute('value') }
        }
    }
    return $value
}

Export-ModuleMember -Function Test-DeployablePath, Get-SafeChildPath, Get-LocalSetting
