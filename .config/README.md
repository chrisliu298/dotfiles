# Application Configs

Terminal application configs.

## Apps

| App | Config | Notes |
|-----|--------|-------|
| Ghostty | [chrisliu298/ghostty-config](https://github.com/chrisliu298/ghostty-config) (separate repo) | Berkeley Mono font, GitHub Dark theme |
| Neovim | `nvim/init.lua` | Minimal, no plugins |
| tmux | `tmux/tmux.conf` | Prefix: `C-a`, vi mode, mouse enabled |
| btop | `btop/btop.conf` | Grok Dark theme, braille graphs |

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
