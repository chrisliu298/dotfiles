---
name: crons
description: >-
  Maintain a durable, version-controlled manifest of a project's recurring Claude Code cron jobs
  (the /loop + CronCreate fleet) and re-arm them after they are lost. Claude crons are session-only —
  durable:true is ignored, CronList truncates prompts, and recurring jobs auto-expire after 7 days — so
  the live state is unrecoverable; this skill keeps crons/*.cron as the source of truth, renders CRONS.md,
  and emits the exact CronCreate/CronDelete calls to re-arm. Use on session start, after a compaction,
  reboot, or 7-day expiry to check whether your crons are still armed and restore them; when you run many
  /loop crons in one project; or on "crons", "manage my crons", "re-arm crons", "are my crons still
  running", "cron manifest". It is a preparer, not an actuator: it never calls the Cron* tools and never
  claims a cron is "armed" (no false assurance) — you run CronList and execute the emitted calls. Do NOT
  use for a one-off cron (use CronCreate directly) or a cache heartbeat (use keep-warm).
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, CronCreate, CronList, CronDelete
user-invocable: true
---

# crons

Keep a **durable, version-controlled manifest** of the recurring crons that run a project unattended, and
**re-arm them** whenever the harness loses them. The manifest lives in `crons/*.cron` (one file per job) at
the project root and renders to a human-readable `CRONS.md`. A stdlib-only helper (`scripts/crons`) does the
deterministic parts; **you** run the `Cron*` tools.

## Why this skill exists (verified against the live harness)

Recurring crons created with `CronCreate` are **not durable and not recoverable**:

- **Session-only.** `durable: true` is silently ignored — *nothing* is written to `.claude/scheduled_tasks.json`
  (GitHub #40228). A force-quit, reboot, or `.claude/` wipe loses every cron.
- **`CronList` is lossy.** It **truncates the prompt** and **humanizes the schedule** (`Every day at 4:17 AM`,
  not `17 4 * * *`); job IDs are **ephemeral** (change on every re-arm).
- **7-day auto-expiry.** Every recurring cron fires one last time after 7 days, then is deleted.
- **`CronDelete` can fail to stick** (GitHub #49198): a deleted job may keep firing until the session restarts.

So the live cron state cannot be trusted or rebuilt from the harness. The **only** durable record of a cron's
verbatim prompt and raw schedule is a file on disk — that is what this skill maintains.

## The load-bearing contract: preparer, never actuator — and NO false assurance

The helper **only** parses the manifest, renders `CRONS.md`, gates staleness, and **emits the exact harness
calls to run**. It cannot call `CronCreate`/`CronList`/`CronDelete` (those are Claude-only tools) and therefore
**cannot verify what is actually armed**. *You* are the sole actuator. Consequently the tool **never says a cron
is "armed"** — `check` only asserts the source files and `CRONS.md` agree; `reconcile` reports only
presence-**by-purpose**. A green check over zero armed crons is the exact trap this avoids. (This is the deliberate
inverse of the `docmaint`/`exec-status` freshness model: there the doc is a derived view of reality; here the
manifest *is* the source of truth and the harness is the lossy projection — so do **not** add a freshness/attest gate.)

## The `.cron` format

One file per job, `crons/<NN>-<name>.cron` (the `NN` prefix sets fire order within the hour; stagger schedules
~7 min apart to avoid pile-ups). Metadata lines, then `---`, then the verbatim prompt or command:

```
schedule: 3,33 * * * *
purpose: GPU watchdog
recurring: true
target: claude
---
GPU watchdog (ICR). Run nvidia-smi; if idle GPUs and queued work, enqueue next cell. Honor STOP_ICR. Then stop.
```

- `schedule` — raw 5-field cron (`M H DoM Mon DoW`).
- `purpose` — a short label; it is the **join key** for reconcile, so **make the first line of each prompt distinct**
  (reconcile matches a truncated `CronList` line by prompt-prefix; identical prefixes become ambiguous).
- `recurring` — `true` | `false`.
- `target` — `claude` (default) routes to the `CronCreate` re-arm path. `target: shell` marks a deterministic job
  (e.g. `nvidia-smi`, `df`, `git`) that does not need an LLM; **v1 records it but does not emit an OS timer yet** —
  run those via the OS (systemd/launchd) so they leave Claude entirely (no session loss, no 7-day expiry). The
  OS-timer emitter is the planned fast-follow.

## Verbs (`scripts/crons` — stdlib Python, no venv)

- `crons scaffold [--root D]` — create `crons/` + an example `.cron` if missing.
- `crons render [--root D]` — parse `crons/*.cron` → rewrite `CRONS.md` (pure, idempotent). Run after editing any `.cron`.
- `crons check [--root D]` — fail-closed gate: do the `.cron` files and `CRONS.md` agree? Exit `0` consistent / `1` stale / `2` malformed. Says "source consistent", **never** "armed".
- `crons reconcile [--root D] [--rearm-all]` — the heart. Reads a **`CronList` dump on STDIN**, matches by purpose,
  and emits the exact `CronDelete`/`CronCreate` calls. The literal text **`No scheduled jobs.`** = **cold start** = arm
  all; **empty or unrecognized input is a fail-closed error** (exit `2`), never a silent arm-all. Exit `0` if fully in
  sync, `1` if any drift (missing / extra / duplicate). `--rearm-all` = full resync (delete every *matched* live copy +
  re-create all; true extras are left as-is) — use after you edit prompts/schedules, since the tool cannot detect an edited prompt.
- `crons self-test` — stdlib fixture tests (exit `0`/`1`); no pytest needed.

The helper auto-locates the project root by searching upward for `crons/` or `.git` (or pass `--root`). It works by
hand too — the format is documented above — but the helper is the fast path.

## The recovery protocol (the main use — do this on session start, after a compaction, or after a 7-day expiry)

1. Run **`CronList`** (the tool).
2. Pipe its output to **`crons reconcile`** verbatim (if `CronList` says `No scheduled jobs.`, pipe exactly that —
   it is the cold-start signal; do **not** run `reconcile` with no input, which is a fail-closed error):
   ```
   crons reconcile <<'DUMP'
   <paste the CronList output here, verbatim>
   DUMP
   ```
3. Execute the emitted calls. For each **`▶ ARM`** block, call `CronCreate` with the shown `cron` + `recurring`, and
   set `prompt` to the lines **between `>>> BEGIN PROMPT` and `>>> END PROMPT`, copied EXACTLY** (they are flush-left —
   do not add indentation, do not include the marker lines). Run each **`✖ CronDelete`** line as shown.
4. Re-run **`CronList`** to confirm. If a deleted job keeps appearing (#49198), **restart the session** to clear it.

Cold recovery is ~4 tool calls. Treat the result as "prepared", not "running" — confirm with step 4.

## Editing the fleet

Edit/add/remove a `crons/*.cron` file → `crons render` → `crons check` (gate) → on next reconcile the change is
emitted. To push an **edited** prompt to an already-armed cron, use `crons reconcile --rearm-all` (the tool can't see
the armed prompt, so a plain reconcile would report it merely "present").

## When NOT to use

- A single one-off or short-lived cron → use `CronCreate` directly; a manifest is overkill.
- A cache heartbeat → use **keep-warm**.
- Human status / task / priority docs → those are **exec-status** / **todo** / **mental-seal** (derived-view skills with
  a freshness gate); this is the opposite polarity (source-of-truth manifest, no freshness gate).

## Rules

- **Never imply a cron is armed.** The tool can only confirm presence by purpose; the armed prompt/schedule are
  unverifiable. Report honestly.
- **Keep `purpose` unique and each prompt's first line distinct** — it is the only stable, `CronList`-visible join key.
- **`crons render` after every `.cron` edit**, and treat `crons check` as the gate before relying on `CRONS.md`.
- **Re-arm is yours to run.** The helper emits calls; you execute them, then verify with `CronList`.
