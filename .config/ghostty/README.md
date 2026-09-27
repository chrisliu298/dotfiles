# Ghostty Config

Personal terminal emulator configuration for macOS, compatible with both [Ghostty](https://ghostty.org/) and [cmux](https://github.com/manaflow-ai/cmux). I personally recommend cmux for its rich built-in multiplexing features.

For the full list of configuration options, see the [Ghostty config reference](https://ghostty.org/docs/config/reference).

## Setup

Run the dotfiles installer from the repo root:

```bash
./dotfiles.sh
```

It symlinks this directory to `~/.config/ghostty`, including `config` and `themes/`.

`theme light` and `theme dark` select the custom `OpenAI Light` and `OpenAI Dark`
Ghostty themes. Their neutral surfaces follow the [OpenAI site](https://openai.com/)
and [developer docs](https://developers.openai.com/api/docs); ANSI accents are
adapted for terminal readability. These are personal themes, not official OpenAI
assets. Starship, tmux, btop, Neovim, Codex TUI, and Claude Code use matching
light/dark palettes; fastfetch follows Ghostty's ANSI colors.

Or symlink this config directory directly:

```bash
ln -sfn "$(pwd)/.config/ghostty" ~/.config/ghostty
```
