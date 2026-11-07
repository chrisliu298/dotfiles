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

Deep platform debugging (hang/NCCL/Arnold diagnosis) beyond this: `merlin-cli job-v2 runs
arnold-diagnose --help`, or install the full vendor skill on demand with
`merlin-cli skill install merlin-job --agent claude-code`.
