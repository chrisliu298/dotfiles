# Ghostty Config

Personal terminal emulator configuration for macOS, compatible with both [Ghostty](https://ghostty.org/) and [cmux](https://github.com/manaflow-ai/cmux). I personally recommend cmux for its rich built-in multiplexing features.

For the full list of configuration options, see the [Ghostty config reference](https://ghostty.org/docs/config/reference).

## Setup

Run the dotfiles installer from the repo root:

```bash
./dotfiles.sh
```

It symlinks this directory to `~/.config/ghostty`, including `config`, `themes/`, and `shaders/`.

`shaders/focus-flash.glsl` briefly tints and borders a split in the theme's ANSI
blue when it gains focus, so switching splits is easy to follow.

`theme light` and `theme dark` select the custom `OpenAI Light` and `OpenAI Dark`
Ghostty themes. Their neutral surfaces follow the [OpenAI site](https://openai.com/)
and [developer docs](https://developers.openai.com/api/docs); ANSI accents are
adapted for terminal readability. These are personal themes, not official OpenAI
assets. Starship, tmux, btop, Neovim, Codex TUI, and Claude Code use matching
light/dark palettes; fastfetch follows Ghostty's ANSI colors.
The themes also remap the extended palette entries used by Claude Code's
green/red diff backgrounds so tmux matches the direct-terminal appearance.

Or symlink this config directory directly:

```bash
ln -sfn "$(pwd)/.config/ghostty" ~/.config/ghostty
```
