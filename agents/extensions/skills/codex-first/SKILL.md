---
effort: medium
name: codex-first
description: |
  Claude Code only. Delegate trusted, scoped implementation to `codex exec --yolo` — building from
  a spec, refactors, mechanical migrations, bug fixes with a repro, tests, CI/dependency/tooling,
  bulk code reading — while Claude writes the spec, picks `-e` effort, and reviews every diff.
  Auto-routes when enabled; also `/codex-first <task>`. Keep design, ambiguous specs, tiny edits,
  secrets/session-only tools, and all commit/push/GitHub ops in Claude. Unsandboxed: the review
  gates the diff, not the machine.
user-invocable: true
argument-hint: <task>
---

# Codex First

Claude Code only. **Codex implements; Claude specs and reviews.**

`codex exec --yolo` runs **unsandboxed**: `--cd` does not confine filesystem or network access. Claude's review gates the visible repo diff, **not the machine** — so delegate only **trusted, scoped** tasks and keep destructive/push ops Claude-side.

## Route

**Delegate** (clear work orders): implementation from a spec, refactors, mechanical migrations, bug fixes with a known repro, tests/coverage, CI/dependency/tooling, bulk code exploration.

**Keep in Claude:** design/API/naming/UX judgment; ambiguous work where the spec *is* the work; tiny edits (≲20 lines); secrets or session-only tools (MCP/browser/1Password); and — never delegated — commits, pushes, releases, GitHub mutations, and the review itself.

`/codex-first <task>` delegates `$ARGUMENTS` immediately via the flow below.

## Invoke

Write the spec, then spawn Codex with the bundled CLI — it appends fixed safety guardrails and runs `codex exec --yolo` from inside the repo. Prefer a clean tree (or throwaway `git worktree`) so the diff is attributable to Codex:

```bash
CF=~/.claude/skills/codex-first/scripts/codex-first
$CF -e <level> /abs/path/to/repo <<'EOF'
Goal: <what to build>. Target paths: <files/dirs>.
Proof: <exact command to run>.
EOF
# Final message: /tmp/codex-first.out.md; stderr: /tmp/codex-first.out.md.err
```

**Choose `-e <level>` by task difficulty** (never `none`) — see the [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning):

| `-e` | Use for |
|------|---------|
| `low` | simple, well-scoped mechanical edits; speed/cost priority |
| `medium` | typical implementation from a clear spec — the default starting point |
| `high` | hard reasoning: tricky multi-file changes, complex debugging, deep planning |
| `xhigh` | only the hardest architecture/analysis, where the extra latency clearly earns it |

- Gate on the exit code: nonzero or empty output = failed run; read the `.err`.
- Fix-up: `$CF -e <level> -r /abs/path/to/repo <<'EOF' … EOF` resumes the repo's last session; cap at 2 rounds, then finish in Claude.
- One delegation at a time uses the default output path; pass `-o <file>` for a parallel run in another repo.

## Verify (always)

- Read `git -C "$REPO" status -sb` + `git -C "$REPO" diff` (including untracked files); judge it like a PR — nothing outside the target paths, no commit/push.
- Re-run the proof yourself — Codex's claims are advisory. If the diff is wrong, fix forward or resume; **never** `git restore`/`reset` it away.

Done = intended diff only, proof passes, nothing out of scope.
