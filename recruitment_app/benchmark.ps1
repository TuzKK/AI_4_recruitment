param(
    [string]$Output = "recruitment_app/.runtime/benchmark_result.json",
    [ValidateRange(0, 100)][int]$Threshold = 75
)

$workspace = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspace 'source/boss-cli-main/.venv/Scripts/python.exe'
$deps = Join-Path $PSScriptRoot '.runtime/benchmark_deps'
if (-not (Test-Path -LiteralPath $python)) { throw "Python environment missing: $python" }
if (-not $env:DASHSCOPE_API_KEY) { throw 'Set DASHSCOPE_API_KEY in this terminal before benchmarking.' }
if (Test-Path -LiteralPath $deps) {
    $env:PYTHONPATH = $deps + [IO.Path]::PathSeparator + $env:PYTHONPATH
}
Push-Location $workspace
try {
    & $python -m recruitment_app.benchmark --output $Output --threshold $Threshold
    if ($LASTEXITCODE -ne 0) { throw "Benchmark failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
