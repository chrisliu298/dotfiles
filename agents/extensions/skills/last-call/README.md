# Last Call

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that performs a thorough quality review before you end a session.**

> *Last call at the bar — one final check before the lights go out.*

You've been deep in a session, shipping changes across multiple files. Before you close the terminal, Last Call reads every changed line with production-shipping rigor and surfaces what you missed: bugs, stale docs, debug artifacts, incomplete migrations, loose ends.

Invoke with `/last-call` or ask your agent to "do a last call review" or "review the session before we wrap up".

## Table of Contents

- [Why](#why)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [What It Catches](#what-it-catches)
- [Output](#output)
- [Contributors](#contributors)

---

## Why

End-of-session is when mistakes slip through. You're tired, the diff is large, and you've been staring at the same code for hours. A fresh set of eyes catches what fatigue hides:

- **No sampling** — reads every changed file in full context, not just diff hunks
- **Flags, doesn't fix** — reports findings with file paths and line numbers so you decide what to act on
- **Mechanical cleanup** — removes obvious debug artifacts and typos automatically, nothing else
- **Session-aware** — knows what commits belong to this session and scopes the review accordingly

### Why not just review the diff?

A diff shows what changed. Last Call reads the whole file to understand whether the change is correct *in context* — does the new code break an assumption three functions away? Did the README fall out of sync? Is there a TODO you forgot?

---

## How It Works

1. **Identify scope** — finds session commits (from conversation history or last 2 hours), uncommitted changes, untracked files, and stashed work
2. **Deep review** — reads every changed file end-to-end and evaluates correctness, documentation debt, architecture consistency, and session completeness
3. **Act and report** — applies mechanical fixes (debug artifacts, typos), proposes documentation updates, and delivers a structured report with severity ratings

For large change sets (10+ files), review lenses run as parallel subagents for depth.

---

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/last-call.git ~/.claude/skills/last-call
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/last-call.git ~/.codex/skills/last-call
```

---

## What It Catches

Every finding is rated **critical**, **warning**, or **nit** with file path and line number.

| Lens | Examples |
|------|----------|
| **Correctness** | Bugs, logic errors, race conditions, security issues, incomplete implementations, leftover debug statements, test gaps |
| **Documentation** | Stale READMEs, outdated CLAUDE.md/AGENTS.md references, undocumented new behavior, missing changelog entries |
| **Architecture** | Broken conventions, unearned abstractions, incomplete migrations, violated contracts |
| **Session completeness** | Original goal not fully addressed, scope creep, uncommitted work that should be staged or gitignored |

---

## Output

```
## Session Review

### Accomplished
- [What was done this session]

### Fixes Applied
- [Debug artifacts removed, typos fixed — with file:line]

### Needs Attention
- [Findings requiring action — severity, file:line, recommendation]

### Documentation Proposals
- [Draft updates for stale/missing docs — show the proposed content]

### Loose Ends
- [Uncommitted work, stashed changes, TODOs, incomplete migrations]
```

Empty sections are omitted. No filler.

---

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** — review protocol design and severity framework
