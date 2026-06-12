---
effort: low
name: gpt-pro-relay
description: |
  Send a prompt to ChatGPT Pro Extended via gpt-pro-relay on macmini — over SSH from any
  other machine, or directly when invoked on macmini itself. Use for "ask gpt-pro", "send
  to gpt-pro", "use gpt-pro", "Pro Extended take", "ask the deep model", or "second
  opinion from chatgpt pro". The wrapper (not the caller) polls through flaky
  networks; the agent fires one backgrounded call and waits for the notification.
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

## Quick start

The happy path, in execution order — the sections below are the authoritative
detail; this is the shape:

1. **Time gate** — Pro Extended runs take 5–20 min. If the user didn't name
   gpt-pro, confirm first; if they did, just go.
2. **Compose a self-contained prompt in a file** — GPT-Pro can't see anything
   local to you (codebase, shell, this conversation), so paste in every file,
   excerpt, and prior decision it needs. It *can* search the public web, so when
   the answer turns on external facts, include the grounding directive — see
   "Grounding external facts".
3. **Run it as a Bash-tool call** — mandatory on every call (a bare shell command
   is a trap: it blocks the turn and drops the envelope). Issue exactly:
   ```text
   command:           gpt-pro < prompt.md
   run_in_background: true
   timeout:           7260000        # 121 min — see Background and timeout
   ```
   Response → stdout; `run_id=<id>` and a copy-paste `recover_with=…` line → stderr.
4. **Wait for the completion notification — do NOT poll.** A backgrounded call
   returns a task id immediately (expected); the harness notifies you when it exits.
   Don't re-run `gpt-pro` or re-read the task output in a loop meanwhile — the
   wrapper is already polling through any drops.
5. **On failure, reattach (also backgrounded — recovery, not polling).** If the
   call dies or exits 124/255, the macmini worker survives. Take the **literal**
   run-id from the task output (`run_id=<id>` / `recover_with=…` on the first stderr
   lines) and reattach in the same envelope: `gpt-pro --run-id <id>`. Then map the
   exit code — see "If it fails".

## Invocation

