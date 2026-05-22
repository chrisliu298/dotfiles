---
name: gpt-pro-relay
description: |
  Send a prompt to ChatGPT Pro Extended via gpt-pro-relay on macmini — over SSH from any
  other machine, or directly when invoked on macmini itself. Use for "ask gpt-pro", "send
  to gpt-pro", "use gpt-pro", "Pro Extended take", "ask the deep model", or "second
  opinion from chatgpt pro". Resilient to flaky networks via short-session polling.
allowed-tools: Bash(ssh:*), Bash(gpt-pro-relay:*), Bash(uuidgen:*), Bash(date:*), Bash(hostname:*), Read, Write
user-invocable: true
---

# gpt-pro-relay

One prompt in, one response out. The browser automation runs on macmini against a dedicated logged-in profile. The work is done by a detached worker so transport drops (or parent death) don't kill it — you can reconnect and `fetch` the result.

## Pick the right transport: local vs SSH

**Run `hostname -s` first.** If it returns `macmini`, you're already on the host — skip SSH entirely and use the [Direct invocation on macmini](#direct-invocation-on-macmini) form below. Wrapping a local call in `ssh macmini ...` will fail (there's no sshd loopback configured for the agent's identity, and even if there were, the SSH-drop polling machinery is pure overhead for a local call).

