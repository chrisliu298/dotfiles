# Shell

Zsh with Zinit plugin manager and Starship prompt.

## Files

| File | Purpose |
|------|---------|
| `.zshenv` | Platform detection (`IS_MACOS`), environment variables, PATH |
| `.zshrc` | Plugin manager, completions, keybindings, history |
| `.aliases` | Command shortcuts |
| `.functions` | Shell utility functions |

Load order: `.zshenv` → `.zshrc` (sources `.aliases` and `.functions`).

## Plugins (Zinit)

`zsh-syntax-highlighting`, `zsh-completions`, `zsh-autosuggestions`, `fzf` + `fzf-tab`, Oh My Zsh snippets (`git`, `sudo`, `command-not-found`). Modern Unix tools (`fd`, `rg`, `zoxide`, `delta`) installed via Zinit from GitHub releases.

## Key Aliases & Functions

See `.aliases` and `.functions` for the full list. Highlights:

- **Shell**: `ez` (reload), `o` (open), `b` (btop)
- **Tmux**: `t`, `ta`, `tl`, `tn`, `tk`, `to` (new/attach to `$PWD` name), `tka` (kill all)
- **Python/uv**: `sv` (source venv), `us` (sync), `ua` (add)
- **Claude Code**: `c` (auto-accept), `cc` (continue), `cr` (resume), `cpu` (/push), `cl`/`cm`/`ch`/`cx`/`cmx` (low/medium/high/xhigh/max effort)
- **Codex**: `x` (default=medium), `xn`/`xl`/`xm`/`xh`/`xx` (none/low/medium/high/xhigh reasoning), `xc` (resume --last)
- **Homebrew**: `bi`/`bu`/`bic` (install/uninstall/cask), `bupd`/`bupg` (update/upgrade)
- **Functions**: `dfs` (pull + install + sync remote), `rename_device`

### Reasoning-effort tiers

Effort suffixes follow one convention — `n`=none, `l`=low, `m`=medium, `h`=high, `x`=xhigh, `mx`=max. Each model exposes only the tiers its endpoint supports; the bare alias is that model's sensible default.

| tier | suffix | Claude `c` | Codex `x` | DeepSeek `ds` | MiMo `mm` |
|------|:------:|:----------:|:---------:|:-------------:|:---------:|
| *bare (default)* | — | `c` (xhigh) | `x` (medium) | `ds` (max) | `mm` (default) |
| none | `n` | — | `xn` | — | — |
| low | `l` | `cl` | `xl` | → high | — |
| medium | `m` | `cm` | `xm` | → high | — |
| high | `h` | `ch` | `xh` | `dsh` | — |
| xhigh | `x` | `cx` | `xx` | → max | — |
| max | `mx` | `cmx` | n/a | `ds` (bare) | — |

`→` = the requested value collapses to that tier (DeepSeek maps low/medium → high, xhigh → max); MiMo's Anthropic endpoint surfaces no effort control. Continue/resume/headless suffixes (`*c`/`*r`/`*hl`) are uniform across all four. Bare `c` doesn't pin an effort — it inherits `effortLevel` from `agents/claude/settings.json` (adaptive thinking is disabled there), currently `xhigh`, so `c` ≡ `cx`.
