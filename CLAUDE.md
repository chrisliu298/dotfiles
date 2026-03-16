# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Personal dotfiles and AI agent configurations for macOS with zsh. Managed with a single `dotfiles.sh` script that symlinks everything to the home directory.

## Structure

```
dotfiles/
├── dotfiles.sh            # Single canonical entrypoint: setup
├── shell/
│   ├── .zshrc              # Shell config (Zinit, Powerlevel10k, fzf)
│   ├── .zshenv             # Environment variables and PATH
│   ├── .aliases            # Command shortcuts (modern tools)
│   ├── .functions          # Shell utility functions
│   └── .p10k.zsh           # Powerlevel10k prompt config
├── .config/
│   ├── nvim/                # Neovim config (minimal, custom GitHub Dark theme)
│   ├── tmux/                # Tmux config (prefix: C-a)
│   └── btop/                # System monitor config and themes
└── agents/                  # AI agent configurations
    ├── claude/              # Claude Code (~/.claude/)
    │   ├── CLAUDE.md        # Global user instructions
    │   ├── settings.json    # Settings (symlinked)
    │   ├── keybindings.json # Key bindings (symlinked)
    │   ├── statusline-command.sh # Statusline script (symlinked)
    │   └── hooks/           # Session hooks
    ├── codex/               # Codex (~/.codex/)
    │   └── AGENTS.md        # Global user instructions (synced from agents/claude/CLAUDE.md)
    └── extensions/          # Local extensions (see agents/extensions/README.md)
        └── skills/          # Local skills (SKILL.md per skill)
```

**Note:** This file (project-level CLAUDE.md) is different from `agents/claude/CLAUDE.md` (global user instructions that apply to all projects).

## Setup

```bash
./dotfiles.sh # Initialize submodules, symlink files, and verify links
```

## Shell Load Order

1. `shell/.zshenv` (platform detection, environment, PATH)
2. `shell/.zshrc` (plugins, prompt, sources `shell/.aliases` and `shell/.functions`)

## Modern Unix Tools

Installed via Zinit from GitHub releases (macOS ARM).

- `fd` → `find`, `rg` → `grep`, `delta` → `diff`, `zoxide` → `z`

## Conventions

- **Platform detection**: `IS_MACOS` is set in `shell/.zshenv` and used for macOS-only code across all dotfiles
- **Safe rm**: The `rm()` function in `shell/.functions` uses `trash` instead of permanent deletion (macOS only)
- **Python**: Use `uv` for virtual environments (`sv`, `us`, `ua`, `upi` aliases)
- **Themes**: Ghostty (GitHub Dark) and btop (Grok Dark)

## Adding Extensions

Extensions are managed by the `SKILLS` table in `dotfiles.sh` using direct git-clone + symlink (no `npx skills`):

- **Local skills**: Add a `<name>/SKILL.md` directory under `agents/extensions/skills/`, run `./dotfiles.sh`
- **Upstream skills**: Add a `name|owner/repo/subpath|agents` entry to the `SKILLS` table in `dotfiles.sh`
- **Agent-specific skills**: Use separate table entries with different sources per agent (e.g., `pdf` has different sources for claude vs codex)
- **Install/update all**: Run `./dotfiles.sh` (clones/updates upstream repos, symlinks everything)

Each skill has a single SKILL.md that works in both Claude Code and Codex. Include Claude-specific frontmatter (`allowed-tools`, `user-invocable`) — Codex ignores unknown keys.

## Keeping Instructions Synced

`agents/claude/CLAUDE.md` and `agents/codex/AGENTS.md` contain the same working principles. When updating one, copy the content to the other.

## Maintaining Docs

After any structural change (adding, removing, or renaming files/directories, skills, or configs), check whether `README.md`, `CLAUDE.md`, or `AGENTS.md` reference the affected paths or content and update them if so.

## What's NOT Backed Up

OAuth tokens, command history, local settings, per-project data, and cache files are excluded for security.
