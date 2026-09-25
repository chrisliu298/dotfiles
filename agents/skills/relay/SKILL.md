---
effort: medium
name: relay
description: |
  The ONLY way to call GPT (a.k.a. Codex). Use whenever the user wants to ask,
  delegate to, or get a second opinion from GPT. Do NOT run the codex CLI
  directly — from the main agent or a subagent; always use this skill's relay
  call command. Triggers on "ask/have/send to/get/delegate to gpt/codex",
  "second opinion", "relay".
allowed-tools: Read, Write, Bash(relay:*), Bash(find:*), Bash(printf:*)
user-invocable: true
---

# Relay

**Claude-only.** Claude is the sole caller; a dispatched peer must never call relay back (the script refuses nested calls via `RELAY_PEER`).

Call GPT like a function: one command generates the request, invokes the peer, and prints the response.

> **The peer is a full agent — not a stateless API call.** Relay invokes GPT through its registered transport (`codex exec`), so the peer has core agent tools — shell, file read/write, search, multi-step agentic loops, and web fetch/search (verified 2026-06-06). It can see this repo, run commands, and verify its own work; delegate file I/O and shell work directly. Do **not** treat it as a one-shot completion that "can't see the codebase." The only constant difference from you is the model behind the harness.

```
relay call --name <slug> [--to <peer>] [--effort <level>] [--body-only] <<'BODY'
task
BODY
```

`relay` is in PATH. The caller is always Claude (this is a Claude-only skill); the peer is GPT (the only registered peer), so `--to` is never needed.

