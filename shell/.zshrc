# =============================================================================
# Starship Prompt (config: ~/.config/starship/starship.toml)
# =============================================================================

# =============================================================================
# Source Local Config Files
# =============================================================================
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
# Loaded before the first prompt: compinit below needs zsh-completions in fpath
zinit light zsh-users/zsh-completions

# fzf - fuzzy finder
export FZF_DEFAULT_OPTS="--exact"
zinit ice from"gh-r" as"program"
zinit light junegunn/fzf

# Turbo: loaded right after the first prompt, in this order (syntax highlighting
# last, since it wraps every widget defined before it).
# OMZP::git is disabled — git aliases unused.
zinit wait lucid for \
    OMZP::sudo \
    OMZP::command-not-found \
    https://raw.githubusercontent.com/junegunn/fzf/master/shell/key-bindings.zsh \
    atload"_zsh_autosuggest_start" zsh-users/zsh-autosuggestions \
    zsh-users/zsh-syntax-highlighting

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
typeset -U fpath
# Full compinit (compaudit + new-function scan) at most once a day; otherwise trust
# the dump. Run `compinit` by hand to pick up a new completion sooner.
autoload -Uz compinit
() {
    local dump=${ZDOTDIR:-$HOME}/.zcompdump
    local -a stale=($dump(N.mh+24))
    if (( $#stale )); then
        compinit && touch $dump
    else
        compinit -C
    fi
}
zinit cdreplay -q

zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'm:{a-zA-Z}={A-Za-z} l:|=* r:|=*'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' menu no

# OpenClaw Completion (source from file — openclaw update can overwrite this safely)
if (( IS_MACOS )) && [[ "$HOST" == "macmini" ]] && [[ -f ~/.openclaw/completions/openclaw.zsh ]]; then
    source ~/.openclaw/completions/openclaw.zsh
fi

# interview-prep make completion
_interview_prep_completion="$HOME/Developer/GitHub/interview-prep/completions/_interview_prep_make"
[[ -f "$_interview_prep_completion" ]] && source "$_interview_prep_completion"
unset _interview_prep_completion

# tmux-persist: subcommands, then live tmux sessions for `restart` (also via the tpr alias)
_tmux-persist() {
    local -a sessions
    if (( CURRENT == 2 )); then
        compadd save restore restart stale
    elif [[ $words[2] == restart ]]; then
        sessions=(${(f)"$(tmux list-sessions -F '#S' 2>/dev/null)"})
        sessions=(${sessions:|words})  # each session once
        compadd -a sessions
    fi
}
compdef _tmux-persist tmux-persist

# User-operated presence commands (including the prs alias).
_presence() {
    (( CURRENT == 2 )) && compadd show away back questions clear
}
compdef _presence presence prs

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
setopt interactive_comments  # allow # comments at the interactive prompt (e.g. pasted snippets)

# Local binaries
[[ -f "$HOME/.local/bin/env" ]] && source "$HOME/.local/bin/env"

# Source `TOOL init zsh` from a cache keyed by the binary's mtime, so an upgrade
# regenerates it and a normal startup spawns nothing.
_source_init_cached() {
    local bin=$commands[$1]
    [[ -n $bin ]] || return 0
    local -a mtime
    zmodload -F zsh/stat b:zstat && zstat -A mtime +mtime $bin
    local dir=${XDG_CACHE_HOME:-$HOME/.cache}/zsh-init
    local cache=$dir/$1-$mtime.zsh
    if [[ ! -s $cache ]]; then
        mkdir -p $dir && rm -f $dir/$1-*.zsh(N) && $bin init zsh >| $cache
    fi
    source $cache
}

# Zoxide (smart cd)
_source_init_cached zoxide

# Reset stuck mouse tracking before every prompt (Ghostty + TUI apps / SSH disconnect)
autoload -Uz add-zsh-hook
add-zsh-hook precmd disable_mouse_tracking

# Starship prompt. The theme has no right_format, so drop RPROMPT rather than
# spawn a second starship per prompt to render nothing.
_source_init_cached starship
unset RPROMPT
unfunction _source_init_cached

# Fix prompt duplication in cmux (https://github.com/manaflow-ai/cmux/issues/1236)
if [[ -n "$CMUX_SHELL_INTEGRATION" ]]; then
    precmd_functions=(${precmd_functions:#_ghostty_precmd})
    preexec_functions=(${preexec_functions:#_ghostty_preexec})
    # Redraw prompt on resize to prevent prompt garbling from sidebar toggle
    function TRAPWINCH() {
        [[ -o zle ]] && zle && zle reset-prompt
    }
fi
