---
name: relay
description: |
  The ONLY way to call Codex. Use this skill whenever the user wants to
  ask, delegate to, or get a second opinion from Codex. Do NOT run the
  codex CLI directly — whether from the main agent or a subagent. Always
  use this skill's relay call command. Triggers on "ask codex", "have
  codex", "send to codex", "get codex to", "delegate to codex", "second
  opinion", "relay". Invoke with "relay".
allowed-tools: Read, Write, Bash(relay:*), Bash(find:*), Bash(printf:*)
user-invocable: true
---

# Relay

Call Codex like a function. One command: generates the request, invokes Codex, prints the response.

```
relay call --name <slug> [--effort <level>] [--body-only] <<'BODY'
task
BODY
```

The script is available as `relay` in PATH. It auto-detects caller/peer from environment variables (`CLAUDECODE=1` for Claude Code, `CODEX_SANDBOX` for Codex) or from its install path.

**All Codex interactions go through `relay call`.** Do not invoke `codex exec` directly, do not spawn agents to run the codex CLI, and do not pass model flags (`-m`, `--model`). The model and invocation method are hardcoded in the script.

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

Choose `--effort` based on the task:

| Level | When to use |
|-------|-------------|
| `none` | No thinking needed: reformat, extract fields, find-and-replace |
| `low` | Light thinking: triage, classify, apply a well-defined migration |
| `medium` | **Default.** Code review, writing tests, fixing bugs |
| `high` | Deeper reasoning: security audit, complex refactoring |
| `xhigh` | Avoid unless necessary. Multi-file architectural redesign |

Before raising effort, improve the prompt first — add output contracts, verification steps, completeness criteria.

## Prompting Codex

**Before composing the prompt body, read the references in `~/.claude/skills/relay/references/`** — `gpt.md` for cross-cutting GPT-5.5 prompt patterns, `codex.md` for Codex coding agent patterns. (If not found, try `relay --help` to locate the install path.) This is not optional — the guides contain model-specific patterns that materially affect output quality.

Use XML tags for structure. Key patterns:

- `<output_contract>` — exact format and structure expected
- `<completeness_contract>` — what "done" means explicitly
- `<verification_loop>` — check correctness before finalizing

**Example:**

```bash
relay call --name pool-refactor --effort medium <<'BODY'
Refactor src/db/pool.py to add connection timeouts.

1. Add timeout_seconds param to ConnectionPool.__init__
2. Implement auto-reconnection for stale connections
3. Add reclaim_stale() method
4. Keep backward compatibility

<output_contract>
Summary of changes, one per line, with file path and description.
</output_contract>

<verification_loop>
Run pytest tests/test_pool.py — all tests must pass.
</verification_loop>

<completeness_contract>
Done means: all 4 requirements implemented, tests pass, no new lint errors.
</completeness_contract>
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

**Never wrap relay in a subagent.** If an Agent task calls `relay` with `run_in_background: true`, the subagent will complete before Codex finishes, and the platform will kill the orphaned Codex process. Always call `relay` from the main conversation. If a subagent must call relay (e.g., the skill was invoked before you could prevent it), the Bash call must run in foreground — omit `run_in_background` so the subagent blocks until Codex replies.

## Prism / Parallax

When Relay is used as the Parallax transport inside Prism, the relay call receives the **same full question and same context** as every local reviewer — only the lens (weighing posture) differs. Do not narrow the prompt for the Parallax agent.

Launch the relay Bash call with `run_in_background: true` in the same parallel dispatch step as the local reviewer subagents. Do not wrap Relay itself in another subagent layer.

If the Parallax relay call fails (after its background completion notification has arrived), treat it as a recoverable transport problem. Read the `.log` sidecar, fix the invocation, and retry once before declaring Parallax unavailable.

## Utility Commands

`relay --help` and `relay --version` print usage and version info.

If auto-detection fails, pass `--from claude --to codex` explicitly to `call`.
