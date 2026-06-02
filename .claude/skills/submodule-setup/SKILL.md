---
description: |
  Manage git submodules in this dotfiles repo. Trigger when the user asks to add, update, or
  troubleshoot submodules; asks about the TPM submodule; or wants to add a new git submodule
  to the dotfiles. Covers .gitmodules, stamp-based caching, and the error-suppression pattern.
user-invocable: true
---

# Submodule Setup

How git submodules work in this dotfiles repo.

## Current submodules

One submodule: **TPM** (Tmux Plugin Manager) at `.config/tmux/plugins/tpm`, sourced from `https://github.com/tmux-plugins/tpm`. This path is also in the `LINKS` array, so it gets symlinked to `~/.config/tmux/plugins/tpm`.

## How `dotfiles.sh` handles submodules

Lines 427-436 in `dotfiles.sh`:

1. **Guard**: only runs if `.gitmodules` exists and is non-empty.
2. **Stamp caching**: computes MD5 of `.gitmodules`. If the stamp file (`$CACHE_DIR/dotfiles-submodule-stamp`) matches, the entire block is skipped. Submodule sync/init only runs when `.gitmodules` content changes.
3. **`git submodule sync --recursive -q`**: updates submodule URLs from `.gitmodules` into `.git/config`.
4. **`git submodule update --init --recursive -q`**: clones missing submodules and checks out the recorded commit.
5. **Error suppression**: both commands have `|| true` — submodule failures never abort the install.

## Adding a new submodule

```bash
cd ~/dotfiles
git submodule add <url> <path>
```

Then verify `.gitmodules` was updated. On next `./dotfiles.sh` run, the stamp will be stale and the new submodule will be initialized automatically.

If the submodule path should also be symlinked to `$HOME`, add a `LINKS` entry in `dotfiles.sh`.

## Updating submodules

To update all submodules to their latest remote commits:
```bash
cd ~/dotfiles
git submodule update --remote --merge
```

This changes the recorded commit in the index, which needs to be committed.

## Gotcha: stamp cache

The stamp file at `$CACHE_DIR/dotfiles-submodule-stamp` caches the `.gitmodules` MD5. If you manually edit `.gitmodules` and `dotfiles.sh` still skips the submodule section, clear the stamp:

```bash
rm -f ~/.cache/dotfiles-submodule-stamp
```

## Gotcha: error suppression

Submodule commands use `|| true`, so failures are silent. If a submodule is not initializing, run the commands manually without suppression to see errors:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

## Gotcha: shallow clones

`dotfiles.sh` does not use `--depth` for submodules. If you need a shallow submodule clone (e.g., for a large repo), add `--depth 1` to the `git submodule add` command and note it in `.gitmodules`:

```ini
[submodule ".config/tmux/plugins/tpm"]
    path = .config/tmux/plugins/tpm
    url = https://github.com/tmux-plugins/tpm
    shallow = true
```
