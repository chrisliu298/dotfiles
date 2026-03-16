# Shell

Zsh with Zinit plugin manager and Powerlevel10k prompt.

## Files

- `.zshenv` - Platform detection (`IS_MACOS`), environment variables, PATH
- `.zshrc` - Plugin manager, completions, keybindings, history
- `.aliases` - Command shortcuts
- `.functions` - Shell utility functions
- `.p10k.zsh` - Powerlevel10k prompt configuration

Load order: `.zshenv` (sets `IS_MACOS`) → `.zshrc` (sources `.aliases` and `.functions`)

## Modern Unix Tools

Installed via Zinit from GitHub releases (macOS ARM).

| Tool | Command | Aliases |
|------|---------|---------|
| [fd](https://github.com/sharkdp/fd) | `fd` | - |
| [ripgrep](https://github.com/BurntSushi/ripgrep) | `rg` | - |
| [zoxide](https://github.com/ajeetdsouza/zoxide) | `z` | - |
| [delta](https://github.com/dandavison/delta) | `delta` | - |

## Zsh Plugins

Managed by Zinit.

- `zsh-syntax-highlighting` - Command syntax coloring
- `zsh-completions` - Additional completions
- `zsh-autosuggestions` - Fish-like suggestions
- `fzf` + `fzf-tab` - Fuzzy finder with tab completion
- Oh My Zsh snippets: `git`, `sudo`, `command-not-found`

## Key Aliases

Shortcuts defined in `.aliases` and `.functions`.

```bash
# Shell
ez, o, b            # reload zsh, open, btop

# Python/uv
sv, upi, uvp        # source venv, pip install, venv --python
us, ua              # sync, add

# Claude Code (functions)
c, cc, cr           # claude (auto-accept), --continue, --resume
crc, cu, cap, ch    # remote control, update, /atomic-push, headless prompt
ct                   # claude-usage-tracker

# Codex (functions)
x, xs               # codex (gpt-5.4), spark variant
xc, xr              # resume --last, resume
xu, xh              # update, headless prompt

# Homebrew (macOS)
bi, bu, bic, buz    # install, uninstall, cask install, uninstall --zap
bupd, bupg, buu     # update, upgrade, update+upgrade
bs, bl, bo          # search, list, outdated

# Tailscale (macOS)
tu, td, ts          # up, down, status

# Quartz
nqs, nqb, nqu       # sync, build --serve, upload
```

## Key Functions

Utilities defined in `.functions` (linked to `~/.functions`).

- `rm()` - Safe delete using `trash` instead of permanent removal (macOS only)
- `rename_device <name>` - Set macOS hostname, local hostname, and computer name
