param([string]$Python)
$ErrorActionPreference = 'Stop'
$taskApiRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
if (-not $Python) { $Python = Join-Path $taskApiRoot '.venv/Scripts/python.exe' }
$taskLegacy = Join-Path $taskApiRoot 'tools/ebrain/legacy'
$taskSources = @(
    (Join-Path $taskLegacy 'benchmark/results_v2.csv'),
    (Join-Path $taskLegacy 'FINAL/reference/results/public_1k.csv'),
    (Join-Path $taskLegacy 'FINAL/reference/results/public_10k_101.csv')
)
foreach ($taskSource in $taskSources) {
    if (-not (Test-Path -LiteralPath $taskSource -PathType Leaf)) { throw "Missing measured source: $taskSource" }
}
$taskOldSources = [Environment]::GetEnvironmentVariable('EBRAIN_FACTS_SOURCES', 'Process')
$taskExit = 1
Push-Location $taskApiRoot
try {
    $env:EBRAIN_FACTS_SOURCES = $taskSources -join ';'
    & $Python -m pytest tests -q
    $taskExit = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('EBRAIN_FACTS_SOURCES', $taskOldSources, 'Process')
    Pop-Location
}
exit $taskExit
