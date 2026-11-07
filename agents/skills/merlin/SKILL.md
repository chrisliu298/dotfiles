---
name: merlin
description: |
  Submit, read, reprioritize, debug and stop Merlin/Seed training jobs, read their logs, and
  check free GPUs and devboxes via merlin-cli (job-v2). Use for a JobRun sid, seed.bytedance.net
  job URL, precheck, queue_priority, trial/pod logs, Robust restarts, execute-script, or
  merlin-cli 401/403 (提交任务、查任务、日志、优先级、卡位、预检、停任务).
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

Responses may be direct (`.data`) or wrapped (`.data.result.data`); check
`ResponseBase` inside the wrapper too, including mutation readback.

## Read the relevant procedure before acting

Resolve bundled `references/`, `scripts/` and `tests/` paths from this skill's root.
Task inputs and outputs (`pre.json`, `req.json`, `hot.json`, `trk.json`, `--out`)
stay relative to the chosen invocation cwd; do not move them into the installed skill.
Read only the procedure needed for the operation; the ground rules above always apply.

- Read status, queue, GPU counts, received requests, routine logs or a routine free-GPU summary: [Read a job and mjob](references/read-jobs.md). Prefer the bundled `scripts/mjob` for routine reads.
- Diagnose exits, restarts, hang/NCCL/Arnold or per-pod evidence; execute a command in a job (`execute-script` / WebShell): read [Logs and failure evidence](references/logs.md) before acting, including the credential and login-host rules.
- Submit or fork: [Submit](references/submit.md), including fresh precheck and readback.
- Reprioritize, stop or hot-update: [Change a live job](references/change-jobs.md). A hot update also requires [Submit](references/submit.md) steps 1–2 before preparing its payload.
- Query underlying resource details, devboxes, datacards or platform knowledge: [Resources](references/resources.md).
- Read per-step scalar metrics: [Tracking](references/tracking.md).
