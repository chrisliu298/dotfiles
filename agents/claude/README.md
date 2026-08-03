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
invisible on the `#fafafa` canvas at 1.09:1. Selecting any custom theme pins the light/dark base,
so `settings.json` pins `theme` to `custom:dotfiles` and `shell/theme-apply` copies
`themes/<mode>.json` over `~/.claude/themes/dotfiles.json`. Claude watches that directory, so
running sessions repaint without a restart. Same mechanism as pi.

Both files set `base` (`light`/`dark`) and override exactly two tokens: the user-message band
and its hover. Everything else stays on Anthropic's palette for that base — the repo's own
colors live in the terminal, and Claude paints straight onto the Ghostty canvas.

| mode | band | hover | canvas | band vs canvas | hover vs canvas | stock band | body text on band |
|------|------|-------|--------|----------------|-----------------|------------|-------------------|
| light | `#ebedef` (`neutral.muted`) | `#d0d7de` (`border.default`) | `#fafafa` | 1.12:1 | 1.39:1 | 1.09:1 | 17.89:1 |
| dark | `#21262d` (`border.muted`) | `#30363d` (`border.default`) | `#0d1117` | 1.25:1 | 1.57:1 | 1.59:1 | 15.21:1 |

The stock dark band sets the ceiling at 1.59:1 from its canvas; the stock light band misses
entirely at 1.09:1 — the bug this fixes. Both bands sit one stop *inside* that ceiling: legible as
a distinct block without reading as a slab, tuned by eye from there. Light stays below dark's
number on purpose — a dark band on a light canvas reads heavier than a light band on a dark one at
equal contrast ratio, so matching it overshoots.

Hover moves *away* from the canvas in both modes (light darkens, dark lightens), so hovering always
adds weight.

Neither mode shares a hex with the tmux status bar (`#eaeef2` light, `#010409` dark) — they match in
*rule* instead: every band on screen sits one stop off its own canvas. The tmux bar is chrome anchored
below the canvas; a message band sits above it in dark and, on a canvas this light, just off it in
light. `neutral.muted` is Primer's background token for exactly this — a surface that reads as a
distinct block without claiming elevation.

Both light values are derived rather than picked: `#ebedef` is `neutral.muted` (`rgba(175,184,193,0.2)`)
flattened onto the `#fafafa` canvas, the same flatten rule the Ghostty themes use for
`selection-background`. Recompute it if the canvas ever changes. The hover pair mirrors dark exactly —
`border.muted` band, `border.default` hover — except light's `border.muted` (`#d8dee4`, 1.30:1) lands
heavier than the 1.12:1 this band is tuned to, so light takes `neutral.muted` for the band and keeps
`border.default` for the hover.

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
