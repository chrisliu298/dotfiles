# Optional `/goal` guardrail (Claude Code + Codex)

A session-scoped backstop the **user** pastes to keep the session working until the goal is verified
done. `/goal` exists on **both Claude Code and Codex** (it originated in Codex; Claude Code added a
compatible command) — but they are **different mechanisms**, so this file documents each, with emit
templates, per-shape derivation, and caveats. **Grok has no `/goal`** (its closest analog is plan
mode) — there, just run goal-drive. goal-elicit emits the block as advisory text in Phase 5; it
never runs `/goal` itself.

- **Claude Code `/goal`** = a *guardrail over goal-drive*: a Stop hook that watches the transcript
  for goal-drive's completion/stop markers and keeps the session alive until one appears.
- **Codex `/goal`** = a *native autonomous executor*: you give it an objective that points at the
  artifact file and Codex drives it to done itself (goal-drive optional, as verification discipline).

## Claude Code `/goal` — a Stop-hook guardrail (the constraints that shape the condition)

`/goal <condition>` wraps a session-scoped, prompt-based **Stop hook**. After each turn, the
condition + the conversation transcript are sent to a small fast model (a fast model such as Haiku
by default) that returns yes/no. If "no", the session gets the reason and keeps working; the hook
auto-clears once the condition holds. Hard facts that dictate the design:

- **The evaluator has no file or tool access.** It judges ONLY text already in the transcript. So
  "all `done_when` in GOAL.md verified" is useless — Haiku can't open the file. The condition must
  reference strings goal-drive **prints into the transcript**.
- **`/goal` is strictly user-typed.** No skill/hook/SDK can set it — hence goal-elicit emits a
  copy-paste block, it does not invoke `/goal`.
- Condition ≤ **4000 chars**. One goal per session (a new one replaces the old). Resume
  (`--resume`/`--continue`) resets the turn count.
- Requires Claude Code **v2.1.139+**. Silently unavailable under `disableAllHooks`,
  `allowManagedHooksOnly`, or an untrusted workspace. (Codex has its **own** `/goal` — a different
  mechanism, see below; Grok has none.)

## When to emit it

Emit only for an **executable, ready** artifact — by shape (`authority` is **optional** for every
shape; Default authority applies when it's omitted, so its absence does NOT make an artifact
non-executable):

- **Contract** — has an `execution:` block and `status: ready`.
- **Checklist** — required header fields filled and a **non-empty `items`** array (each item with a
  stable `id` + `state`) plus a `done_when`. A checklist carries no `status` field, so "ready" =
  header complete + items present. **Skip if `items: []`** (a script will fill it later) — a 0/0
  condition would false-positive instantly.
- **Phased doc** — a `## Phases` section with `[state:]` markers and `status: ready`.

Never emit for a `draft` or `blocked` artifact. **Recommend** it (bold the block) when
`commit_policy: per_unit` or the work is many-unit / high-autonomy — where premature "done" or
runaway looping costs most. **Skip** it for a Clear-domain one-shot (friction exceeds benefit); on
**Codex** emit the Codex form instead (below), and on **Grok** just run goal-drive.

## The condition template

It anchors on goal-drive's terminal markers — whose **canonical literals live in
`goal-drive/references/execution-loop.md` § Terminal markers** (this template matches their
**prefix** only). It requires real output to accompany the completion marker (defeats narrated
"done"), accepts a by-exception stop as terminal (so the hook never fights a legitimate halt), and
carries a turn-bound TIMEOUT (the universal safety valve).

```
/goal "Drive <ARTIFACT> id <ID> with goal-drive. SATISFIED when the transcript contains a line beginning with 'GOAL-DRIVE COMPLETE: <ID>', with the real verification output for <TOP-LEVEL CHECK(S)> (command + exit/result, or the named file/metric/observed behavior — not a bare claim) appearing earlier in the transcript. ALSO SATISFIED by a line beginning with 'GOAL-DRIVE STOPPED: <ID> —' (a legitimate by-exception halt) — stop and surface it. Do not accept a 'done' narration without that evidence. TIMEOUT: if neither marker appears after <N> turns, stop and report that the guardrail expired without completion/stop evidence — do not claim the goal is done."
```

Fill `<ARTIFACT>`/`<ID>` from frontmatter; `<TOP-LEVEL CHECK(S)>` by shape (below). The per-unit
checks stay in the artifact — the artifact is the single source of truth; the condition inlines
only the small, stable top-level check.

**Constructing the string.** Flatten the whole condition to one line. If an inlined check contains
a double-quote, escape it as `\"` or paraphrase the check without raw quotes; keep shell snippets
in backticks only when they don't break the surrounding `/goal "..."`. Re-count length after
escaping and keep it under 4000 chars. Match the markers by **prefix only** — the
`— <n>/<n> <units> verified` suffix on COMPLETE varies by shape and is not load-bearing.

### Turn-bound heuristic

`<N>` = a generous cap, not a deadline — the markers clear the goal first; `<N>` only bounds a
stuck run, and hitting it produces a TIMEOUT report (not a "done"). A safe default that leaves room
for repair attempts:

    <N> = (done_when count | items count | phase count) × (repair_budget + 1) + 10

(`repair_budget` defaults to 3.) Round up for large artifacts; when unsure, err high — an over-tight
`<N>` just ends the session early with a TIMEOUT report, which is recoverable.

## Per-shape derivation

`<TOP-LEVEL CHECK(S)>` must name what goal-drive **echoes at FINISH** (the goal-completion
predicate), not the per-unit checks it ran earlier — those scroll past before the marker. If a
check names a **file artifact, metric, or observed behavior** rather than a command, describe the
expected observable signal in plain language (e.g. "`coverage/index.html` reports ≥80%") — the
evaluator is a language model and can judge a described signal.

