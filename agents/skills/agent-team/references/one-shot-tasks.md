## One-shot task

```bash
$helper --once --backend gpt < /tmp/review.md
$helper --once --backend gpt --output-format json < /tmp/review.md
$helper --once --backend claude --backend gpt < /tmp/review.md
$helper --once --backend claude --backend gpt --timeout 300 < /tmp/review.md
$helper --once --backend gpt=/tmp/a.md --backend ds=/tmp/b.md
```

Single text mode returns the final reply. Single JSON mode uses
`{"result":"...","exit_code":0,"is_error":false}`. Multi-session and multi-backend
one-shot actions return `{"results":[{"backend":"...","result":"...","exit_code":0,"is_error":false}],"is_error":false}`.
Each one-shot backend has a 3600-second deadline (`pro` 7200), configurable with `--timeout`.
Timeout returns 124 and stops the owned process group, including descendants.
Each completed one-shot reply is immediately recorded on stderr as a JSON line
with `event: "completed"`, backend and the same result fields. Save
these records if the caller stops before the final stdout manifest; do not rerun
already completed assignments. SIGINT/SIGTERM stops unfinished process groups
and returns the collected manifest with exit code 130/143.

