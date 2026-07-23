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

1. **Runtime** — Pro Extended runs take 5–20 min. Launch immediately; the
   invocation (direct, or a calling skill adding a gpt-pro lens) is the
   go-ahead. Never pause to confirm — mention the runtime only as passing
   context if useful.
2. **Put the question in a file; attach local files with `-f`** — GPT-Pro can't see
   anything local to you (codebase, shell, this conversation). Don't hand-`cat` files
   into the prompt: pass each one with **`-f <path>`** (repeatable; globs and
   `@base-relative` paths ok; whole dirs via `--include-tree`) and `gpt-pro` inlines
   them for you — validated, secret-scanned, and capped (5 MB composed) **before**
   submit, no quota burned on rejection. The file on stdin then holds just your
   question (plus any prior decisions only you know). GPT-Pro *can* search the public
   web, so for external facts include the grounding directive — see "Grounding external
   facts". (Hand-paste only when you need a surgical excerpt `-f` can't express.)
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
gpt-pro [-f <path>]... [--max-wait <sec>] [--dry-run] < prompt.md   # new run
gpt-pro --run-id <id> [--max-wait <sec>]                            # reattach / recover
```

| Flag | Purpose |
|---|---|
| `-f`, `--file <path>` | Attach a local file — contents inlined into the prompt (GPT-Pro can't read local paths). Repeatable; accepts a single-level glob (`-f 'src/*.py'`); `@`-prefix is optional sugar. |
| `--files-from <file>` | Inline every path listed in `<file>` (one per line; `#` comments ok). Repeatable. |
| `--include-tree <dir>` | Inline a directory recursively — capped, skips hidden/vendor/binary/secret files. Repeatable. |
| `--allow-secret <path>` | Permit one file the secret scan would otherwise refuse. Repeatable. |
| `--run-id <id>` | Reattach to an existing run (recovery); skips submit, then waits for the result (blocking fetch on macmini, poll loop over SSH). |
| `--max-wait <sec>` | Poll deadline on the SSH path (default 7200 = 120 min — generous so a queued run isn't killed mid-flight). Ignored on macmini, where the engine's own 60-min cap and the Bash-tool `timeout` bound the run. |
| `--dry-run` | Resolve the included files + run-id, report the composed size, then exit. No Pro quota used. |

Files are inlined through the shared **`filectx`** helper (sibling script): validated, secret-scanned (`FILECTX_SECRETS=deny\|warn\|off`), and capped — all **before** submit, so a bad file burns no quota.

Want a durable copy? Keep the streams **separate**: `gpt-pro < prompt.md > answer.md 2> gpt-pro.log` — never `2>&1` (it contaminates the answer and buries the `run_id`). Optional: the backgrounded task output already captures both streams, so a redirect is only for a persistent on-disk artifact.

If `gpt-pro: command not found` (a sandboxed or reset-env shell that didn't inherit the
`.zshenv` PATH), run the identical command from this skill's own `scripts/` directory —
the `gpt-pro` script sits beside this `SKILL.md` (`<this-skill-dir>/scripts/gpt-pro < prompt.md`).

## Prompts must be self-contained

GPT-Pro runs in a ChatGPT web tab. **It cannot see anything local to you — your codebase,
your shell, the files on your machine, or this conversation.** Every byte of *local* context
it needs must be inside the prompt: **attach files with `-f <path>`** (the wrapper inlines them
for you, validated/secret-scanned/capped before submit) and paste any non-file context (a
decision earlier in this session) into the stdin prompt. Use `-f` instead of hand-`cat`-ing —
it eliminates the most error-prone step (a forgotten file, mangled `$`/backticks, a silently
oversized prompt, an accidentally-pasted secret). It *can*, however, reach the **public web**
through its own browser/search tool — so don't attach public docs it can fetch itself; tell it
what to look up (see "Grounding external facts"). The rule: private-local context comes in via
`-f` (or paste); public-external facts are searched for.

Err toward more context, not less — the 5 MB submission cap is generous, and a run that
fails for missing context still burns 5–20 min. Put the **question** in a file (the **Write
tool** sidesteps `$`/backtick/heredoc mangling) and attach **files** with `-f`:

```bash
gpt-pro -f src/foo.py -f src/bar.py -f 'tests/*.py' < question.md
```

`question.md` holds only the question (plus any non-file context); each `-f` is inlined under a
fenced `## Included files` section. Preview exactly what would be sent — resolved files and the
composed byte total — without spending quota:

```bash
gpt-pro --dry-run -f src/foo.py --include-tree docs/ < question.md
```

You rarely need to assemble the prompt by hand now. If you must (a surgical excerpt `-f` can't
express), build the whole prompt in a file with the Write tool and pipe it in with no `-f`.

## Grounding external facts

Web research is one of gpt-pro's **two first-class modes** (alongside deep reasoning), not an
afterthought — but it stays **conditional**. Local context is pasted in (above); **public,
external facts are searched for.** When the answer turns on information not in the pasted
context, GPT-Pro must search the web and ground its answer in cited sources. The directive below
is **conditional** — a no-op on pure-reasoning tasks — so include it in `prompt.md` whenever the
task could depend on external facts. Paste it verbatim:

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

## Runtime note

Pro Extended runs take 5–20 minutes per prompt. Invoking gpt-pro is itself the go-ahead — whether the user named it directly or a calling skill (prism, goal-loop) added a gpt-pro lens. Just launch; do **not** pause to confirm or wait for a "continue". Mention the ~5–20 min runtime in passing only if it's useful context, never as a gate.

## Background and timeout

On a remote machine `gpt-pro` runs its own poll loop for up to `--max-wait` (default 120 min); on macmini it blocks on the engine directly (the engine's cap and the Bash-tool `timeout` bound it there). The default is deliberately generous — a queued or long Pro run killed by a tight timeout wastes the tokens it already spent, so favor completion. Either way, always wrap the Bash invocation in:

- `run_in_background: true`
- `timeout: 7260000` — Bash-tool timeout in **milliseconds** = **121 min**, 60 s of slack over the default `--max-wait 7200` (= 120 min) so the tool doesn't preempt the wrapper's final diagnostic. If you change `--max-wait`, set this to at least `(--max-wait + 60) × 1000`.

Three clocks, inner → outer: the engine's **60-min** per-run cap → the wrapper's **`--max-wait`** poll deadline (default 120 min, SSH path) → the Bash-tool **`timeout`** (121 min). A `status: "timeout"` (exit 3) is the *engine* cap firing, not `--max-wait`.

Wait for the completion notification. Do NOT poll from the agent side — the wrapper is already polling (the affirmative wait primitive is in Quick start step 4).

## Recovery

`gpt-pro` prints `run_id=<id>` and a ready-to-run `recover_with=gpt-pro --run-id <id>` line to stderr at the start — both land in the background task's output file. Capture the **literal** id from there; a `$RUN_ID` shell variable does **not** survive into a later Bash-tool call. If the caller dies, or the wrapper exits 124 (timed out, still pending) or 255 (SSH transport unknown), the worker on macmini keeps running. Reattach with the same id, inside the same envelope (`run_in_background: true`, `timeout: 7260000`) — this is recovery, not the forbidden polling:

```bash
gpt-pro --run-id ask-20260611T002710Z-…    # the literal id, not "$RUN_ID"
```

This skips submit and waits for the existing run to complete (blocking fetch on macmini, poll loop over SSH). If the run already finished but you lost the output, read it off macmini directly — but **read `result.json` FIRST: only `status: "ok"` makes `response.md` usable.** Quote the remote command so `~` expands on macmini, not locally:

```bash
ssh macmini "jq -r '.status, .reason, .model_audit' ~/.gpt-pro/runs/<run_id>/result.json"   # gate — must print ok
ssh macmini "cat ~/.gpt-pro/runs/<run_id>/response.md"                                      # ONLY when status == ok
```

**On `status: "error"` the body is QUARANTINED — diagnostic only, never an answer.** A rejected turn is complete, fluent, and on-topic; it differs from a verified one **only by provenance**, so "the text looks fine" is not a reason to use it — that inference is exactly how a GPT-5.5 answer once got laundered into a Sol lens. The two model-audit rejects rename the body to **`response.rejected.md`** (and set `rejected_response` in `result.json`) so that returning it takes deliberately naming a rejected file; every other error reason leaves it at `response.md`. **Both are void.** Recovery is a fresh run (new quota → the user decides) or an honest failure report — never a `cat`.

## Stopping a run

To interrupt a run you launched — you changed your mind, or a better answer arrived elsewhere — use `--stop` with the literal run-id (same envelope isn't needed; stop is quick and bounded):

```bash
gpt-pro --stop ask-20260611T002710Z-…    # the literal id, not "$RUN_ID"
```

It's **graceful and worker-driven**: the command writes a stop signal into the run_dir and the owning worker consumes it at its next phase gate. If the prompt **hasn't been sent yet**, the run is **dequeued** (no Pro quota spent). If it **was already sent**, the worker **clicks ChatGPT's Stop button** on the live turn to halt generation. Either way the run finalizes `status: stopped` and **no response is returned** (the partial is discarded, not published). All output is JSONL on stderr.

- **`stopped` / `already_finished` / `pending` → exit 0.** `pending` means the worker is alive and will consume the stop; poll `fetch` to confirm.
- **`no_live_worker` → exit 2.** No live worker consumed the signal (the worker process itself died, rare — workers survive SSH drops). Server-side generation may still be running; use the manual teardown path if you must halt it: `ssh macmini gpt-pro-relay close-chrome --force` is a blunt last resort (kills all tabs).
- **`not_found` → exit 4.** Unknown run-id.

Stop is **not** resubmit-safe cover for a mistake: a dequeued run spent no quota, but a run stopped after send already burned its reasoning up to the interrupt. Don't stop-then-resubmit reflexively.

## Concurrency

Up to `GPT_PRO_MAX_PARALLEL` (default **6**, clamped to a ceiling of **10**) `gpt-pro` calls run in parallel — each worker gets its own tab in a single shared Chrome process. Beyond the cap, additional workers queue on a file-lock semaphore in `~/.gpt-pro/slots/` and wait for a slot to free up (the worker logs `slot_queued`, then `slot_acquired` when it gets in). A queued run can wait **15+ min before it even reaches `sent`** (961 s observed), so total wall-clock = **queue wait + the 5–20 min run** — don't set `--max-wait` (or the Bash-tool timeout) shorter than that.

**A backgrounded call with no exit code is not a failed call.** Empty output + no completion notification = **still running**. Never diagnose it as lost, and never fresh-submit over it — that double-submits a live run and double-burns quota. Confirm liveness from the stage trace before concluding anything:

```bash
ssh macmini "tail -5 ~/.gpt-pro/runs/<run_id>/worker.stderr"
```

`slot_queued` with no `slot_acquired` = queued, waiting its turn. `sent` with no `finished` = generating. Either way: **wait.**

Chrome stays alive between runs (no per-call launch cost after the first) — an invoking agent never needs to tear it down. `ssh macmini gpt-pro-relay close-chrome` is **operator maintenance only** (it refuses by default if any worker is in flight; `--force` kills anyway) — don't run it as part of normal use or recovery. Raising `GPT_PRO_MAX_PARALLEL` above the default is a knob, not a free upgrade: parallel bursts on one ChatGPT Pro session are an account-side anti-abuse signal. If `network.json` starts showing 429s, captcha redirects, or unexplained `needs_reauth` after parallel use, drop it back to `1`.

## If it fails

The wrapper's **exit code** is the agent's decision key — every code maps to one action. Empty prompts, oversized prompts (>5 MB), and malformed run-ids are caught *before* any submission (exit 2 — no quota burned).

| exit | meaning | do next |
|---|---|---|
| 0 | response on stdout (non-empty) | use it |
| 1 | engine error, or rc 0 with an empty body (extraction failure) | read the `reason` in stderr → reason table below; if none, inspect `run_dir`. Do **not** blindly resubmit (would re-burn quota) |
| 2 | usage error (empty/oversized prompt, bad run-id, bad flag) — no quota burned | fix the call from the stderr message; do **not** reattach |
| 3 | worker hit the engine's 60-min cap (`status: "timeout"`) | terminal — don't reattach (a re-fetch just re-times-out); inspect `streaming-*.png`, surface to the user |
| 4 | run_dir not found (reattach to a run that never landed) | the submit never reached macmini — start a **fresh** run (drop `--run-id`) |
| 124 | `--max-wait` elapsed, run still pending | reattach: `gpt-pro --run-id <id>` (same envelope) |
| 255 | SSH transport state unknown | reattach **first**: `gpt-pro --run-id <id>`; only if *that* exits 4 did the submit never land — then resubmit. Never start a fresh run before reattaching (risks a duplicate, double-quota run) |

On a non-zero exit the engine's terminal stderr JSON carries a `reason`. **Exit 1 is the catch-all — every engine error returns it** (`err()` hardcodes `exit_code: 1`; only `ok` → 0 and the two timeouts → 3 differ), so for a failed run the **`reason`, not the exit code, is the decision key**.

**The chip proves EFFORT; the served slug proves MODEL.** Since the 2026-07 GPT-5.6 redesign the composer chip carries the reasoning-effort tier *only* — the model has no chip signal at all (no aria-label, no dataset key). A chip that read `"Pro"` is therefore **not** evidence the model was right; only the post-send served-slug audit is. The axes are gated separately, which is why a run can pass every pre-send check and still be rejected *after* completing.

The **`sent?`** column is the resubmit-safety key: **pre-send** = the failure happened before the prompt went in, no quota burned, a fresh run is safe. **post-send / ambiguous** = quota may be spent and a live run may exist — **never auto-resubmit** (it double-submits); surface to the user.

| reason | exit | sent? | meaning | what to do |
|---|---|---|---|---|
| `needs_reauth` | 1 | pre-send | session cookie missing or expired | user runs `gpt-pro-relay login` on macmini, then resubmit |
| `model_select_failed` | 1 | pre-send | couldn't get Pro selected in the picker | selectors drifted; surface `run_dir` to the user |
| `model_drift_before_send` | 1 | pre-send | chip stopped reading `"Pro"` between verify and click — fails closed *before* the send | safe to resubmit (no quota burned); if it repeats, selectors drifted |
| `served_model_mismatch` | 1 | **post-send** | served slug outside `PRO_MODEL_SLUGS` — the wrong model answered (e.g. `gpt-5-5-pro`, not Sol's `gpt-5-6-pro`) | answer is **VOID + quarantined** to `response.rejected.md`. Never return it. Fresh run re-burns quota → **ask the user** |
| `model_menu_mismatch` | 1 | **post-send** | slug absent and the chip-menu read confirms a non-Sol model | same as above — void, quarantined, ask the user |
| `conversation_drift` | 1 | **post-send** | the tab moved to a *different* `/c/<id>`; extracting would return another conversation's answer | void — never salvage. Ask the user before a fresh run |
| `browser_disconnected_after_send` | 1 | **post-send** | Chrome dropped after the send — the run may still be live | **never auto-resubmit**; check `worker.stderr`/reattach first |
| `send_outcome_unknown` | 1 | **ambiguous** | the send click raised with no conversation captured — may or may not have sent | **never resend blind**; surface to the user |
| `page_closed_before_conversation_url` | 1 | **ambiguous** | tab closed before the conversation URL was captured | same — never resend blind |
| `page_recovery_exhausted` | 1 | **post-send** | tab kept closing; recovery attempts exhausted | terminal; surface `run_dir` |
| `worker_exception` | 1 | depends | Python exception in the worker | inspect `run_dir/worker.stderr` (structured stage trace) — the last `stage` before the error tells you where it died, and whether `sent` had fired |
| *(none — `status: "timeout"`)* | 3 | post-send | no completion within the engine's 60-min cap. Arrives as a **status, not a reason** (the dict carries no `reason` key) | terminal — inspect `run_dir/streaming-*.png`. `response.md` holds a **partial** body: audit-passed but incomplete, still not an answer |
| `deadline_during_recovery` | 3 | post-send | generation budget ran out while recovering a closed tab | terminal — same |
| `empty_prompt` / `prompt_too_large` | 2 | pre-send | empty stdin, or >5 MB | fix the call; no quota burned |
| `run_id_conflict` | 2 | pre-send | reattach id collided with a *different* prompt | pick a fresh run (drop `--run-id`) |
| `run_id_conflict_no_sha` | 2 | pre-send | run_dir exists but `meta.json` lacks a prompt hash (a prior `ask` was killed mid-write) | delete the run_dir and retry, or use a fresh `--run-id` |
| `not_found` | 4 | — | reattached to a run that never landed | the submit never reached macmini — start a **fresh** run |
| `wait_timeout` / `fetch_timeout` | 124 | — | `--max-wait` elapsed, **worker still alive** (`status: pending`, not an error) | reattach: `gpt-pro --run-id <id>` |

`model_audit` also appears in a **successful** result — these are the fail-**open** verdicts, not errors: `verified` (slug present and allowlisted — the normal case), `model_ok_slug_missing` (slug absent but the menu confirms Sol; model confirmed, effort unverified), `unverified_missing_slug` (slug absent *and* menu unreadable — a double selector break degrades rather than bricking the tool). The two FATAL verdicts (`slug_mismatch`, `menu_mismatch`) never reach a `status: ok`; they surface as the two mismatch reasons above.

Reasons you may see in `worker.stderr`'s stage trace but **never** as a caller-visible failure — they are internal log lines or other subcommands, don't treat them as your decision key: `chip_menu_open_failed`, `chip_menuitem_missing`, `closed_during_nav`, `browser_pid_not_found`, `shell_missing` (an internal tab-recovery verdict), `missing_prompt` (the detached `_run` worker), `run_already_claimed` (a duplicate `_run` losing the run's claim to the worker that owns it — it exits touching nothing, and the owner's `result.json` is what your poll returns), `workers_in_flight` (`close-chrome`).

## Run artifacts

`run_dir` lives on macmini at `~/.gpt-pro/runs/<run_id>/`:

- `prompt.md`, `meta.json`, `result.json`
- **the answer body — under exactly one name, and the name is the verdict.** `response.md` **only** when `result.json` says `status: "ok"`; otherwise `response.rejected.md` (a model-audit reject), `response.partial.md` (timed out — never passed the completion gate), or `response.pending.md` (the run died before any verdict, so the body was never adjudicated at all). A failure before extraction publishes none of them. Only `response.md` is ever an answer; the other three are diagnostics with a complete, fluent, on-topic body — that is precisely why they are not named `response.md`.
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
