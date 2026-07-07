# Application Configs

Terminal application configs.

## Apps

| App | Config | Notes |
|-----|--------|-------|
| Ghostty | `ghostty/config` | Berkeley Mono font, GitHub Light/Dark themes |
| Neovim | `nvim/init.lua` | Minimal, no plugins |
| tmux | `tmux/tmux.conf` | Prefix: `C-a`, vi mode, mouse enabled, GitHub Light/Dark themes |
| btop | `btop/btop.conf` | GitHub Light/Dark themes, braille graphs |

## Tmux Keybindings

Prefix: `C-a` (not default `C-b`).

| Key | Action |
|-----|--------|
| `_` | Split vertical |
| `-` | Split horizontal |
| `h/j/k/l` | Switch panes (repeatable) |
| `r` | Reload config |
| `v` | Begin selection (copy mode) |
| `y` | Copy selection |
