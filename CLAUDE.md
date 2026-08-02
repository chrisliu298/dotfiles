# CLAUDE.md

Personal dotfiles and AI agent configurations for macOS with zsh, managed by `dotfiles.sh` (the single entrypoint: initializes submodules, symlinks configs into `~`, installs skills, and registers MCP servers + Claude plugins + tmux plugins).

> **Project-level doc.** Global Claude instructions live in `agents/claude/CLAUDE.md`. Keep this file aligned with the sibling `AGENTS.md` — same facts and section order; only the H1, this pointer, and Claude's `<important>` wrappers may differ.

## Project Structure & Module Organization

Four `agents/<name>/` directories target one agent's home each: `claude/` → `~/.claude/` (`CLAUDE.md`, `settings.json` — copied, not symlinked — keybindings, statusline, themes), `codex/` → `~/.codex/`, `grok/` → `~/.grok/` (relay/prism dispatch target), `pi/` → `~/.pi/agent/`. The rest are not agent homes:

- `agents/eval/` — instruction-following harness for the shared agent doc (prompts, rubric, runner scripts).
- `agents/hooks/` — shared Claude/Codex destructive-command guard and tests.
- `agents/skills/` — the single source of truth for repo-owned skills; `dotfiles.sh` symlinks each into the agent dirs the `SKILLS` table selects (most to Claude/Codex/Grok/Pi; some are Claude-only). Pi (`~/.pi/agent/skills/`) mirrors the Codex/Grok set and additionally loads its own native npm extensions declared in `agents/pi/settings.json`.

Elsewhere:

- `.claude/skills/` holds project-local skills available only when working in this repo.
- `.config/ghostty`: Ghostty/cmux terminal config — tracked in-repo (not fetched from the standalone `chrisliu298/ghostty-config` repo), symlinked like the rest of `.config/`.
- The four global instruction files (`agents/claude/CLAUDE.md` + `agents/{codex,grok,pi}/AGENTS.md`) are one canonical, agent-read text copied to all four paths, **identical except the H1** (which just names each file — `# CLAUDE.md` vs `# AGENTS.md`). Edit one, copy to the other three (keeping each H1); `./dotfiles.sh lint` asserts the bodies match. Behavior parity across models when the text changes is checked by the harness in `agents/eval/`.

## Build, Test, and Development Commands

- `./dotfiles.sh` — initialize submodules, sync skill repos, symlink files, install skills, and register MCP servers + Claude plugins + tmux plugins (TPM).
- `./dotfiles.sh lint` — run skill portability checks (universal C/X/G skill mechanical violations); also runs automatically at the end of a full `./dotfiles.sh`.
- `./dotfiles.sh skills` — list manual skills and whether each is enabled.
- `./dotfiles.sh enable <name>` / `./dotfiles.sh disable <name>` — toggle a manual skill; rewrites the committed `agents/skills/manual-skills.enabled` set, so commit + `dfs` to propagate the change to every machine.

## Conventions

- **Shell load order**: `shell/.zshenv` (platform detection, env, PATH) → `shell/.zshrc` (plugins, sources `.aliases` + `.functions`)
- **Themes**: Ghostty, Starship, btop, tmux, and pi (Catppuccin Latte/GitHub Light ↔ GitHub Dark), toggled with `theme light|dark|toggle|status`; use `theme --all <mode>` to apply the same mode on this host plus macmini and l40s. The active choice is **host-local** — a single `mode` file under `~/.local/state/dotfiles-theme/` (never tracked, so switching never dirties git); definitions stay in-repo. `shell/theme-apply` materializes each tool's live config from `mode` (Ghostty/tmux via optional `config-file`/`source-file -q` includes; btop/Starship as generated files, since neither supports includes), and `dotfiles.sh` seeds/re-applies it per host. pi is the special case: it pins its `theme` setting to the custom theme `dotfiles`, and `theme-apply` swaps *what that theme is* by copying `agents/pi/themes/<mode>.json` to `~/.pi/agent/themes/dotfiles.json` — pi watches that file, so running sessions repaint without a restart. It needs this because its auto mode (`theme: "light/dark"`, since 0.79.7) resolves from terminal background detection rather than from `mode`, so it would ignore `theme --all` whenever the terminal disagrees with the host's chosen mode (notably SSH sessions into macmini/l40s).

## Skills, MCP Servers & Plugins

Never edit in `~/.claude/skills/`, `~/.codex/skills/`, `~/.grok/skills/`, or `~/.pi/agent/skills/` — those are symlinks. Check `agents/skills/README.md` for source.

Wiring details — where each kind of skill is edited, the `SKILLS`/`MCP_SERVERS`/`PLUGINS` tables, manual-skill toggling, and the universal-skill authoring rules — live in the `skill-wiring` skill in `.claude/skills/`. Run `./dotfiles.sh` after any change to re-sync symlinks.

## Testing Guidelines

- Primary validation is functional: run `./dotfiles.sh` and verify symlinks resolve correctly.
- Run `./dotfiles.sh lint` when editing universal skills or skill-install logic.
- For skills with Python scripts, run `uv run pytest` on the relevant test file.
- If you add scripts, include at least one runnable verification path (a test or a documented command).

<important if="you are committing and pushing changes to this repo">

## Commit & Pull Request Guidelines

- Match existing history: imperative, concise subjects (`Add ...`, `Update ...`, `Remove ...`, `Refactor ...`).
- Keep commits atomic by logical change (docs vs scripts vs skill content).
- PRs include: purpose, changed paths, verification commands run, and any migration/symlink impact. Link related issues; add screenshots only for UI-facing documentation changes.
- **Sync after push**: after `git push` succeeds, run `dfs` (a `shell/.functions` helper) to propagate to peers — concurrent `git pull --ff-only` + `./dotfiles.sh` on `macbookpro16`, `macmini`, `l40s`; the current host is skipped. Skipping this leaves the other machines on the previous revision. Non-interactive/agent shells: `zsh -c 'source ~/dotfiles/shell/.functions && dfs'` (self-contained; no TTY or `.zshrc` needed).

</important>

<important if="you are modifying CLAUDE.md, AGENTS.md, README.md, or project structure">

## Maintaining Docs

- **Sync root docs**: keep root `CLAUDE.md` and root `AGENTS.md` aligned — same facts and section order, diverging only in the H1, the project-level pointer, and Claude's `<important>` wrappers.
- **Sync global instructions**: edit one of the four global instruction files, copy the body to the other three (keeping each H1), commit together — see Project Structure above for the rule and `agents/eval/` for the parity check.
- **Update docs**: after structural changes (adding, removing, or renaming files/directories, skills, or configs), check whether `README.md`, `CLAUDE.md`, or `AGENTS.md` reference the affected paths and update them.

</important>

## Not Backed Up

OAuth tokens, command history, local settings, the host-local active theme (`~/.local/state/dotfiles-theme/`, so each machine keeps its own light/dark), per-project data, and cache files. API keys live in `~/.zshenv.local` (not in the repo, so `dfs` never carries them) — after adding a new `export *_API_KEY=` or `*_PLAN_KEY=` locally, run `synckeys` (a `shell/.functions` helper, not a `dotfiles.sh` subcommand) — dry-run first, then `synckeys apply` — to propagate it to the other machines.
