# Repository Guidelines

Personal dotfiles and AI agent configurations for macOS with zsh, managed by `dotfiles.sh` (the single entrypoint: initializes submodules, symlinks configs into `~`, installs skills, and registers MCP servers + Claude plugins).

> **Project-level doc.** Global Codex/Grok instructions live in `agents/codex/AGENTS.md` and `agents/grok/AGENTS.md`. Keep this file aligned with the sibling `CLAUDE.md` — same facts and section order; only the H1, this pointer, and Claude's `<important>` wrappers may differ.

## Project Structure & Module Organization

```
dotfiles/
├── dotfiles.sh              # Single entrypoint: submodules, symlinks, skills, MCP, plugins
├── README.md                # Top-level usage + maintenance docs
├── CLAUDE.md, AGENTS.md     # Repo-level guidance (this file and its counterpart for the other agents)
├── shell/                   # Zsh config (.zshrc, .zshenv, .aliases, .functions)
├── .config/                 # App configs (nvim, tmux, btop, starship, ghostty, fastfetch)
├── .claude/skills/          # Project-local Claude skills (this repo only)
└── agents/
    ├── claude/              # Claude Code (~/.claude/) — CLAUDE.md, settings.json (copied), keybindings, statusline
    ├── codex/               # Codex (~/.codex/) — AGENTS.md
    ├── grok/                # Grok Build (~/.grok/) — AGENTS.md (relay/prism dispatch target)
    ├── pi/                  # Pi (~/.pi/agent/) — AGENTS.md, settings.json
    ├── eval/                # Instruction-following harness for the shared agent doc (prompts, rubric, runner scripts)
    └── skills/              # Repo-owned skill sources (one SKILL.md each) + authoring refs, wired by the SKILLS table
```

- `.config/ghostty`: Ghostty/cmux terminal config — tracked in-repo (not fetched from the standalone `chrisliu298/ghostty-config` repo), symlinked like the rest of `.config/`.
- `agents/skills/` is the single source of truth for repo-owned skills; `dotfiles.sh` symlinks each into the agent dirs the `SKILLS` table selects (most to Claude/Codex/Grok/Pi; some are Claude-only). Pi (`~/.pi/agent/skills/`) mirrors the Codex/Grok set and additionally loads its own native npm extensions declared in `agents/pi/settings.json`.
- `.claude/skills/` holds project-local skills available only when working in this repo.
- The four global instruction files (`agents/claude/CLAUDE.md` + `agents/{codex,grok,pi}/AGENTS.md`) are one canonical, agent-read text copied to all four paths, **identical except the H1** (which just names each file — `# CLAUDE.md` vs `# AGENTS.md`). Edit one, copy to the other three (keeping each H1); `./dotfiles.sh lint` asserts the bodies match. Behavior parity across models when the text changes is checked by the harness in `agents/eval/`.

## Build, Test, and Development Commands

- `./dotfiles.sh` — initialize submodules, sync skill repos, symlink files, install skills, and register MCP servers + plugins.
- `./dotfiles.sh lint` — run skill portability checks (universal C/X/G skill mechanical violations); also runs automatically at the end of a full `./dotfiles.sh`.
- `./dotfiles.sh skills` — list manual skills and whether each is enabled.
- `./dotfiles.sh enable <name>` / `./dotfiles.sh disable <name>` — toggle a manual skill; rewrites the committed `agents/skills/manual-skills.enabled` set, so commit + `dfs` to propagate the change to every machine.
- `git status --short` — confirm only intended files changed before committing.
- `rg --files` — inspect tracked structure when adding/updating files or skills.
- `uv venv && source .venv/bin/activate` — initialize a local Python environment for script-based skills.

## Conventions

- **Shell load order**: `shell/.zshenv` (platform detection, env, PATH) → `shell/.zshrc` (plugins, sources `.aliases` + `.functions`)
- **Modern tools**: `fd` → find, `rg` → grep, `delta` → diff, `zoxide` → z (installed via Zinit, macOS ARM)
- **Platform detection**: `IS_MACOS` set in `shell/.zshenv`, gates macOS-only code
- **Python**: use `uv` for virtual environments (`sv`, `us`, `ua`, `upi` aliases)
- **Prompt**: Starship (Catppuccin Latte/GitHub Dark palettes, config in `.config/starship/`)
- **Themes**: Ghostty, Starship, btop, and tmux (Catppuccin Latte/GitHub Light ↔ GitHub Dark), toggled with `theme light|dark|toggle|status`; use `theme --all <mode>` to apply the same mode on this host plus macmini and l40s. The active choice is **host-local** — a single `mode` file under `~/.local/state/dotfiles-theme/` (never tracked, so switching never dirties git); definitions stay in-repo. `shell/theme-apply` materializes each tool's live config from `mode` (Ghostty/tmux via optional `config-file`/`source-file -q` includes; btop/Starship as generated files, since neither supports includes), and `dotfiles.sh` seeds/re-applies it per host.

## Editing Skills

Never edit in `~/.claude/skills/`, `~/.codex/skills/`, `~/.grok/skills/`, or `~/.pi/agent/skills/` — those are symlinks. Check `agents/skills/README.md` for source.

