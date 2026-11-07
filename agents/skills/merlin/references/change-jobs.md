## Change a live job

```bash
$M job-v2 run-trials update --json '{"sid":"<trial>","queue_priority":40}'   # trial sid, not run sid
$M job-v2 runs stop --json '{"sid":"<run>","stop_reason":"…"}'
$M job-v2 runs robust-hot-update --json "$(cat hot.json)"   # sid+version+attachments+job_config+resource_config
```

Hot update does **not** restart the running round by default: the new config takes effect at
the next Robust restart, in the same pods, without requeueing; pass `restart_now: true` to
restart immediately (useful when the round is crash-looping anyway). Build the body on the
**trial's runtime config**, not the static create request: `run-trials get --json
'{"sid":"<trial>","options":{"include_robust_runtime_config":true}}'` →
`data.robust_runtime_config`, whose `job_template_config` goes in as
`job_config.job_template_config`, with its i64 `version` echoed at the top level (0 the first
time); drop the read-only `is_effective` / `reason` / `cmd` / `roles` / `version` from inside
it. Changing `git_repo.commit_sha` this way works — measured 2026-11-06, a crashing arm picked
up the fixed commit on the next round. This subcommand takes `--json` only; it has no
`--from-file` (0.2.577). It returns code 0 with no `[CONFIRM]`, logs one `robust_hot_update` timeline
event, and `get-request-config` / `runs get` keep showing the old entrypoint — verify via the
next round's `set -x` echo in the logs. It can't change guaranteed/unguaranteed quota. The body
also needs a fresh create precheck sid in `request_context.precheck_sid`, same as Submit steps
1–2 (2026-10-25, d3c51d73). Read state back after every other change.


Before preparing a hot update, read [Submit](submit.md) steps 1–2 for the required fresh create precheck and request_context.precheck_sid.
