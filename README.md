# dotfiles

Personal dotfiles and AI agent configurations for macOS with zsh. Managed with a single `dotfiles.sh` script.

## Installation

```bash
git clone git@github.com:chrisliu298/dotfiles.git ~/dotfiles
cd ~/dotfiles
./dotfiles.sh
```

Syncs submodules, symlinks dotfiles and agent configs to `~`, installs AI agent extensions, registers MCP servers, and verifies all links.

## Structure

```text
dotfiles/
├── dotfiles.sh              # Single entrypoint: submodules + symlinks + extensions
├── shell/                   # Zsh config (Zinit, Starship, fzf)
├── .config/                 # App configs (Neovim, tmux, btop)
└── agents/                  # AI agent configurations
    ├── claude/              # Claude Code config (CLAUDE.md, settings, hooks)
    ├── codex/               # Codex config (AGENTS.md)
    └── extensions/          # Local AI agent extensions
```

See [`shell/`](shell/README.md), [`.config/`](.config/README.md), and [`agents/extensions/`](agents/extensions/README.md) for details.

## Extensions

32 extensions across local and upstream sources. See [`agents/extensions/README.md`](agents/extensions/README.md) for full catalog. 4 additional Obsidian-specific skills live in the vault's `_claude/skills/`.

| Action | Command |
|--------|---------|
| Install/update all | `./dotfiles.sh` |
| List manual skills | `./dotfiles.sh skills` |
| Enable a manual skill | `./dotfiles.sh enable <name>` |
| Disable a manual skill | `./dotfiles.sh disable <name>` |
| Sync skills to published repos | `./dotfiles.sh publish` |
| Add a local skill | Create `agents/extensions/skills/<name>/SKILL.md`, run `./dotfiles.sh` |
| Add an upstream skill | Add `name\|owner/repo/subpath\|agents` to `SKILLS` table in `dotfiles.sh` |
