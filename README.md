# dotfiles

Personal dotfiles and AI agent configurations for macOS with zsh. Managed with a single `dotfiles.sh` script.

## 1. Installation

**One command sets up everything: submodules, symlinks, and extensions.**

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

## 2. Structure

**Shell config, app configs, and AI agent extensions — all in one repo.**

```text
dotfiles/
├── dotfiles.sh              # Single entrypoint: submodules + symlinks + extensions
├── shell/                   # Zsh config (Zinit, Powerlevel10k, fzf)
├── .config/                 # App configs (Neovim, tmux, btop)
└── agents/                  # AI agent configurations
    ├── claude/              # Claude Code config (CLAUDE.md, settings, hooks)
    ├── codex/               # Codex config (AGENTS.md)
    └── extensions/          # Local AI agent extensions (symlinked directly)
```

| Directory | Contents | Details |
|-----------|----------|---------|
| [`shell/`](shell/README.md) | Zsh config, plugins, aliases, functions | Zinit, Powerlevel10k, modern Unix tools |
| [`.config/`](.config/README.md) | Application configs | Neovim, tmux, btop |
| [`agents/`](agents/) | AI agent configurations | Claude Code, Codex, and local extensions |

## 3. Symlinks

**All managed by `dotfiles.sh`.**

| Symlink Target | Source |
|----------------|--------|
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
| `~/.claude/settings.json` | `agents/claude/settings.json` |
| `~/.claude/keybindings.json` | `agents/claude/keybindings.json` |
| `~/.claude/hooks` | `agents/claude/hooks` |
| `~/.claude/statusline-command.sh` | `agents/claude/statusline-command.sh` |
| `~/.codex/AGENTS.md` | `agents/codex/AGENTS.md` |

Skills are symlinked directly into `~/.claude/skills/` and `~/.codex/skills/` (see [`agents/extensions/`](agents/extensions/README.md)).

## 4. Extensions

**24 extensions across local and upstream sources, installed to Claude Code and Codex.**

- Local skills live in `agents/extensions/<name>/SKILL.md` — symlinked directly, single file works in both agents
- Upstream skills are declared in the `SKILLS` table in `dotfiles.sh` and cloned from GitHub
- Agent-specific skills (e.g., `pdf`, `relay`) use separate table entries with different sources per agent

| Action | Command |
|--------|---------|
| Install/update all | `./dotfiles.sh` |
| Add a new local skill | Create `agents/extensions/<name>/SKILL.md`, run `./dotfiles.sh` |
| Add upstream skill | Add `name\|owner/repo/subpath\|agents` to SKILLS table in `dotfiles.sh` |

## 5. What's Not Backed Up

**Security-sensitive and ephemeral files are excluded.**

- `auth.json`, `~/.claude.json` — OAuth tokens
- `history.jsonl` — command history (sensitive)
- `settings.local.json` — local settings overrides
- `projects/`, `sessions/` — per-project/session data
- `cache/`, `log/`, `debug/` — temporary files
