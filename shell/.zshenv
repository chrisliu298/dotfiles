# =============================================================================
# Environment Variables
# =============================================================================

# Platform detection
[[ "$OSTYPE" == darwin* ]] && export IS_MACOS=1

# Zsh options
export DISABLE_MAGIC_FUNCTIONS=true

# Terminal color support
export COLORTERM=truecolor

# Starship prompt config
# Host-local generated Starship config (active palette applied by `theme`;
# outside git). Generated from the tracked ~/.config/starship/starship.toml
# template by `theme`/dotfiles.sh; before the first seed Starship falls back to
# its built-in defaults, so run ./dotfiles.sh once after a fresh clone.
export STARSHIP_CONFIG="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles-theme/starship.toml"

# =============================================================================
# PATH
# =============================================================================
export GPT_PRO_HOST=local  # gpt-pro-relay engine runs on this Mac (was: macmini over SSH)
export PATH="$HOME/.claude/skills/relay/scripts:$HOME/.claude/skills/prism/scripts:$HOME/.codex/skills/gpt-pro-relay/scripts:$HOME/.cargo/bin:$HOME/.bun/bin:$HOME/.local/bin:$PATH"
if (( IS_MACOS )); then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    export PATH="/opt/homebrew/opt/curl/bin:$PATH"
    export PATH="/Applications/Visual Studio Code.app/Contents/Resources/app/bin:$PATH"
    export PATH="/Library/TeX/texbin:$PATH"
    export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:$PATH"
    export LDFLAGS="-L/opt/homebrew/opt/curl/lib"
    export CPPFLAGS="-I/opt/homebrew/opt/curl/include"
fi

# =============================================================================
# Editor
# =============================================================================
if (( IS_MACOS )); then
    # export EDITOR="open -We"
    export EDITOR="code --wait"
else
    export EDITOR="code --wait"
fi

# =============================================================================
# Claude Code
# =============================================================================
export ENABLE_PROMPT_CACHING_1H=1
# Telemetry left ENABLED so Claude Code can fetch the GrowthBook flag for /rc (remote-control).
# Actively `unset` (not merely leave the export commented): commenting out only stops *setting* the
# var — it does not clear a value already inherited from a long-lived parent (e.g. a tmux server
# started before telemetry was re-enabled, which then injects DISABLE_TELEMETRY=1 into every pane).
# unset clears that stale value in every new shell, so tmux panes get /rc too. To opt back out of
# telemetry, replace the line below with: export DISABLE_TELEMETRY=1
unset DISABLE_TELEMETRY

# Unset CLAUDECODE inside tmux so claude can start fresh
[[ -n "$TMUX" ]] && unset CLAUDECODE

# =============================================================================
# Local secrets (not version controlled)
# =============================================================================
[[ -f "$HOME/.zshenv.local" ]] && source "$HOME/.zshenv.local"
