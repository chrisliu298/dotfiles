# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`.

| Path | Installed as | Notes |
|------|--------------|-------|
| `CLAUDE.md` | symlink | One of the two canonical global instruction files — see root `CLAUDE.md`. |
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **copied** by `dotfiles.sh` | `~/` is expanded to an absolute path on copy, which Claude Code requires. |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |

Skills are not here — they are symlinked into `~/.claude/skills/` from `agents/skills/` by the
`SKILLS` table in `dotfiles.sh`.

## Status line

`statusline-command.sh` owns its entire output string. It uses ANSI *named* colors only
(`\033[36m` etc.), which the Ghostty palette remaps per mode.