From any other machine (l40s, macbookpro16, …), use the [SSH polling pattern](#the-command) — that's what the rest of this doc describes.

## Prompts must be self-contained

GPT-Pro runs in a ChatGPT web tab. **It cannot read your codebase, run shell commands, follow links, or see anything from this local conversation.** Every byte it needs to answer must be inside the heredoc body. If you reference a file path, paste its contents. If a decision earlier in this session shapes the answer, paste that excerpt.

Err toward more context, not less — the 1 MB submission cap is generous, and a run that fails for missing context still burns 5–20 min of Pro quota.

Compose the prompt in a file (so file contents with `$`, backticks, or heredoc markers don't get mangled), then submit it via stdin redirect:

```bash
PROMPT_FILE=$(mktemp)
{
  cat <<'TASK'
<one-sentence outcome>

Success criteria:
- ...
TASK

  echo
  echo '=== src/foo.py ==='
  cat src/foo.py

  echo
  echo '=== tests/test_foo.py ==='
  cat tests/test_foo.py
} > "$PROMPT_FILE"

# Then in Phase 1 below, replace the inline heredoc with a stdin redirect:
ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay ask --run-id "$RUN_ID" --no-wait < "$PROMPT_FILE"
```

For recurring tasks, factor the composer into a small `compose-prompt.sh` in the project — keep the file list and section headers there rather than rewriting them on every call.

## Direct invocation on macmini

When already on macmini, skip SSH and the polling loop — just call `gpt-pro-relay` directly with the blocking single-call form. There's no transport that can drop, so the polling machinery is overhead.

```bash
RUN_ID="ask-$(date -u +%Y%m%dT%H%M%SZ)-$(uuidgen | tr '[:upper:]' '[:lower:]')"
gpt-pro-relay ask --run-id "$RUN_ID" < "$PROMPT_FILE"
```

Wrap in `run_in_background: true, timeout: 1800000` (30 min). Recovery on parent death is `gpt-pro-relay fetch "$RUN_ID"` (no SSH). Everything else is identical to the SSH path: same artifacts in `~/.gpt-pro/runs/<run_id>/`, same exit codes, same error reasons in the terminal stderr JSON.

If `gpt-pro-relay: command not found`, the `~/.local/bin/gpt-pro-relay` symlink is gone — fall back to `/Users/chrisliu298/Developer/GitHub/gpt-pro/.venv/bin/gpt-pro-relay`.

The rest of this skill (SSH polling, fetch loop, transport-drop recovery) is for callers on other machines. Skip it.

## The command

> **About the bare `gpt-pro-relay` command:** it's not a system tool. The remote shell finds it because the project ships a console script (in `.venv/bin/gpt-pro-relay`) that's symlinked into a directory on the SSH non-interactive `PATH` (`~/.local/bin/gpt-pro-relay` here, picked up via `~/.zshenv`). If you ever see `gpt-pro-relay: command not found`, the symlink got removed — fall back to the absolute venv path or recreate `~/.local/bin/gpt-pro-relay`.

Two phases: a 1-second `--no-wait` submit, then a polling loop where each
SSH session lasts ≤60s. A NAT/firewall idle-drop on any single session
just costs one retry instead of the whole run.

```bash
SSH_OPTS=(-S none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4)
RUN_ID="ask-$(date -u +%Y%m%dT%H%M%SZ)-$(uuidgen | tr '[:upper:]' '[:lower:]')"

# Phase 1: submit (≤1s SSH session; idempotent on same run_id + same prompt)
ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay ask --run-id "$RUN_ID" --no-wait <<'PROMPT'
... the prompt ...
PROMPT
submit_rc=$?
if (( submit_rc != 0 )); then
  echo "gpt-pro-relay Phase 1 submit failed (rc=$submit_rc); skipping fetch loop. Safe to retry with the same RUN_ID — same prompt bytes attach idempotently." >&2
  exit "$submit_rc"
fi

# Phase 2: poll (each SSH session ≤60s, exponential backoff on transport drop)
deadline=$((SECONDS + 3600)); delay=5
while (( SECONDS < deadline )); do
  out=$(ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay fetch "$RUN_ID" --timeout 60 2>/tmp/gpt-pro-$RUN_ID.err); rc=$?
  case $rc in
    0)   printf '%s' "$out"; exit 0 ;;
    124) delay=5; continue ;;                              # still pending
    255) sleep "$delay"; (( delay < 30 )) && delay=$((delay * 2)) ;;  # ssh died
    *)   cat /tmp/gpt-pro-$RUN_ID.err >&2; exit "$rc" ;;   # terminal error
  esac
done
echo "gpt-pro-relay overall timeout for $RUN_ID" >&2; exit 124
```

- **stdout** of the whole block = the ChatGPT response (markdown, captured via Copy button when possible)
- **stderr** = newline-delimited JSON: a `submitted` line from Phase 1, then a terminal `ok` / `error` / `timeout` from the final fetch. The `ok` line includes `extraction: "copy_button" | "innertext"` so you can audit which capture path won.
- **exit 0** = success. Other codes mean inspect stderr.

Always pass `--run-id`. Use a UUID or timestamp+UUID — anything matching `[A-Za-z0-9._-]+`, max **100 chars**. Same id + same prompt bytes attaches to an existing run instead of submitting a new one (`submitted` JSONL gains `"attached": true`), so the Phase 1 submit is safe to retry on transport flakiness.

**Do not add descriptive labels** (`ask-frontier-vlms-comparison-...`). The canonical `ask-<timestamp>-<uuid>` form (≈57 chars) is already opaque-by-design; appending a topic slug routinely pushes the id past 100 chars and gpt-pro-relay rejects it with `invalid run_id: '...'` (exit 2). If you need a human-readable handle for your own tracking, keep it outside the run_id (in the task description, a local variable, etc.).

Use a heredoc, never `echo "$prompt"` — bare echo mangles `$`, backticks, and quotes.

### SSH options (load-bearing)
- `ConnectTimeout=15` — bail in 15s on a dead connect.
- `ServerAliveInterval=15` + `ServerAliveCountMax=4` — bound a dead established session to ~60s.
- `BatchMode=yes` — never prompt for a password (would hang an agent forever).
- `-S none` — no ControlMaster reuse; reuse can resurrect a stale network path.

### Fallback: blocking single-call

For stable links, the older blocking form still works:

```bash
ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay ask --run-id "$RUN_ID" <<'PROMPT'
... the prompt ...
PROMPT
```

This holds the SSH session open for the full 5–20 min reasoning duration. A single NAT/firewall idle-drop kills the run from the caller's view (the worker on macmini survives — recover with `gpt-pro-relay fetch $RUN_ID`, ideally inside the polling loop). Default to the polling pattern.

## Output: stdout or file

By default the response is on stdout (from the polling block's `printf '%s' "$out"` on success). If you'd rather end up with a file:

**Caller-side redirect** — file on the *caller's* machine:

```bash
# In the polling block, replace the success branch with:
0)   printf '%s' "$out" > /tmp/response-$RUN_ID.md; exit 0 ;;
```

**`--output PATH` on `fetch`** — file on macmini; the polling block's stdout stays empty; terminal stderr JSON gains `"output": "<resolved-path>"`:

```bash
# Replace the fetch line in the polling block with:
out=$(ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay fetch "$RUN_ID" --output ~/responses/$RUN_ID.md --timeout 60 2>/tmp/gpt-pro-$RUN_ID.err); rc=$?
# Read it back from macmini when the run is done:
ssh "${SSH_OPTS[@]}" macmini cat ~/responses/$RUN_ID.md
```

Caller-side redirect is one fewer SSH hop. `--output` on `fetch` is mainly useful when driving gpt-pro-relay from the same host (i.e. an agent running directly on macmini). `--output` on `ask --no-wait` is silently ignored — the response only exists at fetch time.

## Cost gate

Pro Extended runs cost real Pro quota and take 5–20 minutes per prompt. Confirm with the user before invoking *unless* they explicitly named gpt-pro:

> "Send this to gpt-pro? It'll take ~5–20 min and use your Pro quota."

If they invoked the skill directly or named gpt-pro in their request, they've consented — just go.

## Background and timeout

The polling block above runs up to 60 min wall-clock. Always wrap the whole bash invocation in:

- `run_in_background: true`
- `timeout: 3600000` (60 min)

Wait for the completion notification. Do NOT poll the output file from the agent side — the bash loop is already polling.

## Manual recovery

If you launched a *blocking* `ask` (not the polling pattern) and SSH dropped, do NOT re-run `ask` without `--no-wait` — that holds another long SSH session open. Recover by entering the polling loop with the same `RUN_ID`, or do a one-shot manual fetch:

```bash
ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay fetch "$RUN_ID"   # blocks until ready
ssh "${SSH_OPTS[@]}" macmini gpt-pro-relay fetch "$RUN_ID" --timeout 0  # non-blocking check
```

Exit 124 = still running. Exit 4 = `not_found` (the run never reached macmini — SSH died before the parent read stdin; submit again with the same run_id).

## Idempotent re-attach

`ask` with the **same `--run-id` and same prompt bytes** attaches to the existing run instead of submitting a new one. The `submitted` JSONL gains `"attached": true`. This is what makes Phase 1 of the polling pattern safe to retry — if the submit SSH session drops mid-flight, just run it again with the same `RUN_ID`.

Same `run_id` with a **different** prompt exits 2 with `run_id_conflict` — gpt-pro-relay refuses to overwrite, by design.

## Concurrency

Up to `GPT_PRO_MAX_PARALLEL` (default 3) `ask` calls to macmini run in parallel — each worker gets its own tab in a single shared Chrome process. Beyond the cap, additional workers queue on a file-lock semaphore in `~/.gpt-pro/slots/` and wait for a slot to free up. The wait is recorded in `worker.stderr` as `{"stage":"slot_queued","max_parallel":N}` followed by `{"stage":"slot_acquired","slot_id":I,"waited_secs":N}`. Pro Extended runs are 5–20 min each, so a queued run can be in that same magnitude — don't add caller-side timeouts shorter than that.

Chrome stays alive between runs (no per-call launch cost after the first). Tear it down explicitly with `ssh macmini gpt-pro-relay close-chrome` — it refuses by default if any worker is in flight, pass `--force` to kill anyway. Raising `GPT_PRO_MAX_PARALLEL` above the default is a knob, not a free upgrade: parallel bursts on one ChatGPT Pro session are an account-side anti-abuse signal. If `network.json` starts showing 429s, captcha redirects, or unexplained `needs_reauth` after parallel use, drop it back to `1`.

## Errors

The terminal stderr JSON's `reason` field tells you what failed:

| reason | meaning | what to do |
|---|---|---|
| `needs_reauth` | session cookie missing or expired | Tell the user to run `gpt-pro-relay login` on macmini |
| `model_select_failed` | couldn't get Pro selected in the picker | Selectors drifted; surface `run_dir` to the user |
| `reasoning_mismatch` | Extended Pro chip absent after model select | Same — selectors drifted |
| `worker_exception` | Python exception in the worker | Inspect `run_dir/worker.stderr` (structured stage trace) — the last `stage` before the error tells you where it died |
| `timeout` | no completion within 60 min | Inspect `run_dir/streaming-*.png` |
| `empty_prompt` | nothing on stdin | You forgot the heredoc |
| `prompt_too_large` | prompt > 1 MB | Trim or split the prompt; the cap is at submission, no Pro quota burned |
| `run_id_conflict` | same run_id, different prompt | Pick a fresh run_id |
| `invalid run_id: '...'` (usage error, exit 2) | run_id exceeded 100 chars or contained chars outside `[A-Za-z0-9._-]` | Drop any descriptive slug; use the canonical `ask-<timestamp>-<uuid>` form |
| `not_found` | fetch couldn't find run_dir | The `ask` parent died before submission; re-submit fresh |

## Exit codes

| code | meaning |
|---|---|
| 0 | response on stdout, status ok (or `ask --no-wait` submitted; nothing on stdout) |
| 1 | error — read stderr `reason` |
| 2 | usage error (empty prompt, prompt_too_large, conflict, invalid run_id) |
| 3 | worker `timeout` (didn't finish within 60 min) |
| 4 | run_dir not found (fetch only) |
| 124 | wait timed out, run still pending |
| 255 | SSH transport failure (the polling loop catches this and retries) |

## Run artifacts

`run_dir` lives on macmini at `~/.gpt-pro/runs/<run_id>/`:

- `prompt.md`, `response.md`, `meta.json`, `result.json`
- `pre-send.png`, `streaming-NNN.png`, `final.png`, `error-*.png`
- `final.html`, `network.json`
- `worker.stdout` — detached worker's stdout (usually empty)
- `worker.stderr` — **structured JSONL stage trace**: one line per stage (`start`, `slot_queued`/`slot_acquired`, `chrome_cdp_ready`/`chrome_connected`/`chrome_activated`, `logged_in`, `model_verified`, `prompt_typed`, `sent`, `extracted`, `finished`, plus `error` / `orphan_kill_*` / `*_skipped`). When something fails mid-run, this is the fastest path to the failure point — the last stage before the `error` line tells you where it died.

Reach for them via `ssh macmini cat <run_dir>/<file>` or `ssh macmini ls <run_dir>` when diagnosing.

## When gpt-pro-relay fits

| Situation | Verdict |
|---|---|
| Pro Extended reasoning, from any machine with SSH to macmini | Yes |
| Tolerating a flaky network on a 5–20 min reasoning run | Yes — the polling pattern handles drops without intervention |
| Driving your local live Chrome with any model + effort | Use a local Chrome-driving skill instead |
| Multi-turn follow-ups in the same chat | Doesn't fit — gpt-pro-relay is one-shot per invocation |

## Multi-turn

gpt-pro-relay is one-shot per invocation — every call is a fresh ChatGPT conversation. To continue a thread, paste the prior response into the next prompt yourself. The dedicated profile retains login but does not persist conversation context across calls.
