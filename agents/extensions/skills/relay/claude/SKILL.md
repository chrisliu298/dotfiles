---
name: relay
description: |
  The ONLY way to call Codex or DeepSeek. Use this skill whenever the user
  wants to ask, delegate to, or get a second opinion from Codex or DeepSeek.
  Do NOT run the codex or deepseek (ds) CLI directly — whether from the main
  agent or a subagent. Always use this skill's relay call command. Triggers
  on "ask codex", "ask deepseek", "have codex", "have deepseek", "send to
  codex", "send to deepseek", "get codex to", "get deepseek to", "delegate
  to codex", "delegate to deepseek", "second opinion", "relay". Invoke with
  "relay".
allowed-tools: Read, Write, Bash(relay:*), Bash(find:*), Bash(printf:*)
user-invocable: true
---

# Relay

**Claude-only.** If `ANTHROPIC_BASE_URL` contains `deepseek`, this skill is unavailable — stop and tell the user: "relay is Claude-only; DeepSeek cannot orchestrate other models from inside a DeepSeek session." The relay script itself also refuses at the shell layer.

Call Codex or DeepSeek like a function. One command: generates the request, invokes the peer, prints the response.

```
relay call --name <slug> [--to <peer>] [--effort <level>] [--body-only] <<'BODY'
task
BODY
```

The script is available as `relay` in PATH. The caller is always Claude (this is a Claude-only skill); the peer defaults to Codex. Pass `--to deepseek` to route to DeepSeek instead.

**All Codex and DeepSeek interactions go through `relay call`.** Do not invoke `codex exec` or the `ds`/`dsx` deepseek aliases directly, do not spawn agents to run the codex or claude CLI for these purposes, and do not pass model flags (`-m`, `--model`). The model and invocation method are hardcoded in the script.

## Peer selection

| Peer | When to pick | How to invoke |
|---|---|---|
| **Codex** (default) | Code review, security review, refactoring, agentic coding. GPT-5.5 lineage. Two effort tiers (`medium`/`xhigh`). | `relay call --name ...` (no `--to` needed) |
| **DeepSeek** | Independent model family for true cross-vendor diversity, frontier reasoning, multi-step analysis. Open-weight V4-Pro (1.6T MoE). Always runs at `max` (DeepThink). | `relay call --to deepseek --name ...` |

Pick Codex by default — it's the strongest general-purpose coding agent and integrates cleanly with the relay protocol. Pick DeepSeek when you want a perspective from a model trained outside both the Anthropic and OpenAI lineages, or when running `/prism` Parallax. DeepSeek always runs at `max`; `--effort` is silently ignored on DeepSeek calls, so just omit it. DeepSeek requires `DEEPSEEK_API_KEY` in the environment.

### Common Mistakes
- **Premature failure diagnosis**: If a relay call was launched with `run_in_background: true`, do not inspect `.relay` files or enter the failure flow until the background task's completion notification arrives. No notification means the peer is still running.
- **Wrapping relay in a subagent**: Do not spawn an Agent that then calls `relay` inside. When the subagent completes, the platform kills its child processes — including the still-running Codex CLI. Call `relay` directly from the main conversation with `run_in_background: true` instead.
- **Empty heredoc body**: The `<<'BODY'` ... `BODY` block must contain text. An empty body causes an immediate error.
- **Missing `--name`**: Every call requires `--name`. Omitting it is a script error, not a peer failure.

## Example

```bash
relay call --name auth-review --effort medium <<'BODY'
Review src/auth.py for security issues. Run pytest to verify.
BODY
```

## Effort Levels

`--effort` applies to Codex only. DeepSeek always runs at `max` (DeepThink) — the flag is silently ignored on DeepSeek calls, so just omit it.

| Level | When to use |
|-------|-------------|
| `medium` | **Default for Codex.** Balanced starting point for code review, tests, bug fixes, and most refactoring. |
| `xhigh` | Codex only. Hard architecture work, deep security review, or eval-bound tasks worth the extra latency. |

Before raising effort, improve the prompt first — add outcome-first success criteria, stop rules, verification steps, and completeness criteria.

## Prompting Codex