- **Contract (`GOAL.md`)** — the goal-level commands from `## Done when` / `## Verification plan`
  (e.g. `pytest` exits 0, `rg '\bfoo\b' src/` empty). Completion = every `Done when` box `[x]`.
- **Checklist (`.goals/<id>.checklist.json`)** — the goal-level `done_when` string (e.g.
  `npm run lint:docs exits 0`) + the item count ("all N items done"). Do NOT enumerate item IDs —
  the count is the stable signal.
- **Phased doc (`.goals/<id>.plan.md`)** — the frontmatter `done_when` predicate (default
  "all phases `[state: done]`"). The per-phase `**Acceptance:**` outputs are unit-level and appear
  earlier in the transcript, so the condition keys on the final predicate, not each phase command.

### Worked example (contract `20260503-2200-rename-foo`)

```
/goal "Drive GOAL.md id 20260503-2200-rename-foo with goal-drive. SATISFIED when the transcript contains a line beginning with 'GOAL-DRIVE COMPLETE: 20260503-2200-rename-foo', with the real verification output appearing earlier (command + exit/result, not a claim) for: rg '\bfoo\b' src/ returns no matches, and pytest tests/test_auth.py exits 0. ALSO SATISFIED by a line beginning with 'GOAL-DRIVE STOPPED: 20260503-2200-rename-foo —' — stop and surface it. Do not accept a 'done' narration without that output. TIMEOUT: if neither marker appears after 20 turns, stop and report the guardrail expired — do not claim done."
```

## Codex `/goal` — a native executor (point it at the file)

Codex's `/goal` (Codex CLI 0.128.0+) is **not** a transcript guardrail — it is the autonomous loop
itself: `/goal <objective>` makes Codex plan → act → test → review → iterate until a verifiable end
state. So the Codex form does **not** reference goal-drive's terminal markers; it states the outcome
and points at the artifact file. This is what makes the Claude→Codex handoff clean: goal-elicit
writes the artifact to an agent-neutral path, and Codex's `/goal` points right at it.

- **Enable / auth.** If `/goal` isn't in the slash menu, enable it — `codex features enable goals`
  (or `features.goals = true` in `config.toml`). Availability can also depend on your Codex version
  and account/auth mode; check Codex's own docs if it stays missing.
- **Objective ≤ 4000 chars; point at a file.** The docs say to put long instructions in a file and
  point the goal at it — exactly the goal-elicit artifact. Keep it a file (`.goals/<id>.*` or
  `GOAL.md`) and reference the path; do **not** paste a large GOAL.md inline (it can exceed the cap).
- **goal-drive is optional here.** Codex's `/goal` drives on its own; name goal-drive in the
  objective only if you want its verification discipline (per-unit acceptance, no verification
  theater) layered on top.
- **Lifecycle:** `/goal` to view · `/goal pause` · `/goal resume` · `/goal clear` (mirrors Claude's controls).

Codex emit template — fill `<PATH>`/`<ID>` from frontmatter and `<TOP-LEVEL CHECK(S)>` by shape (same
derivation as the Claude section):

```
/goal Drive the goal defined in <PATH> (id <ID>) to done. Implement it, then verify <TOP-LEVEL CHECK(S)> with the listed command/evidence — never weaken a check. Stop when every "done when" item passes, or pause and ask me if you hit a blocker that needs my input.
```

## Emit format (Phase 5)

Append to the "artifact written at `<path>`" handoff — emit the form(s) for where the user will run it:

```markdown
**Optional `/goal` guardrail.**

- **Claude Code (v2.1.139+)** — paste BEFORE running goal-drive, to keep the session working until
  the goal is verified done:

      /goal "...filled marker-keyed condition..."

- **Codex (`features.goals` enabled, ChatGPT auth)** — paste to drive the artifact natively:

      /goal Drive the goal in <path> (id <id>) to done; verify <top-level check(s)>, never weaken a check, stop when all pass or on a blocker.

On Grok (no `/goal`) just run goal-drive — its by-exception stops are enough.
```

Also state the **staleness and availability caveats** (below) in that handoff, so the user knows
when to refresh the condition and when the guardrail is silently inert.

## Caveats (state these to the user)

- **Stale condition.** The condition is anchored on the markers, not on `done_when` text, so
  editing the artifact body does not break it. Changing the **`id`** does → `/goal clear`, then
  re-paste a condition built from the new `id`.
- **One goal per session / resume.** Pasting replaces any active goal. After `--resume`, the turn
  count resets — re-paste if needed.
- **Over-tight condition.** The turn bound and the `GOAL-DRIVE STOPPED` escape both let the session
  end; `/goal clear` is the manual out.
- **False positives are probabilistic, not proof.** The marker + "preceded by real output" rule
  narrow them, but a tool-less evaluator can still be fooled by fabricated-looking text.
  goal-drive's own no-verification-theater rule is the real backstop — `/goal` is a seatbelt, not
  the brakes.
- **Availability (Claude Code).** Silently inert under `disableAllHooks` / `allowManagedHooksOnly` /
  untrusted workspace, or below v2.1.139. The pipeline runs fine without it; the guardrail is purely
  additive.
- **Availability (Codex).** `/goal` may need enabling (`codex features enable goals` /
  `features.goals`) and can depend on your Codex version and account/auth — if it's absent, check
  Codex's docs. The 4000-char cap applies to the objective — point at the artifact file rather than
  inlining a large one. For a cross-machine handoff, the file must exist in Codex's checkout
  (committed/synced), since the objective only references its path.
