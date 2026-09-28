# Runtime, recovery, and diagnostics

## Background and timeout

The engine runs on this Mac by default, where `gpt-pro` blocks on it directly; with `GPT_PRO_HOST` set to an SSH host (e.g. `macmini`) it instead runs its own short-session poll loop. Either way `--max-wait` (default 120 min) bounds how long the wrapper waits. The default is deliberately generous — a queued or long Pro run killed by a tight timeout wastes the tokens it already spent, so favor completion. For a Bash tool supporting background and timeout fields, wrap the invocation in:

- `run_in_background: true`
- `timeout: 7260000` — Bash-tool timeout in **milliseconds** = **121 min**, 60 s of slack over the default `--max-wait 7200` (= 120 min) so the tool doesn't preempt the wrapper's final diagnostic. If you change `--max-wait`, set this to at least `(--max-wait + 60) × 1000`.

For other harnesses, use the supported background/session equivalent described in [SKILL.md](../SKILL.md#invoke-and-wait), preserving the same wrapper deadline and timeout slack.

Two clocks, inner → outer: the wrapper's **`--max-wait`** (default 120 min, both paths) → the Bash-tool **`timeout`** (121 min). The engine itself has **no** per-run generation cap — a long Pro turn runs until it finishes or is stopped. When `--max-wait` elapses the wrapper exits 124 but the detached worker keeps running; reattach with `--run-id` rather than resubmitting.

Wait for the completion notification. Do NOT poll from the agent side — the wrapper is already polling (see the waiting guidance in [SKILL.md](../SKILL.md#invoke-and-wait)).

## Recovery

`gpt-pro` prints `run_id=<id>` and a ready-to-run `recover_with=gpt-pro --run-id <id>` line to stderr at the start — both land in the background task's output file. Capture the **literal** id from there; a `$RUN_ID` shell variable does **not** survive into a later Bash-tool call. If the caller dies, or the wrapper exits 124 (timed out, still pending) or 255 (SSH transport unknown), the engine's worker keeps running. Reattach with the same id, inside the same envelope (`run_in_background: true`, `timeout: 7260000`) — this is recovery, not the forbidden polling:

```bash
gpt-pro --run-id ask-20260611T002710Z-…    # the literal id, not "$RUN_ID"
```

This skips submit and waits for the existing run to complete (blocking fetch locally, poll loop over SSH). If the run already finished but you lost the output, read it from the run_dir directly — but **read `result.json` FIRST: only `status: "ok"` makes `response.md` usable.** With the default local engine:

```bash
jq -r '.status, .reason, .model_audit' ~/.gpt-pro/runs/<run_id>/result.json   # gate — must print ok
cat ~/.gpt-pro/runs/<run_id>/response.md                                      # ONLY when status == ok
```

**On `status: "error"` any extracted body is QUARANTINED — diagnostic only, never an answer.** A rejected turn can be complete, fluent, and on-topic, so "the text looks fine" is not a reason to use it. Model-audit failures publish `response.rejected.md`; an attachment acknowledgement instead of completed work publishes `response.incomplete.md`; a failure before adjudication may leave `response.pending.md`. None is `response.md`, and all are void. Recovery is a fresh run (new quota → the user decides) or an honest failure report — never a `cat`.

## Stopping a run

To interrupt a run you launched — you changed your mind, or a better answer arrived elsewhere — use `--stop` with the literal run-id (same envelope isn't needed; stop is quick and bounded):

```bash
gpt-pro --stop ask-20260611T002710Z-…    # the literal id, not "$RUN_ID"
```

It's **graceful and worker-driven**: the command writes a stop signal into the run_dir and the owning worker consumes it at its next phase gate. If the prompt **hasn't been sent yet**, the run is **dequeued** (no Pro quota spent). If it **was already sent**, the worker **clicks ChatGPT's Stop button** on the live turn to halt generation. Either way the run finalizes `status: stopped` and **no response is returned** (the partial is discarded, not published). All output is JSONL on stderr.

- **`stopped` / `already_finished` / `pending` → exit 0.** `pending` means the worker is alive and will consume the stop; poll `fetch` to confirm.
- **`no_live_worker` → exit 2.** No live worker consumed the signal (the worker process itself died, rare — workers survive SSH drops). Server-side generation may still be running; use the manual teardown path if you must halt it: `gpt-pro-relay close-chrome --account all --force` is a blunt last resort (kills all tabs).
- **`not_found` → exit 4.** Unknown run-id.

Stop is **not** resubmit-safe cover for a mistake: a dequeued run spent no quota, but a run stopped after send already burned its reasoning up to the interrupt. Don't stop-then-resubmit reflexively.

## Concurrency

New runs rotate across the four ChatGPT accounts (1 → 2 → 3 → 4, persisted in `~/.gpt-pro/account-router.json`; the run's `account` is in `meta.json`). Each account has its own Chrome process and profile, and up to `GPT_PRO_MAX_PARALLEL` (default **6**, clamped to a ceiling of **10**) runs **per account** share it, each in its own tab. Beyond the cap, that account's additional workers queue on its file-lock semaphore (`~/.gpt-pro/slots/` for account 1, `~/.gpt-pro/account-<N>/slots/` for the others) and wait for a slot to free up (the worker logs `slot_queued`, then `slot_acquired` when it gets in). A queued run can wait **15+ min before it even reaches `sent`** (961 s observed), so total wall-clock = **queue wait + the run itself (5–20 min, up to 1–2 hours)** — don't set `--max-wait` (or the Bash-tool timeout) shorter than that.

**A backgrounded call with no exit code is not a failed call.** Empty output + no completion notification = **still running**. Never diagnose it as lost, and never fresh-submit over it — that double-submits a live run and double-burns quota. Confirm liveness from the stage trace before concluding anything:

```bash
tail -5 ~/.gpt-pro/runs/<run_id>/worker.stderr
```

`slot_queued` with no `slot_acquired` = queued, waiting its turn. `sent` with no `finished` = generating. Either way: **wait.**

Each account's Chrome closes itself when its last run (or `login`/`doctor`) exits, and the next run on that account relaunches it automatically with the saved profile — an invoking agent never needs to manage it. `gpt-pro-relay close-chrome [--account N|all]` is **operator maintenance only** (it refuses by default if any worker is in flight; `--force` kills anyway) — don't run it as part of normal use or recovery. Raising `GPT_PRO_MAX_PARALLEL` above the default is a knob, not a free upgrade: parallel bursts on one ChatGPT Pro session are an account-side anti-abuse signal. If `network.json` starts showing 429s, captcha redirects, or unexplained `needs_reauth` after parallel use, drop it back to `1`.

## If it fails

The wrapper's **exit code** is the agent's decision key — every code maps to one action. Empty prompts, oversized prompts (>5 MB), and malformed run-ids are caught *before* any submission (exit 2 — no quota burned).

| exit | meaning | do next |
|---|---|---|
| 0 | response on stdout (non-empty) | use it |
| 1 | engine error, or rc 0 with an empty body (extraction failure) | read the `reason` in stderr → reason table below; if none, inspect `run_dir`. Do **not** blindly resubmit (would re-burn quota) |
| 2 | usage error (empty/oversized prompt, bad run-id, bad flag) — no quota burned | fix the call from the stderr message; do **not** reattach |
| 3 | `status: "timeout"` — only from a worker started before the engine's generation cap was removed; current workers never time out | terminal — don't reattach (a re-fetch just re-times-out); inspect `streaming-*.png`, surface to the user |
| 4 | run_dir not found (reattach to a run that never landed) | the submit never reached the engine — start a **fresh** run (drop `--run-id`) |
| 124 | `--max-wait` elapsed, run still pending | reattach: `gpt-pro --run-id <id>` (same envelope) |
| 255 | SSH transport state unknown | reattach **first**: `gpt-pro --run-id <id>`; only if *that* exits 4 did the submit never land — then resubmit. Never start a fresh run before reattaching (risks a duplicate, double-quota run) |

On a non-zero exit the engine's terminal stderr JSON carries a `reason`. **Exit 1 is the catch-all — every engine error returns it** (`err()` hardcodes `exit_code: 1`; only `ok` → 0, legacy timeouts → 3, and `stopped` → 5 differ), so for a failed run the **`reason`, not the exit code, is the decision key**.

**The chip proves EFFORT; the served slug proves MODEL.** Since the 2026-07 GPT-5.6 redesign the composer chip carries the reasoning-effort tier *only* — the model has no chip signal at all (no aria-label, no dataset key). A chip that read `"Pro"` is therefore **not** evidence the model was right; only the post-send served-slug audit is. The axes are gated separately, which is why a run can pass every pre-send check and still be rejected *after* completing.

The **`sent?`** column is the resubmit-safety key: **pre-send** = the failure happened before the prompt went in, no quota burned, a fresh run is safe. **post-send / ambiguous** = quota may be spent and a live run may exist — **never auto-resubmit** (it double-submits); surface to the user.

| reason | exit | sent? | meaning | what to do |
|---|---|---|---|---|
| `needs_reauth` | 1 | pre-send | session cookie missing or expired | user runs `gpt-pro-relay login --account <N>` (the run's `account` from `meta.json`) on the engine host, then resubmit |
| `model_select_failed` | 1 | pre-send | couldn't get Pro selected in the picker | selectors drifted; surface `run_dir` to the user |
| `model_drift_before_send` | 1 | pre-send | chip stopped reading `"Pro"` between verify and click — fails closed *before* the send | safe to resubmit (no quota burned); if it repeats, selectors drifted |
| `instruction_boundary_lost_before_send` | 1 | pre-send | a large paste became attachment-only and the relay could not prove a non-empty ordinary execution instruction before Send | no quota burned; surface `run_dir`. Safe to retry after updating/fixing the relay; repeated failures mean composer selectors or behavior drifted |
| `instruction_boundary_lost` | 1 | **post-send** | despite the restored top-level instruction, Pro only acknowledged/read the attached prompt and asked for another instruction or promised to continue later | output is **VOID + quarantined** to `response.incomplete.md`. Never return it. A fresh run re-burns quota → **ask the user** |
| `served_model_mismatch` | 1 | **post-send** | served slug outside `PRO_MODEL_SLUGS` — the wrong model answered (e.g. `gpt-5-5-pro`, not Sol's `gpt-5-6-pro`) | answer is **VOID + quarantined** to `response.rejected.md`. Never return it. Fresh run re-burns quota → **ask the user** |
| `model_menu_mismatch` | 1 | **post-send** | slug absent and the chip-menu read confirms a non-Sol model | same as above — void, quarantined, ask the user |
| `conversation_drift` | 1 | **post-send** | the tab moved to a *different* `/c/<id>`; extracting would return another conversation's answer | void — never salvage. Ask the user before a fresh run |
| `browser_disconnected_after_send` | 1 | **post-send** | Chrome dropped after the send — the run may still be live | **never auto-resubmit**; check `worker.stderr`/reattach first |
| `send_outcome_unknown` | 1 | **ambiguous** | the send click raised with no conversation captured — may or may not have sent | **never resend blind**; surface to the user |
| `page_closed_before_conversation_url` | 1 | **ambiguous** | tab closed before the conversation URL was captured | same — never resend blind |
| `page_recovery_exhausted` | 1 | **post-send** | tab kept closing; recovery attempts exhausted | terminal; surface `run_dir` |
| `worker_exception` | 1 | depends | Python exception in the worker | inspect `run_dir/worker.stderr` (structured stage trace) — the last `stage` before the error tells you where it died, and whether `sent` had fired |
| *(none — `status: "timeout"`)* | 3 | post-send | legacy only: no completion within the generation cap that older workers had. Arrives as a **status, not a reason** (the dict carries no `reason` key) | terminal — inspect `run_dir/streaming-*.png`. `response.partial.md` holds a partial body, never an answer |
| `deadline_during_recovery` | 3 | post-send | legacy only: generation budget ran out while recovering a closed tab (current workers have no budget) | terminal — same |
| `empty_prompt` / `prompt_too_large` | 2 | pre-send | empty stdin, or >5 MB | fix the call; no quota burned |
| `run_id_conflict` | 2 | pre-send | reattach id collided with a *different* prompt | pick a fresh run (drop `--run-id`) |
| `run_id_conflict_no_sha` | 2 | pre-send | run_dir exists but `meta.json` lacks a prompt hash (a prior `ask` was killed mid-write) | delete the run_dir and retry, or use a fresh `--run-id` |
| `not_found` | 4 | — | reattached to a run that never landed | the submit never reached the engine — start a **fresh** run |
| `wait_timeout` / `fetch_timeout` | 124 | — | `--max-wait` elapsed (local or SSH path), **worker still alive** (`status: pending`, not an error) | reattach: `gpt-pro --run-id <id>` |

`model_audit` also appears in a **successful** result — these are the fail-**open** verdicts, not errors: `verified` (slug present and allowlisted — the normal case), `model_ok_slug_missing` (slug absent but the menu confirms Sol; model confirmed, effort unverified), `unverified_missing_slug` (slug absent *and* menu unreadable — a double selector break degrades rather than bricking the tool). The two FATAL verdicts (`slug_mismatch`, `menu_mismatch`) never reach a `status: ok`; they surface as the two mismatch reasons above.

Reasons you may see in `worker.stderr`'s stage trace but **never** as a caller-visible failure — they are internal log lines or other subcommands, don't treat them as your decision key: `chip_menu_open_failed`, `chip_menuitem_missing`, `closed_during_nav`, `browser_pid_not_found`, `shell_missing` (an internal tab-recovery verdict), `missing_prompt` (the detached `_run` worker), `run_already_claimed` (a duplicate `_run` losing the run's claim to the worker that owns it — it exits touching nothing, and the owner's `result.json` is what your poll returns), `workers_in_flight` (`close-chrome`).

## Run artifacts

`run_dir` lives on the engine host (this Mac by default) at `~/.gpt-pro/runs/<run_id>/`:

- `prompt.md`, `meta.json`, `result.json`
- **the answer body — under exactly one name, and the name is the verdict.** `response.md` **only** when `result.json` says `status: "ok"`; otherwise `response.rejected.md` (a model-audit reject), `response.incomplete.md` (the attached task was acknowledged rather than executed), `response.partial.md` (timed out — never passed the completion gate), or `response.pending.md` (the run died before any verdict, so the body was never adjudicated at all). A failure before extraction publishes none of them. Only `response.md` is ever an answer; the other four are diagnostics that may look plausible — that is precisely why they are not named `response.md`.
- `pre-send.png`, `streaming-NNN.png`, `final.png`, `error-*.png`
- `final.html`, `network.json`
- `worker.stdout` — detached worker's stdout (usually empty)
- `worker.stderr` — **structured JSONL stage trace**: one line per stage (`start`, `slot_queued`/`slot_acquired`, `chrome_cdp_ready`/`chrome_connected`/`chrome_activated`, `logged_in`, `model_verified`, `prompt_typed`, `sent`, `extracted`, `finished`, plus `error` / `orphan_kill_*` / `*_skipped`). When something fails mid-run, this is the fastest path to the failure point — the last stage before the `error` line tells you where it died.

Read them directly when diagnosing (prefix `ssh "$GPT_PRO_HOST"` if you relay to a remote engine).
