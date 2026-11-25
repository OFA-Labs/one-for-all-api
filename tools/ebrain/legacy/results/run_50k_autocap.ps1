# Agent-1: 50k re-run with scale-aware anchor cap (EXPERIMENT ONLY).
$ErrorActionPreference = "Continue"
cd C:\Users\jaiva\OneDrive\Desktop\voice-agents\ebrain-tournament\benchmark
$env:AG1_COVERAGE_MIN = "0.85"
$env:AG1_RARE_CAP_MODE = "auto"
$env:AG1_CAP_DIVISOR = "26"
$env:AG1_RANK_MAX = "16"
Write-Output "START autocap 50k $(Get-Date -Format o)"
& .\.venv\Scripts\python.exe ..\results\run_extended.py ..\results\proto_F 50000 101 ..\results\extended_protoF_autocap_50k_101.csv 7200 *>&1 |
  Tee-Object ..\results\log_extended_protoF_autocap_50k_101.txt
Write-Output "DONE autocap 50k $(Get-Date -Format o) exit=$LASTEXITCODE"
