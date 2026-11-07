## Read a job

```bash
$M job-v2 runs get --json '{"sid":"<run>"}'
$M job-v2 run-trials list --json '{"filter":{"job_run_sid_any":["<run>"]}}'   # queue_at, start_at
$M job-v2 runs list --json '{"filter":{"arnold_group_id_any":[1043],"created_at_from":"<RFC3339>",
  "created_by_any":["<user>"],"status_any":["running","started"]},"page_size":100}'
```

- CLI 0.2.528 verified 2026-10-23: `--json '<body>'` supplies the request; use the examples
  above, not named `--sid` / `--filter` flags. Responses may be direct (`.data`) or wrapped
  (`.data.result.data`); check `ResponseBase` inside the wrapper too.
- `runs get` fields: `.data.status` goes `launching` → `started` (**still queued**) →
  `running` → `done|failed|stopped`; `.data.runtime_context.{trial_id,trial_status}`;
  priority at `.data.attachments[].arnold_cluster_control_attachment.queue_priority`;
  GPUs = Σ `num × gpu` over `.data.resource_config.arnold_resource_config.roles[]`.
- Robust is on iff an attachment with `robust_attachment` exists — when off the platform
  drops it entirely (there is no `use_robust_training: false` to see).
- "Is it really running" = trial `start_at` is set. Give the scheduler ~10 min after submit
  before concluding there is no capacity.
- Every timestamp in these payloads (`created_at`, `schedule_at`, `start_at`, timeline events)
  is **UTC**, printed with a trailing `Z`; log lines inside the job print +08:00. Reading one
  as local time shifts it 8 hours — a job submitted 14:43 Beijing reads `06:43Z` and looks
  like it has been running since morning. Convert before reporting any elapsed time.
- `runs list` pages via `pagination.next_page_token` → `page_token`; walk all pages.
  Server-side filters verified 2026-10-18: `arnold_group_id_any`, `created_at_from`,
  `created_by_any`, `status_any`, `keyword_contains`. A misnamed filter field is silently
  ignored — confirm `pagination.total` actually shrank, and still check `created_by` on the
  rows you act on.
- Group 1043 with `created_at_from=2026-10-20T00:00:00Z`, checked 2026-10-23: omitting
  `created_by_any` and passing `["*"]` both returned 251 runs with identical SIDs and 14
  creators. Group queries therefore omit it; personal queries still pass and re-check it.

## Read-only summaries with mjob

Prefer this skill's executable `scripts/mjob` for routine reads (Python 3 stdlib plus
`merlin-cli` on PATH). It always uses `--control-plane cn-seed`, handles warning prefixes
and both response envelopes, and fails on API errors without printing credentials or signed
URL queries. No installation or platform mutation is needed. From this skill directory:

```bash
scripts/mjob brief ee445eb08a202165 1d4eaf79cca17bfc
scripts/mjob free                         # --group 1043 --cluster 47
scripts/mjob mine                         # --user liuyuhao.chris --group 1043 --since RFC3339
scripts/mjob mine --gpu-only               # positive GPU count and job_type=train
scripts/mjob queue --since 2026-10-20T00:00:00Z  # --group 1043
scripts/mjob logs ee445eb08a202165 --rank 0 --grep 'global_step' --tail 3
scripts/mjob req ee445eb08a202165 --out req.json  # what the platform received
```

`brief`, `mine`, and `queue` print tab-separated, labelled fields with no header (one run
per line); `started` gets `state=queued`, and absent trial `start_at` is `-`. GPUs sum
`num × gpu` across all roles. `mine` walks every page for running/started/launching runs;
it includes Devboxes by default; `--gpu-only` keeps positive-GPU runs whose `job_type` is
`train` (other types are excluded even if they request GPUs).
`scripts/mjob mine | wc -l` recomputes the row count. Both list commands search all history
unless `--since` is supplied. `queue` requests `status_any=["running","started","launching"]`:
unfiltered server pagination was observed to omit queued runs inconsistently. It retains
the local queued/staging/pending/initializing trial-state filter, then sorts by
`(queue_priority, numeric trial_id)` (missing priority sorts as 99; missing trial IDs go
last within their priority).
This is a queue-order view, not a guarantee of allocation or resource fit.

`logs` selects the pod name's rank suffix (default 0, not the distributed global rank),
downloads stdout, applies the Python
regular expression locally, then takes the last N matching lines. An empty download URL
falls back to paginated TLS `std` logs for that same trial and pod over the last hour
(`--since-min` changes this window). The fallback checks `run-trial-tls-log-configs`, then
uses `run-trial-tls-log-files get` in that same window to find the unique file named
`stdout`. It passes that path as `pod_file_path` and re-checks returned paths locally so
the shared `std` stream cannot mix in stderr. Missing/ambiguous stdout files or ranks fail
explicitly; missing or invalid run data also produces a readable error with a nonzero exit.
`req` reads `runs get-request-config`, whose response has no `data` layer, prints commit, GPUs,
priority, steps and data path on one line, and with `--out` writes the body without the envelope.
The platform drops `false` and default-valued fields from this body, so check a body before
submitting it from what you will submit, and use this readback for facts after submitting.
Offline verification: `uv run --with pytest pytest tests/test_mjob.py`.

