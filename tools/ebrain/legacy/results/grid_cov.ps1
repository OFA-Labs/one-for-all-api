# Agent-1 coverage sweep (EXPERIMENT ONLY). Run from benchmark/.
foreach ($c in 0.40,0.45,0.50,0.55) {
  $env:AG1_COVERAGE_MIN=$c
  $env:AG1_RARE_CAP=12
  $env:AG1_RANK_MAX=8
  $out="..\results\cov_$c`_10k_101.csv"
  Write-Output "=== cov=$c ==="
  & .\.venv\Scripts\python.exe -m harness.runner --contender ..\results\proto_F --size 10000 --seed 101 --out $out | Select-String "correct_version_acc|zombie_rate |injection_success_rate|crashes"
}
