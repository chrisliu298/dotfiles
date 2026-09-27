# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`.

| Path | Installed as | Notes |
|------|--------------|-------|
| `CLAUDE.md` | symlink | One of the two canonical global instruction files — see root `CLAUDE.md`. |
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **copied** by `dotfiles.sh` | `~/` is expanded to an absolute path on copy, which Claude Code requires. `theme` is set to `custom:openai`. |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |
| `themes/openai-{dark,light}.json` | symlinks | Claude themes based on the built-in ANSI variants, with tuned message, diff, and selection backgrounds. |
| `themes/openai.json` | generated file | Active theme, replaced by `theme` so running Claude sessions can reload its colors. |

Skills are not here — they are symlinked into `~/.claude/skills/` from `agents/skills/` by the
`SKILLS` table in `dotfiles.sh`.

## Status line

`statusline-command.sh` owns its entire output string. It uses ANSI *named* colors only
(`\033[34m` etc.), which the Ghostty palette remaps per mode. Project and
worktree names use blue, branches and additions use green, and deletions use red.

Claude Code uses the stable `custom:openai` selection. `theme` copies the matching
tracked variant to `~/.claude/themes/openai.json`; Claude watches that file and
reloads changes in running sessions. Sessions opened before this change with an
old `custom:openai-dark` or `custom:openai-light` selection need one manual
`/theme` selection of the generated OpenAI Light/Dark entry (or a restart) to
start following the stable file.
Each variant inherits the corresponding built-in ANSI palette and tunes the
message, diff, and selection backgrounds.
The dark diff backgrounds use xterm 256 colors 22 and 52. Claude Code defaults
to 256 colors in tmux, where the earlier RGB values both mapped to gray. The
darker red and Ghostty's `faint-opacity = 0.75` make dimmed deletion text easier
to read in dark mode; the opacity setting also improves light mode.
