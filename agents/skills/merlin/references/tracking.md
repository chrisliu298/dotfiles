## Training metrics (Tracking)

Per-step scalars the training script logged. Strictly better than parsing one pod's stdout: these are
the global values. Needs the project/run ids, which the training logs print (`project_<date>_<hex>` /
`run_<date>_<hex>`), not the JobRun sid.

```bash
cat > trk.json <<'JSON'
{"ProjectRunIds":[{"ProjectId":"project_…","RunId":"run_…","Region":"cn"}],
 "XAxis":{"Name":"Step"},
 "YAxis":{"Metrics":[{"Name":"reward/psm_r2v_reward_r2v_clf"}]},
 "Option":{"DisableDownsample":true}}
JSON
$M tracking run-scalar-charts get --from-file trk.json
#   → .MetricLinesArray[0][0].Line.Data.{Xs,Ys,Timestamps}   (note: no `data` envelope here)
```

- `YAxis.Metrics` must be **objects** (`[{"Name":"…"}]`). A bare string list returns HTTP 400
  `Mismatch type run_scalar_chart.RunScalarChartYMetric with value string` — the CLI then prints its
  own usage after the error, which looks like a flag problem but is not.
- Without `DisableDownsample` the series comes back decimated.
- A killed job can lose its last writes: the series may end short of the last step the logs show.
  Compare against the log's final step before reporting a count.

