## Submit

1. Precheck the exact payload you will submit:
   `$M job-v2 check-items check --from-file pre.json` with
   `{"node_type":"merlin_job_run_seed","check_point":"create","job_run_context":<create body>}`.
   Need `data.status == "success"` (`warn` = read each item); copy `data.sid`.
2. Put it in the create body as `"request_context":{"precheck_sid":"<sid>"}` (missing →
   `21806 PrecheckRequired`). The sid expires: precheck right before submitting, never reuse
   an old sid.
3. `$M job-v2 runs create --from-file req.json --dry-run`, then without `--dry-run`.
   File must sit in the cwd, passed as a relative path.
4. Read back `runs get`: `created_by`, `queue_priority`, robust attachment as intended.

Reuse a known-good request rather than writing one: `job-v2 runs get-request-config --json
'{"sid":"<run>"}'` returns the original create body (strip the response envelope; `diff`
before resubmitting). `job-v2 runs fork --json '{"source_sid":"<run>","name":"…",
"overrides":{…}}'` — overrides replace whole top-level fields (shallow), so pass a full
`job_config` when changing anything inside it.

