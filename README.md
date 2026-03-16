# dotfiles

Personal dotfiles and AI agent configurations for macOS with zsh. Managed with a single `dotfiles.sh` script.

## Installation

```bash
git clone git@github.com:chrisliu298/dotfiles.git ~/dotfiles
cd ~/dotfiles
./dotfiles.sh
```

- Syncs and initializes git submodules
- Symlinks dotfiles and agent configs to `~`
- Installs 24 AI agent extensions to `~/.claude/skills/` and `~/.codex/skills/`
- Registers MCP servers (Playwright browser automation, Codex cross-model review)
- Verifies all required symlinks

## Structure

```text
dotfiles/
├── dotfiles.sh              # Single entrypoint: submodules + symlinks + extensions
├── shell/                   # Zsh config (Zinit, Powerlevel10k, fzf)
├── .config/                 # App configs (Neovim, tmux, btop)
└── agents/                  # AI agent configurations
    ├── claude/              # Claude Code config (CLAUDE.md, settings, hooks)
    ├── codex/               # Codex config (AGENTS.md)
    └── extensions/          # Local AI agent extensions
```

See [`shell/`](shell/README.md), [`.config/`](.config/README.md), and [`agents/extensions/`](agents/extensions/README.md) for details.

## Symlinks

All managed by `dotfiles.sh`.

| Target | Source |
|--------|--------|
| `~/.zshrc` | `shell/.zshrc` |
| `~/.zshenv` | `shell/.zshenv` |
| `~/.aliases` | `shell/.aliases` |
| `~/.functions` | `shell/.functions` |
| `~/.p10k.zsh` | `shell/.p10k.zsh` |
| `~/.config/btop` | `.config/btop` |
| `~/.config/ghostty` | [chrisliu298/ghostty-config](https://github.com/chrisliu298/ghostty-config) (cloned) |
| `~/.config/nvim` | `.config/nvim` |
| `~/.config/tmux` | `.config/tmux` |
| `~/.claude/CLAUDE.md` | `agents/claude/CLAUDE.md` |
| `~/.claude/settings.json` | `agents/claude/settings.json` (copied, `~` expanded) |
| `~/.claude/keybindings.json` | `agents/claude/keybindings.json` |
| `~/.claude/hooks` | `agents/claude/hooks` |
| `~/.claude/statusline-command.sh` | `agents/claude/statusline-command.sh` |
| `~/.codex/AGENTS.md` | `agents/codex/AGENTS.md` |

Skills are symlinked into `~/.claude/skills/` and `~/.codex/skills/` (see [`agents/extensions/`](agents/extensions/README.md)).

## Extensions

24 extensions across local and upstream sources. See [`agents/extensions/README.md`](agents/extensions/README.md) for full catalog.

| Action | Command |
|--------|---------|
| Install/update all | `./dotfiles.sh` |
| Add a local skill | Create `agents/extensions/skills/<name>/SKILL.md`, run `./dotfiles.sh` |
| Add an upstream skill | Add `name\|owner/repo/subpath\|agents` to `SKILLS` table in `dotfiles.sh` |

## Not Backed Up

- `auth.json`, `~/.claude.json` — OAuth tokens
- `history.jsonl` — command history
- `settings.local.json` — local settings overrides
- `projects/`, `sessions/` — per-project/session data
- `cache/`, `log/`, `debug/` — temporary files
