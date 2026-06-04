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

# =============================================================================
# PATH
# =============================================================================
export PATH="$HOME/.claude/skills/relay/scripts:$HOME/.claude/skills/prism/scripts:$HOME/.claude/skills/gpt-pro-relay/scripts:$HOME/.cargo/bin:$HOME/.bun/bin:$HOME/.local/bin:$PATH"
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
export DISABLE_TELEMETRY=1

# Unset CLAUDECODE inside tmux so claude can start fresh
[[ -n "$TMUX" ]] && unset CLAUDECODE

# =============================================================================
# Grok (xAI Grok Build CLI — used as a relay/prism dispatch target)
# =============================================================================
# Isolate grok from ALL Claude-compat config: it gets its own Codex-mirrored
# skills (~/.grok/skills) and working-principles file (~/.grok/AGENTS.md) via
# dotfiles.sh — not Claude's ~/.claude/{skills, CLAUDE.md, rules, .claude.json
# MCPs, settings.json hooks}. The relay grok transport sets this same suite
# explicitly too, for non-.zshenv shells. (Claude *plugin* hooks under
# ~/.claude/plugins are a separate mechanism, not gated by these.) Binary on
# PATH via ~/.local/bin. Highest-precedence compat overrides.
export GROK_CLAUDE_SKILLS_ENABLED=false
export GROK_CLAUDE_AGENTS_ENABLED=false
export GROK_CLAUDE_RULES_ENABLED=false
export GROK_CLAUDE_MCPS_ENABLED=false
export GROK_CLAUDE_HOOKS_ENABLED=false

# =============================================================================
# Local secrets (not version controlled)
# =============================================================================
[[ -f "$HOME/.zshenv.local" ]] && source "$HOME/.zshenv.local"
