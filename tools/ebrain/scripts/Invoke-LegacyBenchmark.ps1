param(
    [ValidateSet('reference','product')][string]$Contender = 'product',
    [ValidateSet(1000,10000)][int]$Size = 1000,
    [ValidateSet(101,102,103)][int]$Seed = 101,
    [string]$Python,
    [int]$TimeoutSeconds = 900
)
$ErrorActionPreference = 'Stop'
$taskApiRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
if (-not $Python) { $Python = Join-Path $taskApiRoot '.venv/Scripts/python.exe' }
$taskPython = (Resolve-Path -LiteralPath $Python).Path
$taskLegacy = Join-Path $taskApiRoot 'tools/ebrain/legacy'
$taskBenchmark = Join-Path $taskLegacy 'benchmark'
$taskAdapter = if ($Contender -eq 'reference') {
    Join-Path $taskLegacy 'FINAL/reference/impl'
} else {
    Join-Path $taskApiRoot 'tools/ebrain/product-adapter'
}
$taskRunId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$taskRunDir = Join-Path $taskApiRoot "docs/ebrain/implementation-plan/evidence/legacy-$Contender-$Size-$Seed-$taskRunId"
New-Item -ItemType Directory -Path $taskRunDir | Out-Null
$taskOut = Join-Path $taskRunDir 'results.csv'
$taskArgs = @('-m','harness.runner','--contender',$taskAdapter,'--size',"$Size",'--seed',"$Seed",'--out',$taskOut,'--timeout-s',"$TimeoutSeconds")
$taskCodeFiles = @(Get-ChildItem -LiteralPath $taskAdapter -Filter '*.py' -File -Recurse)
if ($Contender -eq 'product') { $taskCodeFiles += @(Get-ChildItem -LiteralPath (Join-Path $taskApiRoot 'ebrain') -Filter '*.py' -File -Recurse) }
$taskHashes = @($taskCodeFiles | Sort-Object FullName | ForEach-Object {
    @{ path = $_.FullName.Substring($taskApiRoot.Length + 1).Replace('\','/'); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$taskManifest = @{
    run_id = $taskRunId; contender = $Contender; size_events = $Size; seed = $Seed
    python = $taskPython; runtime = @(& $taskPython -c 'import sys,sqlite3; print(sys.version); print(sqlite3.sqlite_version)')
    cwd = $taskBenchmark; args = $taskArgs; source_hashes = $taskHashes
    git_head = (& git -C $taskApiRoot rev-parse HEAD)
    note = 'Frozen legacy synthetic protocol. Runtime may differ from original Python 3.11 research. Product source hashes supplement harness adapter hash. Not V3 evidence.'
}
$taskManifestPath = Join-Path $taskRunDir 'manifest.json'
$taskManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskManifestPath -Encoding UTF8
$taskExit = 1
Push-Location $taskBenchmark
try {
    & $taskPython @taskArgs
    $taskExit = $LASTEXITCODE
} finally {
    Pop-Location
    $taskManifest.exit_code = $taskExit
    $taskManifest.completed_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    if (Test-Path -LiteralPath $taskOut) { $taskManifest.csv_sha256 = (Get-FileHash -LiteralPath $taskOut -Algorithm SHA256).Hash.ToLowerInvariant() }
    $taskManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskManifestPath -Encoding UTF8
    Write-Output "Evidence: $taskRunDir"
}
exit $taskExit
