---
name: merlin
description: |
  Submit, read back, reprioritize, debug and stop Merlin/Seed training jobs, read their logs,
  check group GPU headroom and devboxes through merlin-cli (job-v2). Use for any JobRun sid,
  seed.bytedance.net job URL, precheck, queue_priority, trial/pod logs, Robust restarts,
  execute-script, free GPUs, or merlin-cli 401/403 (提交任务、查任务、日志、优先级、卡位、预检、停任务).
---

# merlin-cli (job-v2)

Covers what we actually use (2026-09 → 10: `job-v2 runs get` alone is ~half of all calls).
For anything else: `merlin-cli <group> <cmd> --help`, `--schema` (request JSON Schema),
`--dry-run` (preview). Don't guess flags — every command takes its body via `--json '<obj>'`
or `--from-file <relative path in cwd>`; there is no `--sid`/`--run-id` flag.

```bash
M="merlin-cli --control-plane cn-seed"     # seed.bytedance.net; ml.bytedance.net would be cn
```

## Ground rules

- Use `job-v2 …` only. The v1 `job get-run` / `job list-run` / `job get-tls-log` / `job
  stop-run` family is legacy; don't write new calls against it.
- Three resource levels, each with its own sid: **run** (16-hex JobRun sid) → **trial**
  (numeric, `runs get` → `.data.runtime_context.trial_id`) → **pod** (numeric, from
  `run-trial-pods list`). Logs are per pod or per trial; priority is per trial.
- Responses are `{"ResponseBase":…, "data":…, "pagination":{…}}`; success is
  `ResponseBase.code == 0`. Exception: `resource groups get` returns `.group`, not `.data`.
- `[CONFIRM] stage=submit` on stderr (stop/create/exec in an agent session) means the call
  is **pending human approval**, even with exit 0. Done only after `stage=responded …
  decision=approved` plus a success payload; otherwise report it as blocked.
- 401 → `merlin-cli login` (SSO, the user scans); 403 → report the message and request_id,
  don't re-login. If `bytedcli merlin …` (MCP) fails, retry the same read with merlin-cli
  before calling the platform down — they are independent paths.
- Platform state is volatile: read it back live before acting on it; quote the command
  behind any number you report.

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
Offline verification: `uv run --with pytest pytest tests/test_mjob.py`.

## Logs and failure evidence

```bash
$M job-v2 run-trials exit-info --json '{"trials_list":{"filter":{"job_run_sid_any":["<run>"]}}}'  # trials+pods+exit codes
$M job-v2 run-trial-pods list --json '{"filter":{"trial_sid_any":["<trial>"]}}'                 # → pod sids
$M job-v2 run-trial-local-logs get --json '{"trial_pod_sid":"<pod>","stream":"stdout"}'          # .data.url → curl -s
$M job-v2 run-trial-tls-logs get --json '{"filter":{"trial_sid":"<trial>","stream":"std",
  "timestamp_ms_from":<ms>,"timestamp_ms_to":<ms>},"page_size":500}'
$M job-v2 run-trial-tls-log-configs get --json '{"filter":{"trial_pod_sid":"<pod>"}}'           # valid stream names
```

- Live logs: `local-logs` with `stdout`/`stderr` returns a signed URL; empty URL = pod gone,
  use TLS. TLS stream for training stdout is `std`; a Ray driver logs to `ray_job_stdout`.
- TLS time window is required and is **epoch ms UTC** (log lines print +08:00; convert with
  `calendar.timegm`, not `time.mktime`). `keyword` is whole-token matching and misses words
  like `watchdog` — pull the window and grep locally. `count` takes the same filter.
- Multi-line output (a printed tensor, a table, a traceback) survives only in **one pod's**
  stdout: `keyword` returns just the line that contains the word, so continuation lines are
  dropped and a 4-row tensor reads as 1 row that looks perfectly normal; the unfiltered merged
  stream sorts all pods by timestamp, interleaving each rank's continuations. Use
  `run-trial-local-logs get` → `.data.url` → `curl` (measured 52 MB / 355k lines in one GET).
