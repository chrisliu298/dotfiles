# Repository Guidelines

## Project Structure & Module Organization
This repository contains personal dotfiles and AI agent configurations for macOS with zsh.

- `shell/.aliases`, `shell/.functions`, `shell/.zshrc`, `shell/.zshenv`, `shell/.p10k.zsh`: Shell dotfiles
- `ssh/config`: SSH host aliases (symlinked on macOS only)
- `.config/`: Application configs kept in-repo (`tmux`, `btop`, `nvim`)
- `~/.config/ghostty`: Ghostty config installed from the external `chrisliu298/ghostty-config` repo via `dotfiles.sh`
- `skills/`: Local skills (one SKILL.md per skill, symlinked via `dotfiles.sh`)
- `claude/`: Claude Code config (`CLAUDE.md`, `settings.json`, `hooks/`)
- `codex/`: Codex config (`AGENTS.md`)
- `dotfiles.sh`: single canonical entrypoint for dotfiles, external repo sync, agent configs, and skill installation
- `README.md` and `CLAUDE.md`: top-level usage and maintenance docs

## Build, Test, and Development Commands
- `./dotfiles.sh`: initialize submodules, sync external repos, apply links, install skills, and run verification.
- `git status --short`: confirm only intended files changed before commit.
- `rg --files`: quickly inspect tracked structure when adding/updating skills.
- `uv venv && source .venv/bin/activate`: initialize local Python environment for script-based skills.
- `./dotfiles.sh`: also handles upstream skill updates (clones/updates repos, symlinks everything).

## Coding Style & Naming Conventions
- Use Markdown for guides and skill instructions, with short sections and actionable bullets.
- Shell scripts should stay Bash-first, with clear helper functions and defensive flags (`set -e`).
- Use lowercase kebab-case for skill directories (example: `note-gen`, `atomic-push`).
- Each skill has a single SKILL.md that works in both Claude Code and Codex.
- Follow `.gitignore`; do not commit secrets, caches, or local environment artifacts.

## Testing Guidelines
- Primary validation is functional: run `./dotfiles.sh` and verify symlinks resolve correctly, including the external Ghostty repo link.
- For skills with Python scripts, use `uv run pytest` on the relevant test file.
- If you add scripts, include at least one runnable verification path (test or documented command).

## Commit & Pull Request Guidelines
- Match existing history style: imperative, concise subject lines (examples: `Add ...`, `Update ...`, `Remove ...`, `Refactor ...`).
- Keep commits atomic by logical change (docs vs scripts vs skill content).
- PRs should include: purpose, changed paths, verification commands run, and any migration/symlink impact.
- Link related issues/tasks when available; include screenshots only for UI-facing documentation changes.

## Maintaining Docs
- After any structural change (adding, removing, or renaming files/directories, skills, or configs), check whether `README.md`, `CLAUDE.md`, or `AGENTS.md` reference the affected paths or content and update them if so.
