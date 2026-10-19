$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$cli = Join-Path $root 'source\boss-cli-main'
$env:PYTHONUTF8 = '1'
$env:BOSS_TRANSPORT = 'browser'
$env:BOSS_BRIDGE_FILE = Join-Path $cli '.runtime\browser-bridge.json'
Set-Location $root
& (Join-Path $cli '.venv\Scripts\python.exe') -m recruitment_app
