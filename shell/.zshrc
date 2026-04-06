# =============================================================================
# Powerlevel10k Instant Prompt
# =============================================================================
# Must stay close to the top. Initialization code requiring console input
# (password prompts, [y/n] confirmations, etc.) must go above this block.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
    source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# =============================================================================
# Source Local Config Files
# =============================================================================
[[ -f ~/.zshenv ]] && source ~/.zshenv
[[ -f ~/.aliases ]] && source ~/.aliases
[[ -f ~/.functions ]] && source ~/.functions

# =============================================================================
# Zinit Plugin Manager
# =============================================================================
export ZINIT_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zinit/zinit.git"

if [[ ! -d "$ZINIT_HOME" ]]; then
    mkdir -p "$(dirname "$ZINIT_HOME")"
    git clone https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME"
fi

source "${ZINIT_HOME}/zinit.zsh"

# =============================================================================
# Theme & Plugins
# =============================================================================
# Powerlevel10k theme
zinit ice depth=1
zinit light romkatv/powerlevel10k

# Zsh plugins
zinit light zsh-users/zsh-syntax-highlighting
zinit light zsh-users/zsh-completions
zinit light zsh-users/zsh-autosuggestions

# Oh My Zsh snippets
zinit snippet OMZP::git
zinit snippet OMZP::sudo
zinit snippet OMZP::command-not-found

# fzf - fuzzy finder
export FZF_DEFAULT_OPTS="--exact"
zinit ice from"gh-r" as"program"
zinit light junegunn/fzf
zinit snippet https://raw.githubusercontent.com/junegunn/fzf/master/shell/key-bindings.zsh
zinit snippet https://raw.githubusercontent.com/junegunn/fzf/master/shell/completion.zsh
zinit light Aloxaf/fzf-tab

# Modern Unix tools (macOS ARM only - on Linux, install via package manager)
if (( IS_MACOS )); then
    zinit ice from"gh-r" as"program" bpick"*aarch64-apple-darwin.tar.gz" mv"fd*/fd -> fd"
    zinit light sharkdp/fd

    zinit ice from"gh-r" as"program" bpick"*aarch64-apple-darwin.tar.gz" mv"ripgrep*/rg -> rg"
    zinit light BurntSushi/ripgrep

    zinit ice from"gh-r" as"program" bpick"*aarch64-apple-darwin.tar.gz"
    zinit light ajeetdsouza/zoxide

    zinit ice from"gh-r" as"program" bpick"*aarch64-apple-darwin.tar.gz" mv"delta*/delta -> delta"
    zinit light dandavison/delta
fi

# =============================================================================
# Completions
# =============================================================================
autoload -Uz compinit && compinit
zinit cdreplay -q

zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'm:{a-zA-Z}={A-Za-z} l:|=* r:|=*'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' menu no

# OpenClaw Completion (source from file — openclaw update can overwrite this safely)
if (( IS_MACOS )) && [[ "$HOST" == "macmini" ]] && [[ -f ~/.openclaw/completions/openclaw.zsh ]]; then
    source ~/.openclaw/completions/openclaw.zsh
fi

# =============================================================================
# Keybindings
# =============================================================================
bindkey -e
bindkey '^p' history-search-backward
bindkey '^n' history-search-forward
bindkey '^[[A' history-beginning-search-backward
bindkey '^[w' kill-region
bindkey '^I' menu-complete
bindkey "$terminfo[kcbt]" reverse-menu-complete
bindkey '^[[H' beginning-of-line
bindkey '^[[F' end-of-line

# =============================================================================
# History
# =============================================================================
HISTSIZE=1000000000
HISTFILE=~/.zsh_history
SAVEHIST=$HISTSIZE
HISTDUP=erase

setopt EXTENDED_HISTORY
setopt appendhistory
setopt sharehistory
setopt hist_ignore_space
setopt hist_ignore_all_dups
setopt hist_save_no_dups
setopt hist_ignore_dups
setopt hist_find_no_dups

# =============================================================================
# Environment Setup
# =============================================================================
setopt auto_cd
setopt NO_BEEP

# Local binaries
[[ -f "$HOME/.local/bin/env" ]] && source "$HOME/.local/bin/env"

# Zoxide (smart cd)
(( $+commands[zoxide] )) && eval "$(zoxide init zsh)"

# Reset stuck mouse tracking before every prompt (Ghostty + TUI apps / SSH disconnect)
autoload -Uz add-zsh-hook
add-zsh-hook precmd disable_mouse_tracking

# Powerlevel10k configuration
[[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh

# Fix prompt duplication in cmux (https://github.com/manaflow-ai/cmux/issues/1236)
if [[ -n "$CMUX_SHELL_INTEGRATION" ]]; then
    precmd_functions=(${precmd_functions:#_ghostty_precmd})
    preexec_functions=(${preexec_functions:#_ghostty_preexec})
    # Redraw prompt on resize to prevent prompt garbling from sidebar toggle
    function TRAPWINCH() {
        [[ -o zle ]] && zle && zle reset-prompt
    }
fi
