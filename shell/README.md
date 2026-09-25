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

- **Shell**: `ez` (reload), `o` (open), `b` (btop), `theme [light|dark|toggle|status]` / `theme --all <mode>` (terminal + prompt + macOS theme)
- **Tmux**: `t`, `ta`, `tl`, `tn`, `tk`, `to` (new/attach to `$PWD` name), `tka` (kill all)
- **Python/uv**: `sv` (source venv), `us` (sync), `ua` (add)
- **Claude Code**: `c` (auto-accept), `cc` (continue), `cr` (resume), `cpu` (/push), `cl`/`cm`/`ch`/`cx`/`cmx` (low/medium/high/xhigh/max effort), `scout-papers-scholar-inbox-all` (sequentially scout five awesome lists with Opus at high effort, showing final messages only)
- **Codex**: `x` (gpt-6-sol, default=medium), `xn`/`xl`/`xm`/`xh`/`xx`/`xmx` (none/low/medium/high/xhigh/max reasoning), `xc` (resume --last), `cal`/`cas`/`caw`/`caa` (codex-auth list/status/switch/login)
- **Homebrew**: `bi`/`bu`/`bic` (install/uninstall/cask), `bupd`/`bupg` (update/upgrade)
- **Functions**: `dfs` (pull + install + sync remote), `theme [light|dark|toggle|status]` / `theme --all <mode>` (Ghostty + Starship + btop + tmux + macOS; `--all` also applies to macmini and l40s), `synckeys` (propagate `~/.zshenv.local` API/plan keys to peers; dry-run by default, `synckeys apply` to write), `rename_device`

### Reasoning-effort tiers

Effort suffixes follow one convention — `n`=none, `l`=low, `m`=medium, `h`=high, `x`=xhigh, `mx`=max. Each model exposes only the tiers its endpoint supports; the bare alias is that model's sensible default.

| tier | suffix | Claude `c` | Codex `x` |
|------|:------:|:----------:|:---------:|
| *bare (default)* | — | `c` (high) | `x` (medium) |
| none | `n` | — | `xn` |
| low | `l` | `cl` | `xl` |
| medium | `m` | `cm` | `xm` |
| high | `h` | `ch` | `xh` |
| xhigh | `x` | `cx` | `xx` |
| max | `mx` | `cmx` | `xmx` |

Continue/resume/headless suffixes (`*c`/`*r`/`*hl`) are uniform across the Claude/Codex aliases. Bare `c` doesn't pin an effort — it inherits `effortLevel` from `agents/claude/settings.json` (with adaptive thinking on), currently `high`, so `c` ≡ `ch`.
