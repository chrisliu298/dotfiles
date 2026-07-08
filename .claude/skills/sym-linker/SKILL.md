---
description: |
  Manage symlinks in this dotfiles repo. Trigger when the user asks to add, remove, verify, or
  troubleshoot symlinks; asks what dotfiles.sh links; or wants to add a new config file to the
  dotfiles. Covers the LINKS array, ensure_symlink() behavior, and the settings.json exception.
user-invocable: true
---

# Sym-Linker

How symlinks work in this dotfiles repo.

## Architecture

`dotfiles.sh` has two symlink systems:

1. **LINKS array** (line 8): maps `source:destination` — repo-relative source → `$HOME`-relative destination. Processed by `install_links()` which calls `ensure_symlink()` for each entry.
2. **SKILLS array** (line 27): maps skill directories into `~/.claude/skills/`, `~/.codex/skills/`, `~/.grok/skills/`, and `~/.pi/agent/skills/` (per the entry's `agents` column). Processed by `install_skills()`. Stale skill symlinks are cleaned up aggressively.

Both use the same `ensure_symlink()` helper.

## The LINKS array format

```
"repo-relative/path:home-relative/path"
```

Example: `"shell/.aliases:.aliases"` creates `~/.aliases → ~/dotfiles/shell/.aliases`.

To add a new config: append to the `LINKS` array in `dotfiles.sh`, then run `./dotfiles.sh`.

## Critical gotcha: `rm -rf` on targets

`ensure_symlink()` (line 76) does:
```bash
rm -rf "$dest"
ln -s "$src" "$dest"
```

If `$dest` is a real directory (not a symlink), **it is destroyed without backup**. Always check if a target exists as a real directory before adding a LINKS entry. Use `ls -la ~/path` to verify.

## The `settings.json` exception

`settings.json` is **copied** with `~/` expanded to `$HOME` (line 173), not symlinked. Claude Code requires absolute paths. Changes to `~/.claude/settings.json` directly are overwritten on next `./dotfiles.sh` run.

## Verifying symlinks

Check a specific link:
```bash
ls -la ~/.config/nvim
# Should show: ~/.config/nvim -> /Users/.../dotfiles/.config/nvim
```

Audit all LINKS entries against actual symlinks:
```bash
source ~/dotfiles/dotfiles.sh  # loads ROOT and LINKS
for entry in "${LINKS[@]}"; do
  dest="$HOME/${entry#*:}"
  if [[ -L "$dest" ]]; then
    echo "✓ $dest -> $(readlink "$dest")"
  else
    echo "✗ $dest (missing or not a symlink)"
  fi
done
```

## Skill symlinks vs LINKS symlinks

Skill symlinks are managed separately by `install_skills()` (line 207). They are cleaned up if not in the expected set (lines 251-267). Manual skills in the `MANUAL_SKILLS` array are excluded from cleanup. Do not confuse the two systems.
