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

Both files set `base` (`light`/`dark`) plus **56 of Claude's 72 color tokens**. The 14
`rainbow_*` and 2 `clawd_*` mascot tokens are left at Claude's defaults — decorative, and
already mode-independent.

### Design rules

1. **Same roles, different family.** Light speaks Catppuccin Latte, dark speaks GitHub Dark —
   the principle `starship.toml` states as *"Same semantic roles as github_dark, mapped onto
   the Latte color family"*. The two files differ only in which family expresses each role.
   Claude paints straight onto the Ghostty canvas (`#eff1f5` / `#0d1117`) — it has no surface
   of its own, which is why light follows Ghostty's Latte rather than tmux/btop's GitHub Light.
2. **3:1 floor for foreground accents**, the convention `.config/ghostty/themes/GitHub Light`
   sets. Latte mostly misses it on `#eff1f5` — yellow 2.31:1, pink 2.34:1, peach 2.64:1,
   sapphire 2.78:1, lavender 2.81:1 — so foreground roles take the same hue one stop darker
   (`#df8e1d` → `#c27b19`, `#ea76cb` → `#e450bd`, `#fe640b` → `#f15901`, `#209fb5` → `#1f98ae`,
   `#7287fd` → `#6b81fd`). Fills and borders keep the true Latte values.
3. **Amber is mode-split.** The repo accent `#ffb000` measures 10.33:1 on GitHub Dark but
   1.62:1 on Latte, so dark uses the amber and light uses the `#a37100` stop (3.78:1) — the
   same split `.config/tmux/themes/github_light.conf` documents. It carries `fastMode` and the
   rate-limit bar.
4. **Fills are calibrated to separation, not copied stops.** The stock dark band that reads
   well sits at 1.59:1 from its canvas, which set the target: `#30363d` (1.55:1) in dark,
   hover one step lighter in both modes. Borrowing tmux's elevated `#161b22` would have landed
   at 1.08:1 and disappeared again — the mistake the stock light palette makes at 1.01:1.
   Light deliberately sits one stop *below* the shared target at `#ccd0da` (1.37:1): a dark
   band on a light canvas reads heavier than a light band on a dark one at equal contrast
   ratio, so matching the number overshoots. Tuned by eye from there.

The four diff *line* fills are alpha-composited from the mode's own green/red over its canvas —
lines at 22%/20%, dimmed at 10%/9% — so every value is reproducible rather than hand-picked.
The two `*Word` tokens are not fills and take the saturated palette green/red instead; see
below. `selectionBg` is copied verbatim from the mode's Ghostty `selection-background`.

### Deliberate exceptions to the 3:1 floor

- Every `*Shimmer` token — a shimmer is the bright end of an animated sweep over a base that
  does clear the floor.
- `claude` / `briefLabelClaude` at 2.79:1 in light: Anthropic's terracotta `#d77757` is kept
  rather than retinted, the same brand-over-contrast trade the Ghostty GitHub Light theme
  documents for its 2.3:1 gold.
- `success`, `green_FOR_SUBAGENTS_ONLY` and `diffAddedWord` at 2.96:1: all three are Latte
  green; the compliant stop is `#3f9e2b`, an invisible change.
- `subtle`, `promptBorder*` and `rate_limit_empty` are low-emphasis chrome. All three are
  *foregrounds* (see below) and each is held at or above the stock value it replaces, which is
  the bar that matters for them — not the 3:1 text floor.

### Which tokens are fills

Only seven paint a background: `userMessageBackground`, `userMessageBackgroundHover`,
`composerSidebarBackground`, `bashMessageBackgroundColor`, `memoryBackgroundColor`, and the two
`clawd_*`; `selectionBg` is applied separately as a selection style. The four `diffAdded`/
`diffRemoved`/`*Dimmed` values are line fills. **Everything else is a foreground**, including
several whose names suggest otherwise:

- `subtle` — 35 `color:` uses and 3 `borderColor:` uses, zero backgrounds. It paints the
  `… (N lines hidden)` collapse indicator and brief-mode labels, so it must stay legible.
- `background` — the *background task* accent (the `↳ N background` chip, cloud-session
  status, ultraplan borders), not a canvas fill. Teal in both stock modes, kept teal here.
- `diffAddedWord` / `diffRemovedWord` — dual-role: the intra-line word highlight *and* the
  `+N` / `−N` counters on every edit result, so they take the saturated palette green/red
  rather than a wash.
- `rate_limit_fill` / `rate_limit_empty` — both are `color:` on repeated glyphs, and the
  empty run is drawn with a *sparse* glyph (`░` / `▱`). A sparse glyph needs high nominal
  contrast to read at all, which is why the track is Latte's darkest ink in light rather than
  a surface tone.

Getting one of these wrong is invisible in review and obvious in use — a fill value on a
foreground token makes the element vanish. Verify with the built-in editor rather than by
inference: `/theme` → select `dotfiles` → set a token to magenta and look, then Esc to discard.

> The editor writes in place if you confirm, which reformats the file and drops any override
> equal to its base default. Recovery is `theme light` / `theme dark`.

Because both palettes have only about five ink stops and six surface stops, unrelated roles
sometimes share a hex (`subtle` and `promptBorderShimmer`, `inactive` and `promptBorder`).
That is reuse across roles that never render adjacent, not a collision.

### After a Claude Code upgrade

Overrides naming a token that no longer exists are **dropped silently** — no error, no log. If
a color looks stock after an upgrade, check that the theme's keys still exist in the base
palette:

```sh
strings -a ~/.local/share/claude/versions/$(claude --version | cut -d' ' -f1) \
  | grep -oE 'userMessageBackground|diffAddedWord|effortUltra'
```

Verified against Claude Code 2.1.220: all 56 keys present in both the `light` and `dark` bases.

## Status line

`statusline-command.sh` is a separate mechanism from the theme and the two never overlap: it
owns its entire output string, and its escape codes go straight to the terminal, so no theme
token can recolor it. It uses ANSI *named* colors only (`\033[36m` etc.), which the Ghostty
palette remaps per mode — so it tracks light/dark for free, with no entry in `theme-apply`.
