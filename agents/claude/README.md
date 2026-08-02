# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`.

| Path | Installed as | Notes |
|------|--------------|-------|
| `CLAUDE.md` | symlink | One of the four canonical global instruction files — see root `CLAUDE.md`. |
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **copied** by `dotfiles.sh` | `~/` is expanded to an absolute path on copy, which Claude Code requires. Includes the `"theme": "custom:dotfiles"` pin. |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |
| `themes/{light,dark}.json` | **copied** by `theme-apply` | The custom theme `dotfiles`; the mode decides which definition that name resolves to. |

Skills are not here — they are symlinked into `~/.claude/skills/` from `agents/skills/` by the
`SKILLS` table in `dotfiles.sh`.

## Themes

Claude Code has a `theme: auto` that follows the terminal, but its built-in palettes are
Anthropic's, not this repo's — and its light palette paints user messages `rgb(240,240,240)`,
invisible on Catppuccin Latte's `#eff1f5`. Selecting any custom theme pins the light/dark base,
so `settings.json` pins `theme` to `custom:dotfiles` and `shell/theme-apply` copies
`themes/<mode>.json` over `~/.claude/themes/dotfiles.json`. Claude watches that directory, so
running sessions repaint without a restart. Same mechanism as pi.

Both files set `base` (`light`/`dark`) and override exactly two tokens: the user-message band
and its hover. Everything else stays on Anthropic's palette for that base — the repo's own
colors live in the terminal, and Claude paints straight onto the Ghostty canvas.

| mode | band | hover | canvas | band vs canvas | stock band | body text on band |
|------|------|-------|--------|----------------|------------|-------------------|
| light | `#ccd0da` (Latte `surface1`) | `#dce0e8` (`crust`) | `#eff1f5` | 1.37:1 | 1.01:1 | 13.60:1 |
| dark | `#30363d` (GitHub Dark) | `#3d444d` | `#0d1117` | 1.55:1 | 1.59:1 | 12.20:1 |

The stock dark band reads well at 1.59:1 from its canvas, which set the target; the stock light
band misses it entirely at 1.01:1 — the bug this fixes — and tmux's elevated `#161b22` would have
landed at 1.08:1 and disappeared the same way. Light deliberately sits one stop *below* the shared
target: a dark band on a light canvas reads heavier than a light band on a dark one at equal
contrast ratio, so matching the number overshoots. Tuned by eye from there.

Dark overrides the pair rather than inheriting because stock dark is a neutral `rgb(55,55,55)`,
slightly warm against GitHub Dark's blue-gray canvas.

These two are true background fills — most of Claude's tokens are foregrounds despite names that
suggest otherwise (`subtle` has 35 `color:` uses and zero backgrounds; `background` is the
background-*task* accent). A fill value on a foreground token makes the element vanish, so verify
any addition with the built-in editor rather than by inference: `/theme` → select `dotfiles` →
set a token to magenta and look, then Esc to discard.

> The editor writes in place if you confirm, which reformats the file and drops any override
> equal to its base default. Recovery is `theme light` / `theme dark`.

### After a Claude Code upgrade

Overrides naming a token that no longer exists are **dropped silently** — no error, no log, not
even under `--debug` — and a `base` Claude doesn't recognize falls back to `dark`. Both are
invisible until you notice a stray color weeks later, so `./dotfiles.sh lint` asserts against the
installed binary (`lint_claude_theme`): it reads the palette key set out of the Claude Code
executable and fails on any token name it doesn't contain, any unrecognized `base`, and any value
Claude's validator would reject. It runs at the end of every full `./dotfiles.sh`, so `dfs`
exercises it on each host, and it downgrades to a skip where Claude Code isn't installed.

That makes an upgrade that renames a token loud instead of silent. Verified against 2.1.220.

## Status line

`statusline-command.sh` is a separate mechanism from the theme and the two never overlap: it
owns its entire output string, and its escape codes go straight to the terminal, so no theme
token can recolor it. It uses ANSI *named* colors only (`\033[36m` etc.), which the Ghostty
palette remaps per mode — so it tracks light/dark for free, with no entry in `theme-apply`.
