# The `/goal` execution message (Claude Code + Codex)

The single copy-paste message the **user** pastes to run the artifact to verified done. `/goal`
exists on **both Claude Code and Codex** (it originated in Codex; Claude Code added a compatible
command) — they are **different mechanisms**, but **one transcript-anchored message is portable to
both**, so this file documents each mechanism, the single shared template, per-shape derivation, and
caveats. **Grok has no `/goal`** (its closest analog is plan mode) — there, the user pastes the *same
message without the `/goal` prefix*. goal-elicit emits the one message as advisory text in Phase 5;
it never runs `/goal` itself.

- **Claude Code `/goal`** = *launch + guard in one paste*: setting the goal **starts a turn
  immediately with the condition as the directive** (so a condition that says "drive <ARTIFACT> with
  goal-drive" launches goal-drive itself — you do **not** run it separately), and a Stop hook then
  watches the transcript for goal-drive's completion/stop markers, keeping the session alive until
  one appears. One paste both starts and guards.
- **Codex `/goal`** = a *native autonomous executor*: you give it an objective that points at the
  artifact file and Codex drives it to done itself (goal-drive optional, as verification discipline).

## Claude Code `/goal` — launch + guard in one paste (the constraints that shape the condition)

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
- Requires Claude Code **v2.1.139+**. Unavailable under `disableAllHooks`, `allowManagedHooksOnly`,
  or an untrusted workspace — per the docs the command **tells you why** rather than silently
  no-op'ing. (Codex has its **own** `/goal` — a different mechanism, see below; Grok has none.)

## When to emit it

**Always** emit for an **executable, ready** artifact — by shape (`authority` is **optional** for every
shape; Default authority applies when it's omitted, so its absence does NOT make an artifact
non-executable):

- **Contract** — has an `execution:` block and `status: ready`.
- **Checklist** — required header fields filled and a **non-empty `items`** array (each item with a
  stable `id` + `state`) plus a `done_when`. A checklist carries no `status` field, so "ready" =
  header complete + items present. **Skip if `items: []`** (a script will fill it later) — a 0/0
  condition would false-positive instantly.
- **Phased doc** — a `## Phases` section with `[state:]` markers and `status: ready`.

Emit it **every time** an artifact is executable-ready, including Clear-domain one-shots. **Never**
emit for a `draft` or `blocked` artifact — nothing to execute yet; say what's missing instead.
**Bold/recommend** it when `commit_policy: per_unit` or the work is many-unit / high-autonomy —
where premature "done" or runaway looping costs most. Emit the **one shared message** for both Claude
Code and Codex; on **Grok** (no `/goal`) paste it without the `/goal` prefix.

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

This TIMEOUT is an **evaluator/runaway backstop, not a success criterion** — it lives only in the
`/goal` message, never in the artifact's `objective` or `done_when`. It is *not* the "arbitrary turn
cap baked into the objective" that goal-authoring guidance warns against: the blind transcript
evaluator has no other runaway signal, so keep it — do not move it into the contract, and do not
delete it as a stray cap.

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

## Autonomous review-loop variant (Claude Code + goal-loop `--auto`)

The default message above drives the artifact with **goal-drive** — build-to-done, no review loop. If the
operator wants the **full elicit→drive→review→fix loop run unattended with multi-model review** (e.g.
overnight), and the **goal-loop** skill is available (Claude Code only — it needs prism + the native
`/goal`), emit *this* variant instead. It is a strict superset of the goal-drive handoff: it adds
multi-model review, oracle-gated safe-subset auto-fix, and a pre-classified morning decision queue, and it
keys on goal-loop's `AUTO-*` markers rather than goal-drive's `COMPLETE`/`STOPPED`:

```
/goal "Drive <ARTIFACT> id <ID> through goal-loop --auto; resume each turn with `goal-loop continue <ID>`. SATISFIED when the transcript contains a line beginning 'GOAL-LOOP AUTO-COMPLETE: <ID>', 'GOAL-LOOP AUTO-HANDOFF: <ID>', or 'GOAL-LOOP AUTO-HALTED: <ID> —', with a 'GOAL-LOOP AUTO EVIDENCE-END' line and the real verification output (commands + exit codes, any RED→GREEN oracle ids) appearing earlier in the transcript — not a bare 'done' claim. Do not accept a narrated summary without that evidence block. TIMEOUT: if no such marker appears after <N> turns, stop and report the guardrail expired without a terminal marker — do not claim done."
```

Caveats to state with it: this needs the **goal-loop** skill (Claude Code; degrades off-Claude — see its
`references/loop-protocol.md` § Autonomous mode); it auto-fixes **only** findings whose pre-signed acceptance
oracle is currently RED, so with no oracles authored at sign-off it auto-fixes nothing and just hands back a
decision queue (`.goals/<ID>.auto-report.md`). Use the **plain goal-drive** message (above) when you only
want the artifact built, not reviewed-and-iterated. On **Codex/Grok** there is no goal-loop — emit the
goal-drive message; the autonomous variant is Claude-Code-only.

## Codex `/goal` — a native executor (the one shared message drives it too)

Codex's `/goal` (Codex CLI 0.128.0+) is **not** a transcript guardrail — it is the autonomous loop
itself: `/goal <objective>` makes Codex plan → act → test → review → iterate until a verifiable end
state. Crucially, the **single transcript-anchored message** from "The condition template" above is a
valid Codex objective: it tells Codex to drive the artifact with goal-drive and stop on the
`GOAL-DRIVE COMPLETE` marker + real output, which goal-drive prints identically on Codex. So **emit
that one message for both runtimes — never author a separate Codex string.** Standardize on the
transcript-anchored form because it is the portable superset (required by Claude's blind evaluator,
valid for Codex); a Codex-minimal "verify the file's checks yourself" objective is shorter but is
**not** portable to Claude.

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

**No separate Codex template** — emit the one transcript-anchored message above. (Codex *can* verify the
file's checks itself, but the shared message already drives goal-drive and stops on its verified-complete
marker, so a Codex-only string would only fragment the handoff and break portability to Claude.)

## Emit format (Phase 5)

Append **one** ready-to-paste message to the "artifact written at `<path>`" handoff — the same line
for Claude Code and Codex, never per-runtime variants:

```markdown
**Run it — paste into Claude Code or Codex:**

    /goal "...filled transcript-anchored condition (drive <artifact> with goal-drive; done on GOAL-DRIVE COMPLETE: <id> + the real verification output; stop on GOAL-DRIVE STOPPED; TIMEOUT after N turns)..."
```

*(On Grok, no `/goal`: paste the same text without the `/goal` prefix — same message, not a second
version.)*

Also state the **staleness and availability caveats** (below) in that handoff, so the user knows
when to refresh the condition and when the command is unavailable.

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
- **Availability (Claude Code).** Unavailable under `disableAllHooks` / `allowManagedHooksOnly` /
  untrusted workspace (the command tells you why), or absent below v2.1.139. The pipeline runs fine
  without it — fall back to running goal-drive directly.
- **Availability (Codex).** `/goal` may need enabling (`codex features enable goals` /
  `features.goals`) and can depend on your Codex version and account/auth — if it's absent, check
  Codex's docs. The 4000-char cap applies to the objective — point at the artifact file rather than
  inlining a large one. For a cross-machine handoff, the file must exist in Codex's checkout
  (committed/synced), since the objective only references its path.
