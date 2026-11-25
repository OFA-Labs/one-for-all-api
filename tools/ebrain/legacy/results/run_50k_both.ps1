# Agent-1: 50k extended-catalogue runs, baseline then new design. (EXPERIMENT ONLY.)
$ErrorActionPreference = "Continue"
cd C:\Users\jaiva\OneDrive\Desktop\voice-agents\ebrain-tournament\benchmark
$py = ".\.venv\Scripts\python.exe"

Write-Output "START baseline 50k $(Get-Date -Format o)"
& $py ..\results\run_extended.py ..\FINAL\reference\impl 50000 101 ..\results\extended_baseline_50k_101.csv 7200 *>&1 |
  Tee-Object ..\results\log_extended_baseline_50k_101.txt
Write-Output "DONE baseline 50k $(Get-Date -Format o) exit=$LASTEXITCODE"

$env:AG1_COVERAGE_MIN = 0.85
$env:AG1_RARE_CAP = 12
$env:AG1_RANK_MAX = 8
Write-Output "START protoF 50k $(Get-Date -Format o)"
& $py ..\results\run_extended.py ..\results\proto_F 50000 101 ..\results\extended_protoF_50k_101.csv 7200 *>&1 |
  Tee-Object ..\results\log_extended_protoF_50k_101.txt
Write-Output "DONE protoF 50k $(Get-Date -Format o) exit=$LASTEXITCODE"
