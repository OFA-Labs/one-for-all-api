# Agent-1 final measurement matrix (EXPERIMENT ONLY). Run from benchmark/.
$env:AG1_COVERAGE_MIN = 0.85
$env:AG1_RARE_CAP = 12
$env:AG1_RANK_MAX = 8
$jobs = @(
  @{s=1000;  d=101}, @{s=1000;  d=102}, @{s=1000;  d=103},
  @{s=10000; d=101}, @{s=10000; d=102}, @{s=10000; d=103},
  @{s=50000; d=101}
)
foreach ($j in $jobs) {
  $out = "..\results\final_protoF_$($j.s)_$($j.d).csv"
  Write-Output "RUN size=$($j.s) seed=$($j.d)"
  & .\.venv\Scripts\python.exe -m harness.runner --contender ..\results\proto_F --size $j.s --seed $j.d --out $out |
    Select-String "correct_version_acc|zombie_rate |tokens_mean|budget_violations|injection_success_rate|leak_count|crashes|runtime_s" | ForEach-Object { $_.Line }
}
