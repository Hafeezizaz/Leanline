# Adds (or updates) the "leanline" MCP server in Claude Desktop's config, keeping any other servers.
$ErrorActionPreference = "Stop"

$py  = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$dir = Join-Path $env:APPDATA "Claude"
$cfg = Join-Path $dir "claude_desktop_config.json"

New-Item -ItemType Directory -Force -Path $dir | Out-Null

$obj = [pscustomobject]@{}
if (Test-Path $cfg) {
    Copy-Item $cfg "$cfg.bak" -Force   # backup before touching it
    $raw = Get-Content $cfg -Raw
    if (-not [string]::IsNullOrWhiteSpace($raw)) { $obj = $raw | ConvertFrom-Json }
}

if (-not $obj.PSObject.Properties["mcpServers"]) {
    $obj | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
}

$entry = [pscustomobject]@{ command = $py; args = @("-m", "leanline", "serve") }
if ($obj.mcpServers.PSObject.Properties["leanline"]) {
    $obj.mcpServers.leanline = $entry
} else {
    $obj.mcpServers | Add-Member -NotePropertyName leanline -NotePropertyValue $entry
}

$json = $obj | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($cfg, $json, (New-Object System.Text.UTF8Encoding($false)))  # UTF-8 without BOM
Write-Host "Updated $cfg"
Write-Host "Leanline command: $py -m leanline serve"