Compose the prompt in a file (so `$`, backticks, and heredoc markers don't get mangled),
then pipe it on stdin:

```bash
gpt-pro < prompt.md
```

That's the whole call. `gpt-pro` is on PATH (added in `~/.zshenv`). The response is on
stdout; the run-id, diagnostics, and the engine's JSONL are on stderr. Always issue it
inside the Bash-tool envelope (`run_in_background: true`, `timeout: 7260000`) — see
Background and timeout.

```
gpt-pro [--max-wait <sec>] [--dry-run] < prompt.md   # new run
gpt-pro --run-id <id> [--max-wait <sec>]             # reattach / recover
```

| Flag | Purpose |
|---|---|
| `--run-id <id>` | Reattach to an existing run (recovery); skips submit, then waits for the result (blocking fetch on macmini, poll loop over SSH). |
| `--max-wait <sec>` | Poll deadline on the SSH path (default 7200 = 120 min — generous so a queued run isn't killed mid-flight). Ignored on macmini, where the engine's own 60-min cap and the Bash-tool `timeout` bound the run. |
| `--dry-run` | Print the resolved run-id and transport, then exit. No Pro quota used. |

Want a durable copy? Keep the streams **separate**: `gpt-pro < prompt.md > answer.md 2> gpt-pro.log` — never `2>&1` (it contaminates the answer and buries the `run_id`). Optional: the backgrounded task output already captures both streams, so a redirect is only for a persistent on-disk artifact.

If `gpt-pro: command not found` (a sandboxed or reset-env shell that didn't inherit the
`.zshenv` PATH), run the identical command by absolute path:
`~/.claude/skills/gpt-pro-relay/scripts/gpt-pro < prompt.md`.

## Prompts must be self-contained

GPT-Pro runs in a ChatGPT web tab. **It cannot see anything local to you — your codebase,
your shell, the files on your machine, or this conversation.** Every byte of *local* context
it needs must be inside the prompt you pipe in: if you reference a file path, paste its
contents; if a decision earlier in this session shapes the answer, paste that excerpt. It
*can*, however, reach the **public web** through its own browser/search tool — so don't paste
public docs it can fetch itself; tell it what to look up (see "Grounding external facts"). The
rule: private-local context is pasted in; public-external facts are searched for.

Err toward more context, not less — the 1 MB submission cap is generous, and a run that
fails for missing context still burns 5–20 min. Compose the prompt in a file.
Prefer the **Write tool** — it's in this skill's `allowed-tools` (bare `mktemp`/`cat`/heredocs
may not be), and it sidesteps `$`/backtick/heredoc mangling entirely. In a plain shell you
can instead build it inline:

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

## Grounding external facts

Local context is pasted in (above); **public, external facts are searched for.** When the
answer turns on information not in the pasted context, GPT-Pro must search the web and ground
its answer in cited sources. The directive below is **conditional** — a no-op on pure-reasoning
tasks — so include it in `prompt.md` whenever the task could depend on external facts. Paste it
verbatim:

```text
## Grounding external facts

Some questions turn on facts not in the pasted context — current versions, releases, dates,
prices, API/library behavior, specs, benchmarks, CVEs, recent events, current best practices:
anything that changes over time or that you'd otherwise answer from memory. For any such fact
you MUST use web search and ground the answer in what you find — do not answer external or
time-sensitive questions from memory.

When you search:
- Corroborate each load-bearing fact across at least two independent sources (prefer
  primary/official). If sources conflict or only one exists, say so and mark it low-confidence.
- Cite the specific page URL you actually opened, inline next to the claim — never a homepage,
  a search-results page, or a URL reconstructed from memory. Didn't open it? Don't cite it.
- End with a `## Sources` list: every URL you opened, each with one line on what you took from it.

Do NOT search when the task is self-contained — pure reasoning, math, or analysis of the pasted
code/text — or to confirm stable facts you already know. If you didn't need external facts, say
so in one line ("No external sources needed — reasoning over the pasted material.") rather than
just omitting citations: that line tells the caller a deliberate skip from a missed one.
```

**On return**, verify grounding cheaply: a fact-dependent answer should carry inline URLs and a
`## Sources` list — spot-check one or two with the Read/WebFetch tools (does the page resolve,
does it actually say that) before relying on it. A fact-heavy answer with no sources *and* no
"no external sources needed" line is ungrounded — re-prompt or discount it.

## Calibration block

For **judgment tasks** — analysis, recommendations, design, second opinions — have gpt-pro end
with a reasons-based calibration block. Its slowness and cost make a self-graded score *more*
tempting and *no* better calibrated, so ask for assumptions and failure modes, not a number.
**Skip it for deterministic lookups or mechanical transforms.** Paste this into `prompt.md`
(alongside the grounding directive when both apply):

```text
## Calibration

End your response with this block exactly:
- Key assumptions: 1-3 the answer depends on ("none material" only if true)
- Most likely wrong because: the strongest failure mode, missing info, or counterargument
- Would change my conclusion: the specific fact, test, or counterexample that would flip it
- Best next check: the single source, test, or lookup that would most reduce uncertainty
- Verify before acting: specific current/high-stakes claims to check ("none" for pure reasoning)

No numeric %, probability, star rating, or High/Medium/Low label — this block is for routing and
verification, not a calibrated probability.
```

**On return**, treat it as the action plan: run the `Best next check` and verify the listed
claims before relying on the answer. Because a re-query costs another 5–20 min, a
targeted check is almost always cheaper than re-running. Discount any answer that self-asserts
confidence in place of naming its assumptions.

## Time gate

Pro Extended runs take 5–20 minutes per prompt. Confirm with the user before invoking *unless* they explicitly named gpt-pro:

> "Send this to gpt-pro? It'll take ~5–20 min."

If they invoked the skill directly or named gpt-pro in their request, they've consented — just go.

## Background and timeout

On a remote machine `gpt-pro` runs its own poll loop for up to `--max-wait` (default 120 min); on macmini it blocks on the engine directly (the engine's cap and the Bash-tool `timeout` bound it there). The default is deliberately generous — a queued or long Pro run killed by a tight timeout wastes the tokens it already spent, so favor completion. Either way, always wrap the Bash invocation in:

- `run_in_background: true`
- `timeout: 7260000` — Bash-tool timeout in **milliseconds** = **121 min**, 60 s of slack over the default `--max-wait 7200` (= 120 min) so the tool doesn't preempt the wrapper's final diagnostic. If you change `--max-wait`, set this to at least `(--max-wait + 60) × 1000`.

Three clocks, inner → outer: the engine's **60-min** per-run cap → the wrapper's **`--max-wait`** poll deadline (default 120 min, SSH path) → the Bash-tool **`timeout`** (121 min). A `reason: timeout` (exit 3) is the *engine* cap firing, not `--max-wait`.

Wait for the completion notification. Do NOT poll from the agent side — the wrapper is already polling (the affirmative wait primitive is in Quick start step 4).

## Recovery

`gpt-pro` prints `run_id=<id>` and a ready-to-run `recover_with=gpt-pro --run-id <id>` line to stderr at the start — both land in the background task's output file. Capture the **literal** id from there; a `$RUN_ID` shell variable does **not** survive into a later Bash-tool call. If the caller dies, or the wrapper exits 124 (timed out, still pending) or 255 (SSH transport unknown), the worker on macmini keeps running. Reattach with the same id, inside the same envelope (`run_in_background: true`, `timeout: 7260000`) — this is recovery, not the forbidden polling:

```bash
gpt-pro --run-id ask-20260611T002710Z-…    # the literal id, not "$RUN_ID"
```

This skips submit and waits for the existing run to complete (blocking fetch on macmini, poll loop over SSH). If the run already finished but you lost the output, read it off macmini directly — quote the remote command so `~` expands on macmini, not locally:

```bash
ssh macmini "cat ~/.gpt-pro/runs/<run_id>/response.md"
```

## Concurrency

Up to `GPT_PRO_MAX_PARALLEL` (default 3) `gpt-pro` calls run in parallel — each worker gets its own tab in a single shared Chrome process. Beyond the cap, additional workers queue on a file-lock semaphore in `~/.gpt-pro/slots/` and wait for a slot to free up. Pro Extended runs are 5–20 min each, so a queued run can be in that same magnitude — don't set `--max-wait` (or the Bash-tool timeout) shorter than that.

Chrome stays alive between runs (no per-call launch cost after the first) — an invoking agent never needs to tear it down. `ssh macmini gpt-pro-relay close-chrome` is **operator maintenance only** (it refuses by default if any worker is in flight; `--force` kills anyway) — don't run it as part of normal use or recovery. Raising `GPT_PRO_MAX_PARALLEL` above the default is a knob, not a free upgrade: parallel bursts on one ChatGPT Pro session are an account-side anti-abuse signal. If `network.json` starts showing 429s, captcha redirects, or unexplained `needs_reauth` after parallel use, drop it back to `1`.

## If it fails

The wrapper's **exit code** is the agent's decision key — every code maps to one action. Empty prompts, oversized prompts (>1 MB), and malformed run-ids are caught *before* any submission (exit 2 — no quota burned).

| exit | meaning | do next |
|---|---|---|
| 0 | response on stdout (non-empty) | use it |
| 1 | engine error, or rc 0 with an empty body (extraction failure) | read the `reason` in stderr → reason table below; if none, inspect `run_dir`. Do **not** blindly resubmit (would re-burn quota) |
| 2 | usage error (empty/oversized prompt, bad run-id, bad flag) — no quota burned | fix the call from the stderr message; do **not** reattach |
| 3 | worker hit the engine's 60-min cap (`reason: timeout`) | terminal — don't reattach (a re-fetch just re-times-out); inspect `streaming-*.png`, surface to the user |
| 4 | run_dir not found (reattach to a run that never landed) | the submit never reached macmini — start a **fresh** run (drop `--run-id`) |
| 124 | `--max-wait` elapsed, run still pending | reattach: `gpt-pro --run-id <id>` (same envelope) |
| 255 | SSH transport state unknown | reattach **first**: `gpt-pro --run-id <id>`; only if *that* exits 4 did the submit never land — then resubmit. Never start a fresh run before reattaching (risks a duplicate, double-quota run) |

On a non-zero exit the engine's terminal stderr JSON carries a `reason`; for exit 1 it disambiguates the cause:

| reason | exit | meaning | what to do |
|---|---|---|---|
| `needs_reauth` | 1 | session cookie missing or expired | tell the user to run `gpt-pro-relay login` on macmini |
| `model_select_failed` | 1 | couldn't get Pro selected in the picker | selectors drifted; surface `run_dir` to the user |
| `reasoning_mismatch` | 1 | Extended Pro chip absent after model select | same — selectors drifted |
| `worker_exception` | 1 | Python exception in the worker | inspect `run_dir/worker.stderr` (structured stage trace) — the last `stage` before the error tells you where it died |
| `timeout` | 3 | no completion within 60 min | inspect `run_dir/streaming-*.png` |
| `run_id_conflict` | 2 | reattach id collided with a different run | pick a fresh run (drop `--run-id`) |

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