- **Own skills** (`agents/skills/`): edit in this repo — the single source of truth.
- **Third-party skills** (cloned from GitHub): edit in the source repo or fork.
- **Best practices**: read `agents/skills/references/skill-best-practices.md` before creating or improving skills.
- **Description length**: every skill's `description` frontmatter must stay under 1024 characters — trim it before committing.
- **Universal (C/X/G — Claude/Codex/Grok) skills**: read `agents/skills/references/universal-skill-authoring.md` before editing a skill shared across all these agents — keep the body harness-agnostic (no `$ARGUMENTS`, no bare `AskUserQuestion`/`Skill()`, capability-not-runtime degradation). Pi now consumes this same shared set (mirroring the Codex/Grok column), so the harness-agnostic rules apply to it too. `./dotfiles.sh` warns on the mechanical violations; `./dotfiles.sh lint` runs the check on demand.
- **Verify vendor guidance**: before updating skills with vendor/model guidance, check against official current docs — don't preserve stale model names or deprecated API parameters.
- **Validate referenced paths**: when skill docs reference installed or symlinked paths, verify they exist after `./dotfiles.sh`.

Run `./dotfiles.sh` after changes to re-sync symlinks.

## Adding Extensions

Managed by the `SKILLS` table in `dotfiles.sh` (local path or GitHub clone + symlink, no `npx skills`):

- **Local**: add `<name>/SKILL.md` under `agents/skills/`, run `./dotfiles.sh`.
- **Upstream**: add a `name|owner/repo/subpath|agents` entry to the `SKILLS` table.
- **Agent-specific**: separate table entries per agent (e.g., `pdf` has different sources for claude vs codex/grok).
- **Manual skills**: add the name to the `MANUAL_SKILLS` array — skipped during auto-install, toggled with `./dotfiles.sh enable/disable <name>`. Enabled state is a committed declarative set in `agents/skills/manual-skills.enabled` (one name per line; empty = all off), enforced on every run (symlink the listed, prune the rest) and propagated by `dfs` — not per-machine local.
- **Project-local skills**: place in `.claude/skills/<name>/` — available only in this repo, not globally.
- **Install/update all**: `./dotfiles.sh`.

A single `SKILL.md` can work across agents when written harness-agnostically. Include Claude-specific frontmatter (`allowed-tools`, `user-invocable`) where needed — Codex/Grok ignore unknown keys.

MCP servers and Claude plugins are wired the same way, via the `MCP_SERVERS` and `PLUGINS` tables in `dotfiles.sh` — see `agents/skills/README.md` for the full catalog.

## Coding Style & Naming Conventions

- Use Markdown for guides and skill instructions, with short sections and actionable bullets.
- Shell scripts stay Bash-first, with clear helper functions and defensive flags (`set -euo pipefail`).
- Use lowercase kebab-case for skill directories (e.g., `arxiv-reader`, `keep-warm`).
- Each skill has a single `SKILL.md`; most work across Claude Code, Codex, and Grok, but the `SKILLS` table can scope one to specific agents.
- Follow `.gitignore`; never commit secrets, caches, or local environment artifacts.
- Don't refactor or reformat unrelated files as part of a doc/skill edit.

## Testing Guidelines

- Primary validation is functional: run `./dotfiles.sh` and verify symlinks resolve correctly.
- Run `./dotfiles.sh lint` when editing universal skills or skill-install logic.
- For skills with Python scripts, run `uv run pytest` on the relevant test file.
- If you add scripts, include at least one runnable verification path (a test or a documented command).

## Commit & Pull Request Guidelines

- Match existing history: imperative, concise subjects (`Add ...`, `Update ...`, `Remove ...`, `Refactor ...`).
- Keep commits atomic by logical change (docs vs scripts vs skill content).
- PRs include: purpose, changed paths, verification commands run, and any migration/symlink impact. Link related issues; add screenshots only for UI-facing documentation changes.
- **Sync after push**: after `git push` succeeds, run `dfs` (a `shell/.functions` helper) to propagate to peers — concurrent `git pull --ff-only` + `./dotfiles.sh` on `macbookpro16`, `macmini`, `l40s`; the current host is skipped. Skipping this leaves the other machines on the previous revision. Non-interactive/agent shells: `zsh -c 'source ~/dotfiles/shell/.functions && dfs'` (self-contained; no TTY or `.zshrc` needed).

## Maintaining Docs

- **Sync root docs**: keep root `CLAUDE.md` and root `AGENTS.md` aligned — same facts and section order, diverging only in the H1, the project-level pointer, and Claude's `<important>` wrappers.
- **Sync global instructions**: the four global instruction files (`agents/claude/CLAUDE.md` + `agents/{codex,grok,pi}/AGENTS.md`) are one canonical, agent-read text, **identical except the H1** (which names each file — `# CLAUDE.md` vs `# AGENTS.md`). Edit one, copy to the other three (keeping each H1), commit together. `./dotfiles.sh lint` asserts the bodies match and fails on any other diff. When the text changes, check behavior parity across models with the harness in `agents/eval/`.
- **Update docs**: after structural changes (adding, removing, or renaming files/directories, skills, or configs), check whether `README.md`, `CLAUDE.md`, or `AGENTS.md` reference the affected paths and update them.

## Not Backed Up

OAuth tokens, command history, local settings, the host-local active theme (`~/.local/state/dotfiles-theme/`, so each machine keeps its own light/dark), per-project data, and cache files. API keys live in `~/.zshenv.local` (not in the repo, so `dfs` never carries them) — after adding a new `export *_API_KEY=` or `*_PLAN_KEY=` locally, run `synckeys` (a `shell/.functions` helper, not a `dotfiles.sh` subcommand) — dry-run first, then `synckeys apply` — to propagate it to the other machines.
