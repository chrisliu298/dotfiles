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

Claude Code uses the stable `custom:openai` selection. `theme` copies the matching
tracked variant to `~/.claude/themes/openai.json`; Claude watches that file and
reloads changes in running sessions. Sessions opened before this change with an
old `custom:openai-dark` or `custom:openai-light` selection need one manual
`/theme` selection of "OpenAI (follows theme)" (or a restart) to
start following the stable file.
Each variant inherits the corresponding built-in ANSI palette. Neutral text and
surface roles are overridden because the ANSI preset maps some secondary text
and light-mode surfaces to terminal colors with the wrong visual weight. The
Claude mascot uses the closest 256-color match to its built-in coral; the ANSI
preset would turn it bright red in the OpenAI terminal palette, while its RGB
color quantizes to pink in tmux. The light-mode assistant label uses a darker
orange for readable text, with a lighter spinner shimmer.
Normal diff rows use the same 256-color red and green backgrounds as Claude
Code's built-in themes. Word-level highlights use stronger shades instead of
resetting to the terminal background. Rejected edits retain quieter backgrounds
so they remain distinct. The empty usage-meter track stays neutral. Explicit
256-color values preserve the normal diff colors in tmux; Ghostty's
`faint-opacity = 0.75` helps dimmed deletion text remain legible.
