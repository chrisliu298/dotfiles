# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`. The global `~/.claude/CLAUDE.md` is a symlink to the shared [`agents/AGENTS.md`](../AGENTS.md).

| Path | Installed as | Notes |
|------|--------------|-------|
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **merged** by `dotfiles.sh` | Merged onto the live file so keys Claude Code writes (e.g. `/effort`'s `modelSettings`) survive; repo values win and arrays are replaced whole, so a key deleted here must also be deleted from `~/.claude/settings.json`. `~/` is expanded to an absolute path, which Claude Code requires. `theme` is not set here; `shell/theme-apply` owns it (see below). |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |
| `themes/anthropic-{dark,light}.json` | symlinks | Claude themes in Anthropic's brand palette, built on the ANSI variants so code syntax follows the terminal. |
| `themes/openai-{dark,light}.json` | symlinks | Claude themes based on the built-in ANSI variants, with tuned text hierarchy, surfaces, and diff backgrounds. |
| `themes/{anthropic,openai}.json` | generated files | Active "Anthropic (follows theme)" and "OpenAI (follows theme)" entries, replaced by `theme` so running Claude sessions can reload their colors. |

Skills are not here — they are symlinked into `~/.claude/skills/` from `agents/skills/` by the
`SKILLS` table in `dotfiles.sh`.

## Status line

`statusline-command.sh` owns its entire output string. It uses ANSI *named* colors only
(`\033[34m` etc.), which the Ghostty palette remaps per mode. Project and
worktree names use blue, branches and additions use green, and deletions use red.
Elapsed time uses cyan, context percentage uses purple, and cost uses gold;
context labels and token counts stay muted so the status line remains scannable.

The default layout has two rows: model/project/git/session details first, then
context/5-hour and 7-day limits/cost/changed lines. It reads Claude Code's
`COLUMNS` and wraps at field boundaries in narrow panes, reserving four columns
for footer spacing. A field wider than the pane wraps within the field without
dropping text. ANSI colors and OSC 8 links do not count toward width and remain
intact across rows; CJK and combining text use Unicode display widths. The
renderer uses `jq` and macOS's bundled Perl (`Unicode::UCD`). Without a valid
`COLUMNS`, it assumes 120 columns.

Two theme families are installed, each with a stable entry that follows the
light/dark mode: `custom:openai` (the default) and `custom:anthropic`. `theme`
copies the matching tracked variants to `~/.claude/themes/anthropic.json` and
`~/.claude/themes/openai.json`; Claude watches the selected file and reloads
changes in running sessions. Pick a family with `/theme`; `theme-apply` keeps
either choice and only sets `custom:openai` when the selection is anything
else. A session opened with an older selection (such as `custom:openai-dark`)
needs one manual `/theme` pick (or a restart) to start following a stable file.

### Anthropic

Both variants take their colors from the design tokens on anthropic.com,
claude.com, and claude.ai: warm slate neutrals for text and surfaces (user
messages sit on slate-800 in dark, slate-150 in light), clay `#d97757` for the
Claude label, spinner, mascot, and usage meter, sky for permission prompts and
inline code, plum for auto-accept and skills, fig for bash mode, mineral for plan
mode, and olive/error red for success and failure. Light mode darkens the accents
(clay to the official `#c6613f` hover shade, sky/plum/fig/mineral/olive to about
5:1 on white) so text stays readable. Selections use peach in light mode and a
dark clay tint in dark mode.

Code syntax still uses Ghostty's ANSI colors through the `*-ansi` bases; a
non-ANSI base would switch Claude to its built-in Monokai/GitHub syntax and fixed
diff backgrounds. Diffs use olive added rows and terracotta removed rows. The four
diff tokens are `ansi256()` indices (dark 58/88/107/167, light 193/217/107/167),
separate from the OpenAI ones, that the Ghostty themes remap, because Claude
limits diff backgrounds to 256 colors inside tmux. The word-highlight tokens also
color the `+N`/`-N` counts.

### OpenAI

Both variants inherit Claude's ANSI syntax palette, with green added rows and
red removed rows. Neutral text and surfaces are overridden to keep the hierarchy clear. The
Claude mascot uses its built-in coral, `rgb(215,119,87)`; the ANSI preset would
turn it bright red in the OpenAI terminal palette. In tmux, where Claude renders
256 colors, the RGB value may quantize toward pink. The light-mode assistant label uses a darker
orange for readable text, with a lighter spinner shimmer.
Word highlights use softer green/red shades than the built-in ANSI palette;
the same theme tokens also color `+N` and `-N` counts. Inside tmux, Claude
quantizes light RGB word colors to indices 72 and 174; Ghostty remaps those
along with row colors to keep the appearance consistent. The empty usage-meter track stays neutral.
Ghostty's `faint-opacity = 0.75` helps dimmed deletion text remain legible.
