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

- **Shell**: `ez` (reload), `o` (open), `b` (btop), `theme [light|dark|toggle]` (terminal theme)
- **Tmux**: `t`, `ta`, `tl`, `tn`, `tk`, `to` (new/attach to `$PWD` name), `tka` (kill all)
- **Python/uv**: `sv` (source venv), `us` (sync), `ua` (add)
- **Claude Code**: `c` (auto-accept), `cc` (continue), `cr` (resume), `cpu` (/push), `cl`/`cm`/`ch`/`cx`/`cmx` (low/medium/high/xhigh/max effort)
- **Codex**: `x` (default=medium), `xn`/`xl`/`xm`/`xh`/`xx` (none/low/medium/high/xhigh reasoning), `xc` (resume --last)
- **Homebrew**: `bi`/`bu`/`bic` (install/uninstall/cask), `bupd`/`bupg` (update/upgrade)
- **Functions**: `dfs` (pull + install + sync remote), `theme [light|dark|toggle]` (Ghostty + btop + tmux), `synckeys` (propagate `~/.zshenv.local` API/plan keys to peers; dry-run by default, `synckeys apply` to write), `rename_device`

### Reasoning-effort tiers

Effort suffixes follow one convention — `n`=none, `l`=low, `m`=medium, `h`=high, `x`=xhigh, `mx`=max. Each model exposes only the tiers its endpoint supports; the bare alias is that model's sensible default.

| tier | suffix | Claude `c` | Codex `x` | GLM `glm` | Kimi `km` | DeepSeek `ds` | MiMo `mm` |
|------|:------:|:----------:|:---------:|:---------:|:----------:|:-------------:|:---------:|
| *bare (default)* | — | `c` (xhigh) | `x` (medium) | `glm` (max) | `km` (K2.7-Code) | `ds` (max) | `mm` (default) |
| none | `n` | — | `xn` | — | — | — | — |
| low | `l` | `cl` | `xl` | — | — | → high | — |
| medium | `m` | `cm` | `xm` | — | — | → high | — |
| high | `h` | `ch` | `xh` | — | — | `dsh` | — |
| xhigh | `x` | `cx` | `xx` | — | — | → max | — |
| max | `mx` | `cmx` | n/a | `glm` (bare) | — | `ds` (bare) | — |

`→` = the requested value collapses to that tier (DeepSeek maps low/medium → high, xhigh → max); MiMo's Anthropic endpoint surfaces no effort control. GLM-5.2 supports a graded `reasoning_effort` (max/xhigh/high/…/none) but the launcher pins **max** — the same level the relay/prism registry pins — so only bare `glm`=max is exposed. Kimi (`km`) runs on the Kimi-for-Coding subscription plan (`api.kimi.com/coding/`), where the thinking toggle picks the model; the launcher pins `CLAUDE_CODE_EFFORT_LEVEL=max` (thinking on → **K2.7-Code**; thinking off would route to K2.6), so only bare `km` is exposed. Continue/resume/headless suffixes (`*c`/`*r`/`*hl`) are uniform across all six. Bare `c` doesn't pin an effort — it inherits `effortLevel` from `agents/claude/settings.json` (adaptive thinking is disabled there), currently `xhigh`, so `c` ≡ `cx`.
