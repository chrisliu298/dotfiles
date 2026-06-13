# Universal-skill authoring (Claude · Codex · Grok)

How to write a `SKILL.md` that is shared across all three agents (marked C/X/G in the
[skill matrix](../README.md)) so one file works — or degrades cleanly — on each. Read this
before editing a skill wired to more than `claude`. Claude-only skills (relay, prism,
keep-warm, goal-loop) are exempt.

## The one idea

The three harnesses **already converged on the Agent Skills `SKILL.md` format** (`name` +
`description` + markdown body) — that intersection is the portable contract. Slash-commands,
`$ARGUMENTS`, the `Skill` tool, `AskUserQuestion`, and schedulers are *harness extensions*
layered on top. A universal skill leans on the portable core and treats every extension as an
optional accelerator with a plain-text fallback.

What each harness actually does (verified 2026-06):

| Construct | Claude Code | Codex CLI | Grok Build |
|-----------|-------------|-----------|------------|
| `SKILL.md` + `description`-trigger | ✓ | ✓ | ✓ (reads `.claude/skills` + AGENTS.md) |
| `/<skill-name>` slash | ✓ | ✗ (no auto per-name; `/skills` picker / implicit) | ✓ |
| `$ARGUMENTS` / `$1` interpolation | interpolated **pre-model** | ✗ (skills; only deprecated custom-prompts had it) | ✗ |
| `Skill(...)`, `AskUserQuestion`, `Cron*` | ✓ | ✗ | ✗ |
| `allowed-tools`/`user-invocable`/`effort` frontmatter | enforced | ignored | ignored |

Why `$ARGUMENTS` is the sharp trap: it's substituted by the harness *before the model sees the
body*. On a harness that doesn't interpolate, the literal string `$ARGUMENTS` reaches the model
as dead text and the parameter is silently lost. `prism` is the model to copy — it parses
`prism 2 xh gp` from the natural-language tail, not from a placeholder.

## Five rules

1. **Args from prose, never interpolation.** No `$ARGUMENTS` / `$1` / `$NAME` in the body.
   Document an **input contract** instead and let the model read args from the message:
   - ✗ `Deploy $1 to $2.`
   - ✓ *"The user's message carries `<target>` and `<mode>` (default `standard`). If absent, ask once."*

2. **Capability-conditional, never runtime-conditional.** Test for the *capability*, never the
   harness name. This is drift-proof — a future Grok tool benefits every skill with zero edits.
   - ✗ `If on Claude, use AskUserQuestion; on Codex/Grok, …`
   - ✓ *"If your harness has a structured-question tool (Claude Code's `AskUserQuestion`), use it; otherwise present numbered options inline and accept a number/letter reply."*

3. **Outcome-first, widget-optional.** Write the plain-text behavior as the *primary* text; the
   rich harness control is an optimization that must yield the **same decision surface / state
   transition**. The fallback is the contract, not the afterthought.

4. **No bare harness-tool imperatives.** Never instruct "invoke `Skill(x,…)`" or "use the
   `AskUserQuestion` tool" as the *only* path. Either pair it with a plain-text fallback (rule 2)
   or — if there is no equivalent — **scope the skill** (rule 5). For skill-to-skill handoff,
   describe intent ("hand off to the `goal-drive` skill"), don't name a tool API.

5. **Scope when degradation would change the outcome.** Litmus: *remove the harness feature —
   does the skill still do what its `description` promises?* **Yes → degrade. No → scope** it
   to `claude` in the `SKILLS` table in `dotfiles.sh`. Capabilities with no plain-text
   equivalent are scope-only: cross-model dispatch (relay/prism), scheduling/persistence
   (`Cron*`, `ScheduleWakeup`, `/loop`), programmatic `Skill()` composition, hook enforcement.

Plus two hygiene rules:

6. **Invocation is a one-line gloss, never the contract.** Rely on the `description` trigger (the
   only universal invocation path). If you mention a slash command, keep it to one line and don't
   hard-reference another command's *behavior* (`/goal launches the guardrail`) — Codex has no
   auto per-name slash, so prose like "run `/deslop`" invokes nothing there.
7. **No hardcoded `~/.claude/` (or `~/.codex/`, `~/.grok/`) skill paths in the body.** They point
   at the wrong directory on the other harnesses. Reference scripts relative to the skill dir
   ("the `gpt-pro` script beside this `SKILL.md`"). Frontmatter (`allowed-tools`) may keep
   absolute paths — it's Claude-only and ignored elsewhere.

## What's already right (copy these)

- `goal-elicit` — "never detects its runtime"; `AskUserQuestion` → numbered plain-text
  degradation; one `/goal` handoff message with the plain-text body as the artifact.
- `goal-drive` — core loop uses only universal tools (Read/Write/Edit/Bash/Grep/Glob).
- `prism` — parses its config from the natural-language tail, no `$ARGUMENTS`.

## Mechanical gate

`./dotfiles.sh` (and `./dotfiles.sh lint` on demand) warns when a universal skill **body**
contains `$ARGUMENTS` or a `~/.{claude,codex,grok}/skills/` path. It is intentionally
conservative — it does **not** catch un-degraded `AskUserQuestion`/`Skill()`/`Cron*` (those have
legitimate degradation uses and need human review against rule 4). The warning is non-fatal:
it surfaces the issue without breaking setup.

## Frontmatter is safe

`allowed-tools`, `user-invocable`, `effort`, `model` are Claude-only keys that Codex and Grok
ignore. Use them freely — they are the no-cost portability layer. The rule is only that the
**body must not rely on** a tool listed there being present at runtime.
