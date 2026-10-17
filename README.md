# dotfiles

Personal dotfiles and AI agent configurations for macOS with zsh. Managed with a single `dotfiles.sh` script.

## Installation

```bash
git clone git@github.com:chrisliu298/dotfiles.git ~/dotfiles
cd ~/dotfiles
./dotfiles.sh
```

Syncs submodules, symlinks dotfiles and agent configs to `~`, installs AI agent extensions, registers MCP servers, installs tmux plugins via TPM, and verifies all links.

## Structure

```text
dotfiles/
├── dotfiles.sh              # Single entrypoint: submodules + symlinks + extensions
├── shell/                   # Zsh config (Zinit, Starship, fzf)
├── .config/                 # App configs (Neovim, tmux, btop)
└── agents/                  # AI agent configurations
    ├── AGENTS.md            # Global instructions, linked as ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md
    ├── claude/              # Claude Code config (settings, keybindings, statusline, themes)
    ├── codex/               # Codex config (themes)
    └── skills/              # Repo-owned skill sources + authoring references
```

See [`shell/`](shell/README.md), [`.config/`](.config/README.md), and [`agents/skills/`](agents/skills/README.md) for details.

## Extensions

19 extensions across local and upstream sources. See [`agents/skills/README.md`](agents/skills/README.md) for full catalog. 4 additional Obsidian-specific skills live in the vault's `_claude/skills/`.

| Action | Command |
|--------|---------|
| Install/update all | `./dotfiles.sh` |
| Add a local skill | Create `agents/skills/<name>/SKILL.md`, run `./dotfiles.sh` |
| Add an upstream skill | Add `name\|owner/repo/subpath\|agents` to `SKILLS` table in `dotfiles.sh` |
