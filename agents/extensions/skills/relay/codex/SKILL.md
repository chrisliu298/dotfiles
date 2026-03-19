---
name: relay
description: |
  The ONLY way to call Claude Code. Use this skill whenever the user wants
  to ask, delegate to, or get a second opinion from Claude. Do NOT invoke
  the claude CLI directly — whether from the main agent or a subagent.
  Always use this skill's relay call command. Triggers on "ask claude",
  "have claude", "send to claude", "get claude to", "delegate to claude",
  "second opinion", "relay". Invoke with /relay.
---

# Relay

Call Claude Code like a function. One command: generates the request, invokes Claude, prints the response.

```
relay call --name <slug> [--effort <level>] [--body-only] <<'BODY'
task
BODY
```

The script is available as `relay` in PATH. It auto-detects caller/peer from environment variables (`CODEX_SANDBOX` for Codex, `CLAUDECODE=1` for Claude Code) or from its install path.

**All Claude interactions go through `relay call`.** Do not invoke the `claude` CLI directly, do not pass model flags (`--model`), and do not use `--dangerously-skip-permissions` yourself. The model and invocation method are hardcoded in the script.

### Common Mistakes
- **Premature failure diagnosis**: If a relay call is running in a subagent, do not inspect `.relay` files or diagnose failure from the main agent before the subagent has returned. The subagent blocks until the relay call completes — wait for it.
- **Empty heredoc body**: The `<<'BODY'` ... `BODY` block must contain text. An empty body causes an immediate error.
- **Missing `--name`**: Every call requires `--name`. Omitting it is a script error, not a peer failure.
- **Shell backgrounding**: Do not use `&`, `disown`, or `nohup` with relay calls. Use subagents for concurrency instead.

## Example

```bash
relay call --name auth-review <<'BODY'
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

The `--effort` flag controls Codex's reasoning effort directly. When calling Claude (the peer direction), `--effort` is accepted by `relay call` but omitted from the request metadata — Claude does not expose a reasoning effort parameter.

Before raising effort, improve the prompt first — add output contracts, verification steps, completeness criteria.

## Prompting Claude

**Before composing the prompt body, read `~/.codex/skills/relay/references/prompting-claude.md`.** (If not found, try `relay --help` to locate the install path.) This is not optional — the guide contains model-specific patterns that materially affect output quality.

Be clear and direct. Use XML tags to separate concerns. Key patterns:

- `<context>` — background and motivation (why, not just what)
- `<instructions>` — numbered steps for multi-part tasks
- `<example>` — example output if format matters

Don't over-prompt — Claude Opus is proactive; avoid excessive MUSTs/NEVERs.

**Example:**

```bash
relay call --name auth-hardening <<'BODY'
<context>
We're hardening auth before a security audit. The auth module has had
significant changes in the last 6 months.
</context>

<instructions>
Review src/auth.py for OWASP Top 10 vulnerabilities, focusing on injection
and broken access control.

1. Read src/auth.py and identify all vulnerabilities
2. Fix each one in-place
3. Run pytest to verify all tests pass
4. Return a summary: one line per fix, with line number and what changed
</instructions>
BODY
```

## Output

The script prints the response file content to stdout. The response has YAML frontmatter followed by free-form markdown:

- **Frontmatter**: `relay`, `re`, `from`, `to`, `status` (`done` | `error`), `verify` (`pass` | `fail` | `skip`)
- **Body**: findings, changes, reasoning — free-form markdown below the frontmatter fence

Use `--body-only` to strip the frontmatter and get just the markdown body.

Request and response files are saved in `.relay/` (auto-gitignored). Peer stderr is logged to a `.log` sidecar file alongside the request.

### When a relay call fails

**You must diagnose and retry — do not report failure to the user without attempting a fix first.**

**Subagent guard:** If the relay call is running inside a subagent, this diagnosis flow applies only after the subagent has returned. Until the subagent completes, the relay call is still in progress — do not inspect `.relay` files from the main agent or conclude the peer has failed.

When a completed relay call reports a missing response file, the peer failed before producing output. Each call generates a new request ID, so retrying does not re-execute previous attempts.

1. **Read the log.** Read the `.log` sidecar file whose path is printed in the error output (`relay: peer log  → <path>`). The log contains the peer's stderr — the actual error message.
2. **Diagnose.** Common causes and fixes:
   - *Peer binary not found* → verify the peer CLI is installed and in PATH
   - *Empty body / malformed heredoc* → verify the heredoc has content and a matching terminator
   - *Peer exited non-zero but response file exists* → not a failure; read the response file
3. **Fix and retry once.** Correct the invocation based on the diagnosis and re-run the relay call.
4. **If the retry also fails**, read the log again. Only then report the failure to the user with the diagnosed cause.

The first failure is information, not a stop signal.

## Async / Parallel

Codex supports concurrency via native parallel tool calls and subagents, but **not** via shell backgrounding (`&`/`disown`/`nohup`). Background child processes do not survive after the shell command returns in Codex's sandbox.

Recommended pattern when you have independent work alongside a relay call:

1. Start any independent local work in parallel tool calls.
2. Spawn a Codex subagent whose only job is to run the blocking relay call.
3. Continue local work in the main agent.
4. Wait for the relay subagent only when you need Claude's answer. The subagent's return is the only readiness signal — do not inspect `.relay` files from the main agent before the subagent completes.

**Rule: Never serialize independent work. Use subagents to run relay calls concurrently with local work.**

## Prism / Parallax

When Relay is used as the Parallax transport inside Prism, the relay call receives the **same full question and same context** as every local reviewer — only the lens (weighing posture) differs. Do not narrow the prompt for the Parallax agent.

For Codex Prism runs, spawn a Codex subagent whose only job is to run the blocking relay call. Launch it concurrently with the local reviewer subagents via parallel tool calls.

If the relay call used for Parallax fails (after the subagent has returned), read the `.log` sidecar, fix the invocation, and retry once before proceeding without Parallax.

## Utility Commands

`relay --help` and `relay --version` print usage and version info.

If auto-detection fails, pass `--from codex --to claude` explicitly to `call`.
