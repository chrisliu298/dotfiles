# Shell

Zsh with Zinit plugin manager and Powerlevel10k prompt.

## Files

| File | Purpose |
|------|---------|
| `.zshenv` | Platform detection (`IS_MACOS`), environment variables, PATH |
| `.zshrc` | Plugin manager, completions, keybindings, history |
| `.aliases` | Command shortcuts |
| `.functions` | Shell utility functions |
| `.p10k.zsh` | Powerlevel10k prompt configuration |

Load order: `.zshenv` (sets `IS_MACOS`) → `.zshrc` (sources `.aliases` and `.functions`).

## Modern Unix Tools

Installed via Zinit from GitHub releases (macOS ARM).

| Tool | Command |
|------|---------|
| [fd](https://github.com/sharkdp/fd) | `fd` |
| [ripgrep](https://github.com/BurntSushi/ripgrep) | `rg` |
| [zoxide](https://github.com/ajeetdsouza/zoxide) | `z` |
| [delta](https://github.com/dandavison/delta) | `delta` |

## Zsh Plugins

Managed by Zinit.

- `zsh-syntax-highlighting` — command syntax coloring
- `zsh-completions` — additional completions
- `zsh-autosuggestions` — fish-like suggestions
- `fzf` + `fzf-tab` — fuzzy finder with tab completion
- Oh My Zsh snippets: `git`, `sudo`, `command-not-found`

## Aliases

Shortcuts defined in `.aliases` and `.functions`.

```bash
# Shell
ez, o, b, fx           # reload zsh, open, btop, reset mouse tracking

# Tmux
t, ta, tl, tn, tk      # tmux, attach, list, new, kill
to, tka                 # new/attach to $PWD name, kill all

# Python/uv
sv, upi, uvp            # source venv, pip install, venv --python
us, ua                  # sync, add

# Claude Code (functions)
c, cc, cr               # claude (auto-accept), --continue, --resume
crc, cu                 # remote control, update
cap, cpu, chl           # /atomic-push, /push, headless prompt

# Codex (functions)
x, xl, xm, xh          # codex default, low/medium/high reasoning
xc, xr, xu, xhl        # resume --last, resume, update, headless prompt

# Homebrew (macOS)
bi, bu, bic, buz        # install, uninstall, cask install, uninstall --zap
bupd, bupg, buu         # update, upgrade, update+upgrade
bs, bl, bo              # search, list, outdated

# Git
glog                    # oneline graph log

# Tailscale (macOS)
tu, td, ts              # up, down, status
```

## Functions

Utilities defined in `.functions` (linked to `~/.functions`).

- `dfs` — pull, install locally, sync to remote machines
- `rm()` — safe delete using `trash` instead of permanent removal (macOS only)
- `rename_device <name>` — set macOS hostname, local hostname, and computer name