**Before composing the prompt body, read the prompt-engineer references** — `~/.claude/skills/prompt-engineer/references/gpt.md` for cross-cutting GPT-5.5 prompt patterns and `~/.claude/skills/prompt-engineer/references/codex.md` for Codex coding agent patterns. If those symlinks are unavailable, use the repo copies at `agents/extensions/skills/prompt-engineer/references/`. This is not optional — the guides contain model-specific patterns that materially affect output quality.

Lead with the outcome, not the procedure. GPT-5.5 responds best to outcome-first prompts — state the goal, success criteria, and stop rules, then let Codex pick the path. Reach for XML scaffolding only when a specific failure mode needs it:

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

## Prompting DeepSeek

**Before composing the prompt body, read `~/.claude/skills/relay/references/deepseek.md`** (symlinked to the prompt-engineer reference). It covers the CO-STAR framework, XML scaffolding conventions, thinking-mode quirks, and DeepThink failure modes. This is not optional — the guide contains model-specific patterns that materially affect output quality.

Default to XML scaffolding (DeepSeek V4 was trained heavily on XML-tagged data). The CO-STAR sections — `<context>`, `<objective>`, `<style>`, `<tone>`, `<audience>`, `<response_format>` — give the cleanest results for non-trivial tasks. Use positive framing ("include X") over negative constraints ("don't omit X"). Keep system-style meta-instructions out of the prompt body — DeepThink (always on for DeepSeek calls) degrades under long system prompts.

**Example:**

```bash
relay call --to deepseek --name pool-design <<'BODY'
<context>
We're hardening src/db/pool.py before a SOC 2 audit. Codebase is Python 3.12 +
FastAPI. Tests live in tests/test_pool.py and run under pytest.
</context>

<objective>
Add connection timeouts and stale-connection recovery to src/db/pool.py.
</objective>

<success_criteria>
- ConnectionPool accepts a timeout_seconds parameter at construction
- stale connections are auto-reconnected on use
- a reclaim_stale() method exists for explicit cleanup
- existing callers keep working without changes
- pytest tests/test_pool.py passes; no new lint errors
</success_criteria>

<response_format>
Summary of changes first (one line per change: file path + description),
then the diffs grouped by file. Cap at 400 words excluding diffs.
</response_format>
BODY
```

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

1. **Check the Bash output.** The relay script prints diagnostic information (exit code, error summary) to stdout/stderr. Use this — visible in the Bash tool result — to identify the cause. **Do not read the `.log` sidecar file** — it contains the peer's full stderr and is extremely long and token-heavy.
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

**Rule: Launch relay calls and subagents concurrently. Never serialize independent work.**

**Never wrap relay in a subagent.** If an Agent task calls `relay` with `run_in_background: true`, the subagent will complete before the peer (Codex or DeepSeek) finishes, and the platform will kill the orphaned peer process. Always call `relay` from the main conversation. If a subagent must call relay (e.g., the skill was invoked before you could prevent it), the Bash call must run in foreground — omit `run_in_background` so the subagent blocks until the peer replies.

## Prism / Parallax

When Relay is used as the Parallax transport inside Prism, the relay call receives the **same full question and same context** as every local reviewer — only the lens (weighing posture) differs. Do not narrow the prompt for the Parallax agent. With two peers available, Prism dispatches each parallax tier independently — Codex calls and DeepSeek calls run concurrently as separate Bash relay invocations.

Launch each relay Bash call with `run_in_background: true` in the same parallel dispatch step as the local reviewer subagents. Do not wrap Relay itself in another subagent layer.

If a Parallax relay call fails (after its background completion notification has arrived), treat it as a recoverable transport problem. Check the relay script's Bash output for the diagnosed cause, fix the invocation, and retry once before declaring that peer unavailable — never read the `.log` sidecar (it contains the peer's full stderr and is extremely long and token-heavy). A failure of one peer (e.g., Codex) does not affect the other.

## Utility Commands

`relay --help` and `relay --version` print usage and version info.

`--to` accepts `codex` (default) or `deepseek`. There is no relay-to-Claude direction — Claude is the sole caller in this protocol.
