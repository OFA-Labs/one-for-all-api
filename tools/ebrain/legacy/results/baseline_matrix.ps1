# Agent-1 baseline matrix (EXPERIMENT ONLY). Run from benchmark/.
foreach ($s in 1000,10000) {
  foreach ($d in 101,102,103) {
    $out = "..\results\baseline_${s}_$d`_ref.csv"
    Write-Output "RUN baseline size=$s seed=$d"
    & .\.venv\Scripts\python.exe -m harness.runner --contender ..\FINAL\reference\impl --size $s --seed $d --out $out |
      Select-String "correct_version_acc|zombie_rate |tokens_mean|crashes" | ForEach-Object { $_.Line }
  }
}
