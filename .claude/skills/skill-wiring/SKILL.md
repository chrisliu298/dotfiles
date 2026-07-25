---
name: skill-wiring
description: How this dotfiles repo wires skills, MCP servers, and Claude plugins — where to edit each kind of skill, the SKILLS/MCP_SERVERS/PLUGINS tables in dotfiles.sh, manual-skill toggling, and the authoring rules for universal (Claude/Codex/Grok/Pi) skills. Use when adding, editing, moving, scoping, enabling, or disabling a skill, MCP server, or plugin in this repo, or when a skill's symlink or agent targeting looks wrong.
---

# Skill wiring in dotfiles

`agents/skills/` is the single source of truth for repo-owned skills. `dotfiles.sh`
symlinks each into the agent dirs its `SKILLS` table selects. Run `./dotfiles.sh`
after any change to re-sync symlinks.

## Editing skills

The root `CLAUDE.md`/`AGENTS.md` carries the one rule you must not miss: never edit
in `~/.claude/skills/`, `~/.codex/skills/`, `~/.grok/skills/`, or
`~/.pi/agent/skills/` — those are symlinks. Check `agents/skills/README.md` for source.

- **Own skills** (`agents/skills/`): edit in this repo — the single source of truth.
- **Third-party skills** (cloned from GitHub): edit in the source repo or fork.
- **Best practices**: read `agents/skills/references/skill-best-practices.md` before
  creating or improving skills.
- **Description length**: every skill's `description` frontmatter must stay under
  1024 characters — trim it before committing.
- **Universal (C/X/G — Claude/Codex/Grok) skills**: read
  `agents/skills/references/universal-skill-authoring.md` before editing a skill
  shared across all these agents — keep the body harness-agnostic (no `$ARGUMENTS`,
  no bare `AskUserQuestion`/`Skill()`, capability-not-runtime degradation). Pi
  consumes this same shared set (mirroring the Codex/Grok column), so the
  harness-agnostic rules apply to it too. `./dotfiles.sh` warns on the mechanical
  violations; `./dotfiles.sh lint` runs the check on demand.
- **Verify vendor guidance**: before updating skills with vendor/model guidance,
  check against official current docs — don't preserve stale model names or
  deprecated API parameters.
- **Validate referenced paths**: when skill docs reference installed or symlinked
  paths, verify they exist after `./dotfiles.sh`.

## Adding extensions

Managed by the `SKILLS` table in `dotfiles.sh` (local path or GitHub clone +
symlink, no `npx skills`):

- **Local**: add `<name>/SKILL.md` under `agents/skills/`, run `./dotfiles.sh`.
- **Upstream**: add a `name|owner/repo/subpath|agents` entry to the `SKILLS` table.
- **Agent-specific**: separate table entries per agent (e.g., `pdf` has different
  sources for claude vs codex/grok).
- **Manual skills**: add the name to the `MANUAL_SKILLS` array — skipped during
  auto-install, toggled with `./dotfiles.sh enable/disable <name>`. Enabled state is
  a committed declarative set in `agents/skills/manual-skills.enabled` (one name per
  line; empty = all off), enforced on every run (symlink the listed, prune the rest)
  and propagated by `dfs` — not per-machine local.
- **Project-local skills**: place in `.claude/skills/<name>/` — available only in
  this repo, not globally.
- **Install/update all**: `./dotfiles.sh`.

A single `SKILL.md` can work across agents when written harness-agnostically.
Include Claude-specific frontmatter (`allowed-tools`, `user-invocable`) where
needed — Codex/Grok ignore unknown keys.

MCP servers and Claude plugins are wired the same way, via the `MCP_SERVERS` and
`PLUGINS` tables in `dotfiles.sh` — see `agents/skills/README.md` for the full
catalog.

## Naming and shape

- Lowercase kebab-case for skill directories (e.g., `arxiv-reader`, `keep-warm`).
- Each skill has a single `SKILL.md`; most work across Claude Code, Codex, Grok, and
  Pi, but the `SKILLS` table can scope one to specific agents.

## Verifying

- Run `./dotfiles.sh` and confirm symlinks resolve correctly.
- Run `./dotfiles.sh lint` when editing universal skills or skill-install logic.
- For skills with Python scripts, run `uv run pytest` on the relevant test file.
