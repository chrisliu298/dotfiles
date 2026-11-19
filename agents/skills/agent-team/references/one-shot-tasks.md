## One-shot task

```bash
$helper --once --effort medium --backend astra < /tmp/review.md
$helper --once --effort medium --backend astra --output-format json < /tmp/review.md
$helper --once --effort high --backend astra --backend neon < /tmp/review.md
$helper --once --effort high --backend astra --backend neon --timeout 300 < /tmp/review.md
$helper --once --effort high --backend astra=/tmp/a.md --backend neon=/tmp/b.md
```

Single text mode returns the final reply. Single JSON mode uses
`{"result":"...","exit_code":0,"is_error":false}`. Multi-session and multi-backend
one-shot actions return `{"results":[{"backend":"...","result":"...","exit_code":0,"is_error":false}],"is_error":false}`.
Each one-shot backend has a 3600-second deadline, configurable with `--timeout`.
Timeout returns 124 and stops the owned process group, including descendants.
Each completed one-shot reply is immediately recorded on stderr as a JSON line
with `event: "completed"`, backend and the same result fields. Save
these records if the caller stops before the final stdout manifest; do not rerun
already completed assignments. SIGINT/SIGTERM stops unfinished process groups
and returns the collected manifest with exit code 130/143.

