# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`.

| Path | Installed as | Notes |
|------|--------------|-------|
| `CLAUDE.md` | symlink | One of the two canonical global instruction files — see root `CLAUDE.md`. |
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **merged** by `dotfiles.sh` | Merged onto the live file so keys Claude Code writes (e.g. `/effort`'s `modelSettings`) survive; repo values win and arrays are replaced whole, so a key deleted here must also be deleted from `~/.claude/settings.json`. `~/` is expanded to an absolute path, which Claude Code requires. `theme` is set to `custom:openai`. |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |
| `themes/openai-{dark,light}.json` | symlinks | Claude themes based on the built-in ANSI variants, with tuned text hierarchy, surfaces, and diff backgrounds. |
| `themes/openai.json` | generated file | Active theme, replaced by `theme` so running Claude sessions can reload its colors. |

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
`/theme` selection of the generated OpenAI Light/Dark entry (or a restart) to
start following the stable file.
Each variant inherits the corresponding built-in ANSI palette. Neutral text and
surface roles are overridden because the ANSI preset maps some secondary text
and light-mode surfaces to terminal colors with the wrong visual weight. The
normal diff rows keep red and green backgrounds; rejected edits use quieter
backgrounds, and the empty usage-meter track stays neutral. In tmux, Claude
currently renders custom RGB colors through 256 colors, so rejected-edit
backgrounds become neutral grays; the normal red and green rows use exact
256-color values and retain their hue.
The dark diff backgrounds use xterm 256 colors 22 and 52. Claude Code defaults
to 256 colors in tmux, where the earlier RGB values both mapped to gray. The
darker red and Ghostty's `faint-opacity = 0.75` make dimmed deletion text easier
to read in dark mode; the opacity setting also improves light mode.
