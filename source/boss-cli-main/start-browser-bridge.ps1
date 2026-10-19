$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:BOSS_BRIDGE_FILE = Join-Path $PSScriptRoot '.runtime\browser-bridge.json'
$runtimeDirectory = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m boss_cli.cli browser serve @args
