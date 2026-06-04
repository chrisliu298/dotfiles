---
effort: low
name: gpt-pro-relay
description: |
  Send a prompt to ChatGPT Pro Extended via gpt-pro-relay on macmini — over SSH from any
  other machine, or directly when invoked on macmini itself. Use for "ask gpt-pro", "send
  to gpt-pro", "use gpt-pro", "Pro Extended take", "ask the deep model", or "second
  opinion from chatgpt pro". Resilient to flaky networks via short-session polling.
allowed-tools: Bash(gpt-pro:*), Bash(~/.claude/skills/gpt-pro-relay/scripts/gpt-pro:*), Bash(ssh:*), Read, Write
user-invocable: true
---

# gpt-pro-relay

One prompt in, one response out. The `gpt-pro` wrapper composes the whole call: it
generates the run-id, picks local-vs-SSH transport, submits, polls with backoff over
flaky links, demuxes exit codes, and prints the response to stdout. The browser
automation runs on macmini against a dedicated logged-in profile; a detached worker does
the work so transport drops (or parent death) don't kill it — reconnect with
`gpt-pro --run-id <id>`.

## Invocation

Compose the prompt in a file (so `$`, backticks, and heredoc markers don't get mangled),
then pipe it on stdin:

```bash
gpt-pro < prompt.md
```

That's the whole call. `gpt-pro` is on PATH (added in `~/.zshenv`). The response is on
stdout; the run-id, diagnostics, and the engine's JSONL are on stderr.

```
gpt-pro [--max-wait <sec>] [--dry-run] < prompt.md   # new run
gpt-pro --run-id <id> [--max-wait <sec>]             # reattach / recover
```

| Flag | Purpose |
|---|---|
| `--run-id <id>` | Reattach to an existing run (recovery); skips submit, then waits for the result (blocking fetch on macmini, poll loop over SSH). |
| `--max-wait <sec>` | Poll deadline on the SSH path (default 7200 = 120 min — generous so a queued run isn't killed mid-flight). Ignored on macmini, where the engine's own 60-min cap and the Bash-tool `timeout` bound the run. |
| `--dry-run` | Print the resolved run-id and transport, then exit. No Pro quota used. |

Want the answer in a file? Redirect: `gpt-pro < prompt.md > answer.md`.

If `gpt-pro: command not found` (a sandboxed or reset-env shell that didn't inherit the
`.zshenv` PATH), run the identical command by absolute path:
`~/.claude/skills/gpt-pro-relay/scripts/gpt-pro < prompt.md`.

## Prompts must be self-contained

GPT-Pro runs in a ChatGPT web tab. **It cannot read your codebase, run shell commands,
follow links, or see anything from this local conversation.** Every byte it needs to
answer must be inside the prompt you pipe in. If you reference a file path, paste its
contents. If a decision earlier in this session shapes the answer, paste that excerpt.

Err toward more context, not less — the 1 MB submission cap is generous, and a run that
fails for missing context still burns 5–20 min of Pro quota. Compose the prompt in a file
so contents with `$`, backticks, or heredoc markers don't get mangled:

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
} > "$PROMPT_FILE"

gpt-pro < "$PROMPT_FILE"
```

For recurring tasks, factor the composer into a small `compose-prompt.sh` in the project —
keep the file list and section headers there rather than rewriting them on every call.

## Cost gate

Pro Extended runs cost real Pro quota and take 5–20 minutes per prompt. Confirm with the user before invoking *unless* they explicitly named gpt-pro:

> "Send this to gpt-pro? It'll take ~5–20 min and use your Pro quota."

If they invoked the skill directly or named gpt-pro in their request, they've consented — just go.

## Background and timeout

On a remote machine `gpt-pro` runs its own poll loop for up to `--max-wait` (default 120 min); on macmini it blocks on the engine directly (the engine's cap and the Bash-tool `timeout` bound it there). The default is deliberately generous — a queued or long Pro run killed by a tight timeout wastes the tokens it already spent, so favor completion. Either way, always wrap the Bash invocation in:

- `run_in_background: true`
- `timeout: 7260000` (120 min)

Wait for the completion notification. Do NOT poll the output from the agent side — the wrapper is already polling. Keep the Bash-tool `timeout` at or above `--max-wait`.

## Recovery

`gpt-pro` prints `run_id=<id>` to stderr at the start. If the caller dies, or the wrapper exits 124 (timed out, still pending) or 255 (SSH transport unknown), the worker on macmini keeps running. Reattach with the same id:

```bash
gpt-pro --run-id "$RUN_ID"
```

This skips submit and waits for the existing run to complete (blocking fetch on macmini, poll loop over SSH). If the run already finished but you lost the output, read it off macmini directly:

```bash
ssh macmini cat ~/.gpt-pro/runs/"$RUN_ID"/response.md
```

## Concurrency

Up to `GPT_PRO_MAX_PARALLEL` (default 3) `gpt-pro` calls run in parallel — each worker gets its own tab in a single shared Chrome process. Beyond the cap, additional workers queue on a file-lock semaphore in `~/.gpt-pro/slots/` and wait for a slot to free up. Pro Extended runs are 5–20 min each, so a queued run can be in that same magnitude — don't set `--max-wait` (or the Bash-tool timeout) shorter than that.

Chrome stays alive between runs (no per-call launch cost after the first). Tear it down explicitly with `ssh macmini gpt-pro-relay close-chrome` — it refuses by default if any worker is in flight, pass `--force` to kill anyway. Raising `GPT_PRO_MAX_PARALLEL` above the default is a knob, not a free upgrade: parallel bursts on one ChatGPT Pro session are an account-side anti-abuse signal. If `network.json` starts showing 429s, captcha redirects, or unexplained `needs_reauth` after parallel use, drop it back to `1`.

## Errors

When `gpt-pro` exits non-zero, the engine's terminal stderr JSON has a `reason` field. Empty prompts, oversized prompts (>1 MB), and malformed run-ids are caught by the wrapper *before* any submission (exit 2, message on stderr — no quota burned).

| reason | meaning | what to do |
|---|---|---|
| `needs_reauth` | session cookie missing or expired | Tell the user to run `gpt-pro-relay login` on macmini |
| `model_select_failed` | couldn't get Pro selected in the picker | Selectors drifted; surface `run_dir` to the user |
| `reasoning_mismatch` | Extended Pro chip absent after model select | Same — selectors drifted |
| `worker_exception` | Python exception in the worker | Inspect `run_dir/worker.stderr` (structured stage trace) — the last `stage` before the error tells you where it died |
| `timeout` | no completion within 60 min | Inspect `run_dir/streaming-*.png` |
| `run_id_conflict` | reattach id collided with a different run | Pick a fresh run (drop `--run-id`) |

## Exit codes

| code | meaning |
|---|---|
| 0 | response on stdout, non-empty (success) |
| 1 | error, or engine returned rc 0 with an empty body (likely extraction failure) — read stderr; inspect `run_dir` on macmini |
| 2 | usage error (empty prompt, prompt too large, invalid run-id, bad flag) |
| 3 | worker `timeout` (didn't finish within 60 min) |
| 4 | run_dir not found (reattach to a run that never reached macmini) |
| 124 | caller-side `--max-wait` elapsed, run still pending — recover with `--run-id` |
| 255 | SSH transport failed and the run's state is unknown — retry with `--run-id` |

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
| Tolerating a flaky network on a 5–20 min reasoning run | Yes — `gpt-pro` polls through drops without intervention |
| Driving your local live Chrome with any model + effort | Use a local Chrome-driving skill instead |
| Multi-turn follow-ups in the same chat | Doesn't fit — gpt-pro is one-shot per invocation |

## Multi-turn

gpt-pro is one-shot per invocation — every call is a fresh ChatGPT conversation. To continue a thread, paste the prior response into the next prompt yourself. The dedicated profile retains login but does not persist conversation context across calls.
