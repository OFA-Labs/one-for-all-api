# Agent-1 experiment grid (EXPERIMENT ONLY). Run from benchmark/.
$configs = @(
  @{r=12; c=0.70; k=8},
  @{r=6;  c=0.70; k=8},
  @{r=20; c=0.70; k=8},
  @{r=12; c=0.85; k=8},
  @{r=12; c=0.70; k=4},
  @{r=6;  c=0.85; k=4}
)
$i = 0
foreach ($cfg in $configs) {
  $i++
  $env:AG1_RARE_CAP = $cfg.r
  $env:AG1_COVERAGE_MIN = $cfg.c
  $env:AG1_RANK_MAX = $cfg.k
  $out = "..\results\gridF_${i}_r$($cfg.r)_c$($cfg.c)_k$($cfg.k).csv"
  Write-Output "RUN $i rare=$($cfg.r) cov=$($cfg.c) rank=$($cfg.k)"
  & .\.venv\Scripts\python.exe -m harness.runner --contender ..\results\proto_F --size 10000 --seed 101 --out $out | Select-String "correct_version_acc|zombie_rate |injection_success_rate|crashes"
}
