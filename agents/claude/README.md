# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`.

| Path | Installed as | Notes |
|------|--------------|-------|
| `CLAUDE.md` | symlink | One of the two canonical global instruction files — see root `CLAUDE.md`. |
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **merged** by `dotfiles.sh` | Merged onto the live file so keys Claude Code writes (e.g. `/effort`'s `modelSettings`) survive; repo values win and arrays are replaced whole, so a key deleted here must also be deleted from `~/.claude/settings.json`. `~/` is expanded to an absolute path, which Claude Code requires. `theme` is set to `custom:openai`. |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |
| `themes/openai-{dark,light}.json` | symlinks | Claude themes based on the built-in ANSI variants, with tuned text hierarchy, surfaces, and diff backgrounds. |
| `themes/openai.json` | generated file | Active "OpenAI (follows theme)" entry, replaced by `theme` so running Claude sessions can reload its colors. |

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

Claude Code uses the stable `custom:openai` selection. `theme` copies the matching
tracked variant to `~/.claude/themes/openai.json`; Claude watches that file and
reloads changes in running sessions. Sessions opened before this change with an
old `custom:openai-dark` or `custom:openai-light` selection need one manual
`/theme` selection of "OpenAI (follows theme)" (or a restart) to
start following the stable file.
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