- Failure root cause must cite this round's exit-info / log output, not the status alone.
- Restarts: `job-v2 run-trial-robusts list --json '{"filter":{"trial_sid":"<trial>"}}'`
  (platform Robust); an image-side `ROBUST_TRAINING` watchdog restarts in the same pods
  without appearing there — judge health by step progress in the logs, not by `status`.
- Events and who changed what: `job-v2 run-timelines list --json '{"filter":{"job_run_sid":"<run>"}}'`
  (singular `job_run_sid` inside `filter`; a top-level `{"sid":…}` is an unknown field; add
  `"event_type_any":[…]`). Low-utilization alerts and kills (3 h rolling mean ≤ 30%) appear
  only here, never in `status`; a kill can come with no prior alert event, and one observed
  kill landed 3h52m after `start_run` (so the window start is unverified — plan handovers
  well inside 3 h of trial start). Alerts: `job-v2 runs
  get-mega-trial-alerts --json '{"trial_id":"<trial>"}'`.
- Platform Robust runs machine checks (Sdclite/Eud/Dmesg/Loopback/Rnic) before each
  restart; all pass = judged a software exit, same machines, ~15 min per round.
- Run a command in the job: `job-v2 runs execute-script --json '{"job_run_id":"<run>",
  "exec":"nvidia-smi --query-gpu=index,utilization.gpu --format=csv"}'` (add `trial_id` /
  `pod_name` for a specific pod). Pods without sshd give `Connection refused`; the WebShell
  fallback needs `merlin-cli login --force` (a credential step for the user, not the agent) —
  otherwise fall back to log evidence. The WebShell cookie lives in the auth file of the
  machine that ran the login: after a local login, run the WebShell call locally, not on a
  devbox whose auth file is still stale.
- Global rank 0 is not necessarily the `executor-0` pod (2026-10-23: trial 438031854 executor-0 held ranks 72–79,
  rank 0 was executor-2). Find the rank-0 pod from a TLS `keyword` hit on a rank-0-only line and read its
  `kubernetes_pod_name`, then pull that pod's local log.
- Not a log path: `run-trial-logs list` requires `filter.path` and usually returns `[]`.

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

## Change a live job

```bash
$M job-v2 run-trials update --json '{"sid":"<trial>","queue_priority":40}'   # trial sid, not run sid
$M job-v2 runs stop --json '{"sid":"<run>","stop_reason":"…"}'
$M job-v2 runs robust-hot-update --from-file hot.json   # sid+attachments+job_config+resource_config
```

Hot update (build `hot.json` from `get-request-config`, change only
`job_config.job_template_config.entrypoint_full_script`) does **not** restart the running
round: the new config takes effect at the next Robust restart, in the same pods, without
requeueing. It returns code 0 with no `[CONFIRM]`, logs one `robust_hot_update` timeline
event, and `get-request-config` / `runs get` keep showing the old entrypoint — verify via the
next round's `set -x` echo in the logs. It can't change guaranteed/unguaranteed quota. Read
state back after every other change.

## Capacity, devboxes, data

```bash
$M resource groups get --json '{"sid":"1043","options":{"include_resources":true}}'
#   free = .group.resources.clusters[] | select(.cluster_sid=="47") | .queues[] | select(.node_type=="gpu")
#          → total.gpu["NVIDIA-H20"] − used.gpu["NVIDIA-H20"]   (my-group-resources list lacks this)
$M gpu-devbox instances get --json '{"instance_sid":"<sid>"}'     # list: '{}'
$M cpu-devbox instances get --json '{"sid":"<sid>"}'
$M data datacards get --json '{"name":"<datacard>","options":{"include_detail":true}}'
$M knowledge-v2 bases query --json '{"query":"…","limit":5}'      # platform docs Q&A with citations
```

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

Deep platform debugging (hang/NCCL/Arnold diagnosis) beyond this: `merlin-cli job-v2 runs
arnold-diagnose --help`, or install the full vendor skill on demand with
`merlin-cli skill install merlin-job --agent claude-code`.