If a bare `relay` ever returns "command not found" (a sandboxed/non-zsh/reset-env shell that didn't inherit the PATH entry), re-run the **identical** command with the absolute install path — `~/.claude/skills/relay/scripts/relay call …`. That is the whole recovery; do not reconstruct the call by hand.

**All GPT interactions go through `relay call`.** Do not invoke `codex exec` directly, do not spawn agents to run the codex CLI for this purpose, and do not pass model flags (`-m`, `--model`) — the model and invocation method come from the peer registry (`peers.json`), not the call.

## Peer selection

| Peer | When to pick | How to invoke |
|---|---|---|
| **GPT** (default) | Code review, security review, refactoring, agentic coding. OpenAI lineage. Five exposed API effort tiers (`low` through `max`) plus Codex `ultra` orchestration. | `relay call --name ...` (no `--to` needed) |

Pick GPT for code review, security review, refactoring, agentic coding, or a second opinion from outside the Anthropic lineage, and as the `/prism` Parallax peer.

### Peer registry

Every model-family fact — transport (`codex` CLI), model id, effort knob, and launcher template style — lives once in `peers.json` next to the script. `relay` and `prism-launch` both read it, so **adding a peer that reuses an existing transport is one stanza** there, not edits across the script, the prism launcher, and the docs. Two of the per-peer keys are **prism-consumed, not relay-consumed**: `order` (the standard-tier dispatch/display position) and `lineage` (the synthesis-weighting group — each peer is its own lineage). `relay` ignores them, but `prism-launch` derives its tier order, `peershape` display, and digest lineage from them, so keep them on each standard-tier stanza (a peer with no `order` is simply not a Prism standard tier). One deliberate exception stays in code, not data: a brand-new *transport* needs its own script branch.

### Common Mistakes
- **Premature failure diagnosis**: If a relay call was launched with `run_in_background: true`, do not inspect `.relay` files or enter the failure flow until the background task's completion notification arrives. No notification means the peer is still running.
- **Wrapping relay in a subagent**: Do not spawn an Agent that then calls `relay` inside. When the subagent completes, the platform kills its child processes — including the still-running peer CLI. Call `relay` directly from the main conversation with `run_in_background: true` instead.
- **Empty heredoc body**: The `<<'BODY'` ... `BODY` block must contain text — an empty body causes an immediate error.
- **Missing `--name`**: Every call requires `--name` — omitting it is a script error, not a peer failure.

## Example

```bash
relay call --name auth-review --effort medium <<'BODY'
Review src/auth.py for security issues. Run pytest to verify.
BODY
```

## Effort Levels

`--effort` applies to GPT only. The GPT API supports `none`/`low`/`medium`/`high`/`xhigh`/`max`; relay exposes `low` through `max`, plus Codex-specific `ultra` orchestration. Relay defaults GPT to `medium`. `ultra` is not an OpenAI API `reasoning.effort` value: relay passes it through and Codex interprets it as maximum reasoning plus automatic task delegation. Level names follow OpenAI's own scale ([reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)), which guarantees no fixed token progression across levels.

| Level | When to use |
|-------|-------------|
| `low` | GPT. Quick, cheap turnarounds — simple lookups, small mechanical edits, sanity checks where deep reasoning isn't worth the latency. |
| `medium` | **Default for GPT.** Balanced starting point for code review, tests, bug fixes, and most refactoring. |
| `high` | GPT — the deeper reasoning tier. Use for hard analysis where the extra latency is worth it. |
| `xhigh` | GPT only. Hard architecture work, deep security review, or eval-bound tasks worth the extra latency. **Prism pins the GPT parallax tier here** (the last validated review-quality tier). |
| `max` | GPT only. Maximum reasoning depth for the hardest problems — more exploration and verification than `xhigh`. |
| `ultra` | GPT through relay/Codex only; not an API reasoning-effort value. Max reasoning **plus automatic task delegation** (spawns subagents inside the `codex exec` run) — the slowest tier; reach for it only when the task genuinely benefits from decomposition. |

Before raising effort, improve the prompt first — add outcome-first success criteria, stop rules, verification steps, and completeness criteria.

## Prompting GPT

**Before composing the prompt body, read `references/gpt.md`** (beside this `SKILL.md`) for cross-cutting GPT prompt patterns. This is not optional — the guide contains model-specific patterns that materially affect output quality.

Lead with the outcome, not the procedure. GPT-5.6 responds best to outcome-first prompts — state the goal, success criteria, and stop rules, then let GPT pick the path. Use XML scaffolding only when a specific failure mode needs it:

- `<output_contract>` — when format precision matters
- `<completeness_contract>` — when the task has discrete items that must all be covered
- `<verification_loop>` — when post-change validation is required

**Example:**

```bash
relay call --name pool-refactor --effort medium <<'BODY'
Add connection timeouts and stale-connection recovery to src/db/pool.py.

Success criteria:
- ConnectionPool accepts a timeout_seconds parameter at construction
- stale connections are auto-reconnected on use
- a reclaim_stale() method exists for explicit cleanup
- existing callers keep working without changes

<verification_loop>
Run pytest tests/test_pool.py — all tests must pass. No new lint errors.
</verification_loop>

<output_contract>
Summary of changes, one per line, with file path and description.
</output_contract>
BODY
```

## Calibration handoff

For **judgment tasks** — analysis, review, design, research, second opinions — ask the peer to end its answer with a reasons-based calibration block, then act on it when the response returns. **Skip it for mechanical or code-changing calls** (run-a-command, apply-a-defined-change): there the trust signal is tests, diffs, and the `verify:` frontmatter, not a self-report. Don't ask for a number — verbalized confidence from these models is poorly calibrated (clusters at round numbers, skews overconfident), so a `%` or `High/Med/Low` manufactures false precision the orchestrator can't discount.

Add to the prompt body, inside `<output_contract>`:

```text
End with a ## Calibration block:
- Key assumptions: 1-3 the answer rests on ("none material" only if true)
- Most likely wrong because: the strongest failure mode, missing info, or counterargument
- Would change my conclusion: the specific fact, test, or counterexample that would flip it
- Verify before acting: specific current/high-stakes claims to check ("none" for pure reasoning)

No numeric %, probability, or High/Medium/Low label — this block is for routing and verification, not a calibrated probability.
```

**On return, use it — otherwise it is decoration.** Verify the listed claims before passing the answer up; re-query with corrected context if a Key assumption conflicts with what you know; seek a tie-breaker (`/prism`) if "Most likely wrong because" attacks the core conclusion. Ignore any self-confidence score a peer volunteers anyway — the assumptions and failure mode are the signal, not a self-graded number.

## Output

The script prints the response file content to stdout. The response has YAML frontmatter followed by free-form markdown:

- **Frontmatter**: `relay`, `re`, `from`, `to`, `status` (`done` | `error`), `verify` (`pass` | `fail` | `skip`)
- **Body**: findings, changes, reasoning — free-form markdown below the frontmatter fence

Use `--body-only` to strip the frontmatter and get just the markdown body.

Request and response files are saved in `.relay/` (auto-gitignored). Peer stderr is logged to a `.log` sidecar file alongside the request. **Never read the `.log` file** — it contains the peer's full stderr output, which is extremely long and token-heavy. Only inspect the `.res.md` response file.

### When a relay call fails

**You must diagnose and retry — do not report failure to the user without attempting a fix first.**

**Background-task guard:** If the relay call was launched with `run_in_background: true`, this diagnosis flow applies only after the background task's completion notification has arrived. Relay calls take significantly longer than subagents — this is normal, not a failure. Until the completion notification arrives, the call is in progress and healthy. Do not read logs or check for the response file.

When a completed relay call reports a missing response file, the peer failed before producing output. Each call generates a new request ID, so retrying does not re-execute previous attempts.

1. **Check the Bash output.** The relay script prints diagnostic information (exit code, error summary) to stdout/stderr. Use this — visible in the Bash tool result — to identify the cause. **Do not read the `.log` sidecar file** — full stderr, token-heavy.
2. **Diagnose.** Common causes and fixes:
   - *Peer binary not found* → verify the peer CLI is installed and in PATH
   - *Empty body / malformed heredoc* → verify the heredoc has content and a matching terminator
   - *Peer exited non-zero but response file exists* → not a failure; read the response file
3. **Fix and retry once.** Correct the invocation based on the diagnosis and re-run the relay call.
4. **If the retry also fails**, report the failure to the user with the diagnosed cause from the Bash output.

The first failure is information, not a stop signal.

## Async / Parallel

When you have independent subagent work alongside a relay call, **never block on relay while subagents wait (or vice versa)**. Run everything concurrently:

**Background the Bash call**: Use `run_in_background: true` on the Bash tool so the relay call runs concurrently with your subagents. The platform sends a completion notification when the background task finishes — do not poll, do not inspect `.relay` files, and do not enter the failure diagnosis flow before that notification arrives.

**Give it a generous timeout.** Relay peers are full agents and can run long (GPT at `xhigh`/`max`/`ultra` routinely takes many minutes). A Bash-tool `timeout` that fires mid-run kills the peer and wastes every token it already spent — favor completion over a tight bound. Set `timeout: 3600000` (60 min) on the backgrounded Bash call; relay has no internal per-call cap, so this outer timeout is the only bound.

**Rule: Launch relay calls and subagents concurrently. Never serialize independent work.**

**Never wrap relay in a subagent.** If an Agent task calls `relay` with `run_in_background: true`, the subagent will complete before the peer (GPT) finishes, and the platform will kill the orphaned peer process. Always call `relay` from the main conversation. If a subagent must call relay (e.g., the skill was invoked before you could prevent it), the Bash call must run in foreground — omit `run_in_background` so the subagent blocks until the peer replies.

## Prism / Parallax

When Relay is used as the Parallax transport inside Prism, the relay call receives the **same full question and same context** as every local reviewer — only the lens (weighing posture) differs. Do not narrow the prompt for the Parallax agent. Prism dispatches each parallax call independently — the relay calls run concurrently as separate Bash invocations.

Launch each relay Bash call with `run_in_background: true` in the same parallel dispatch step as the local reviewer subagents. Do not wrap Relay itself in another subagent layer.

If a Parallax relay call fails (after its background completion notification has arrived), treat it as a recoverable transport problem. Check the relay script's Bash output for the diagnosed cause, fix the invocation, and retry once before declaring that peer unavailable — never read the `.log` sidecar (full stderr, token-heavy). A failed parallax call does not affect the other tiers.

## Utility Commands

`relay --help` and `relay --version` print usage and version info.

`--to` accepts only `gpt` (the default). There is no relay-to-Claude direction — Claude is the sole caller in this protocol.
