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
export STARSHIP_CONFIG="$HOME/.config/starship/starship.toml"

# Disable Claude Code auto-update (set at shell level so the updater sees it
# before any settings.json env block is applied)
export DISABLE_AUTOUPDATER=1

# =============================================================================
# PATH
# =============================================================================
export PATH="$HOME/.claude/skills/relay/scripts:$HOME/.cargo/bin:$HOME/.bun/bin:$HOME/.local/bin:$PATH"
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
# QMD
# =============================================================================
export QMD_EMBED_MODEL="hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf"

# Unset CLAUDECODE inside tmux so claude can start fresh
[[ -n "$TMUX" ]] && unset CLAUDECODE