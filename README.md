# dotfiles

Personal dotfiles and AI agent configurations for macOS with zsh. Managed with a single `dotfiles.sh` script.

## 1. Installation

**One command sets up everything: submodules, symlinks, and skills.**

```bash
git clone git@github.com:chrisliu298/dotfiles.git ~/dotfiles
cd ~/dotfiles
./dotfiles.sh
```

- Syncs and initializes git submodules
- Symlinks dotfiles and agent configs to `~`
- Installs 24 AI agent skills to `~/.claude/skills/` and `~/.codex/skills/`
- Registers MCP servers (Playwright browser automation, Codex cross-model review)
- Verifies all required symlinks

## 2. Structure

**Shell config, app configs, and AI agent skills — all in one repo.**

```text
dotfiles/
├── dotfiles.sh              # Single entrypoint: submodules + symlinks + skills
├── shell/                   # Zsh config (Zinit, Powerlevel10k, fzf)
├── .config/                 # App configs (Neovim, tmux, btop)
├── skills/                  # Local AI agent skills (symlinked directly)
├── claude/                  # Claude Code config (CLAUDE.md, settings, hooks)
├── codex/                   # Codex config (AGENTS.md)
└── ssh/                     # SSH host aliases (no keys stored)
```

| Directory | Contents | Details |
|-----------|----------|---------|
| [`shell/`](shell/README.md) | Zsh config, plugins, aliases, functions | Zinit, Powerlevel10k, modern Unix tools |
| [`.config/`](.config/README.md) | Application configs | Neovim, tmux, btop |
| [`skills/`](skills/README.md) | AI agent skills (24 total) | Local + upstream, managed via `dotfiles.sh` SKILLS table |
| `claude/` | Claude Code config | `CLAUDE.md`, `settings.json`, `keybindings.json`, hooks, statusline |
| `codex/` | Codex config | `AGENTS.md` (synced from `claude/CLAUDE.md`) |
| `ssh/` | SSH host aliases | No keys stored |

## 3. Symlinks

**All managed by `dotfiles.sh`. SSH config is macOS-only.**

| Symlink Target | Source |
|----------------|--------|
| `~/.zshrc` | `shell/.zshrc` |
| `~/.zshenv` | `shell/.zshenv` |
| `~/.aliases` | `shell/.aliases` |
| `~/.functions` | `shell/.functions` |
| `~/.p10k.zsh` | `shell/.p10k.zsh` |
| `~/.ssh/config` | `ssh/config` |
| `~/.config/btop` | `.config/btop` |
| `~/.config/ghostty` | [chrisliu298/ghostty-config](https://github.com/chrisliu298/ghostty-config) (cloned) |
| `~/.config/nvim` | `.config/nvim` |
| `~/.config/tmux` | `.config/tmux` |
| `~/.claude/CLAUDE.md` | `claude/CLAUDE.md` |
| `~/.claude/settings.json` | `claude/settings.json` |
| `~/.claude/keybindings.json` | `claude/keybindings.json` |
| `~/.claude/hooks` | `claude/hooks` |
| `~/.claude/statusline-command.sh` | `claude/statusline-command.sh` |
| `~/.codex/AGENTS.md` | `codex/AGENTS.md` |

Skills are symlinked directly into `~/.claude/skills/` and `~/.codex/skills/` (see [`skills/`](skills/README.md)).

## 4. Skills

**24 skills across local and upstream sources, installed to Claude Code and Codex.**

- Local skills live in `skills/<name>/SKILL.md` — symlinked directly, single file works in both agents
- Upstream skills are declared in the `SKILLS` table in `dotfiles.sh` and cloned from GitHub
- Agent-specific skills (e.g., `pdf`, `relay`) use separate table entries with different sources per agent

| Action | Command |
|--------|---------|
| Install/update all | `./dotfiles.sh` |
| Add a new local skill | Create `skills/<name>/SKILL.md`, run `./dotfiles.sh` |
| Add upstream skill | Add `name\|owner/repo/subpath\|agents` to SKILLS table in `dotfiles.sh` |

## 5. What's Not Backed Up

**Security-sensitive and ephemeral files are excluded.**

- `auth.json`, `~/.claude.json` — OAuth tokens
- `history.jsonl` — command history (sensitive)
- `settings.local.json` — local settings overrides
- `projects/`, `sessions/` — per-project/session data
- `cache/`, `log/`, `debug/` — temporary files
