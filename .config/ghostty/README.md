# Ghostty Config

Personal terminal emulator configuration for macOS, compatible with both [Ghostty](https://ghostty.org/) and [cmux](https://github.com/manaflow-ai/cmux). I personally recommend cmux for its rich built-in multiplexing features.

For the full list of configuration options, see the [Ghostty config reference](https://ghostty.org/docs/config/reference).

## Setup

Clone this repo and symlink to the config directory:

```bash
git clone https://github.com/chrisliu298/ghostty-config.git
ln -sf "$(pwd)/ghostty-config/config" ~/.config/ghostty/config
ln -sf "$(pwd)/ghostty-config/themes" ~/.config/ghostty/themes
```

Or copy the files directly:

```bash
cp config ~/.config/ghostty/config
cp -r themes ~/.config/ghostty/themes/
```
