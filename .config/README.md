# Application Configs

Terminal application configs.

## Apps

| App | Config | Notes |
|-----|--------|-------|
| Ghostty | `ghostty/config` | Berkeley Mono font, OpenAI Light/Dark themes |
| Starship | `starship/starship.toml` | Prompt with OpenAI Light/Dark palettes |
| Neovim | `nvim/init.lua` | OpenAI Light/Dark colorschemes, selected from the host-local mode at startup |
| tmux | `tmux/tmux.conf` | Prefix: `C-a`, vi mode, mouse enabled, OpenAI Light/Dark themes |
| btop | `btop/btop.conf.template` | OpenAI Light/Dark themes, braille graphs |
| fastfetch | `fastfetch/config.jsonc` | ANSI colors follow the terminal theme |

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
