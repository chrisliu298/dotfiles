# Repository Guidelines

Personal dotfiles and AI agent configurations for macOS with zsh, managed by `dotfiles.sh` (the single entrypoint: initializes submodules, symlinks configs into `~`, installs skills, and registers MCP servers + Claude plugins + tmux plugins).

> **Project-level doc, shared by Codex and Claude Code** (v2.1.277+ reads `AGENTS.md` when no `CLAUDE.md` exists). Global instructions live in `agents/AGENTS.md`. Don't add a root `CLAUDE.md` or `CLAUDE.local.md` — either makes Claude Code skip this file.

## Project Structure & Module Organization

Two `agents/<name>/` directories target one agent's home each: `claude/` → `~/.claude/` (`settings.json` — merged into the live file, not symlinked — keybindings, statusline, themes) and `codex/` → `~/.codex/` (themes). Muse Code has no `agents/` home: `~/.config/muse/settings.json` is host-local, with only the theme keys rewritten by `shell/theme-apply`. The rest are not agent homes:

- `agents/AGENTS.md` — the single global instruction file, symlinked as both `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`.
- `agents/eval/` — instruction-following harness for the shared agent doc (prompts, rubric, runner scripts).
- `agents/skills/` — the single source of truth for repo-owned skills; `dotfiles.sh` installs each into the agents the `SKILLS` table selects (most to Claude, Codex, and Muse; some are Claude- or Codex-only): live symlinks for Claude/Codex, and copy-installs into Muse's store-owned personal root via `muse skills install`. Manual skills install only when listed in `agents/skills/manual-skills.enabled`.

Elsewhere:

- `.config/ghostty`: Ghostty/cmux terminal config — tracked in-repo (not fetched from the standalone `chrisliu298/ghostty-config` repo), symlinked like the rest of `.config/`.
- The global instruction file `agents/AGENTS.md` is one agent-read text shared by Claude Code and Codex through symlinks, so there is no copy to sync. Behavior parity across models when the text changes is checked by the harness in `agents/eval/`.

## Build, Test, and Development Commands

- `./dotfiles.sh` — initialize submodules, sync skill repos, symlink files, install skills, and register MCP servers + Claude plugins + tmux plugins (TPM).
- `./dotfiles.sh lint` — run skill portability checks (universal C/X skill mechanical violations); also runs automatically at the end of a full `./dotfiles.sh`.
- `./dotfiles.sh skills` — list manual skills and whether each is enabled.
- `./dotfiles.sh enable <name>` / `./dotfiles.sh disable <name>` — toggle a manual skill; rewrites the committed `agents/skills/manual-skills.enabled` set.

## Conventions

- **Shell load order**: `shell/.zshenv` (platform detection, env, PATH) → `shell/.zshrc` (plugins, sources `.aliases` + `.functions`)
- **Themes**: Ghostty, Starship, btop, tmux, Neovim, Codex TUI, and Claude Code (OpenAI Light ↔ OpenAI Dark; Claude Code also has Anthropic Light ↔ Anthropic Dark) plus Muse Code on its built-in default theme, with fastfetch inheriting terminal ANSI colors, toggled with `theme light|dark|toggle|status`; use `theme --all <mode>` to apply the same mode on this host plus every peer in `_dotfiles_peers` (`shell/.functions`), the one list `theme --all` and `dfs` share. The active choice is **host-local** — a single `mode` file under `~/.local/state/dotfiles-theme/` (never tracked, so switching never dirties git); definitions stay in-repo. `shell/theme-apply` materializes each tool's live config from `mode` (Ghostty/tmux via optional `config-file`/`source-file -q` includes; btop/Starship as generated files, since neither supports includes; Codex by rewriting only `[tui].theme` in the host-local `~/.codex/config.toml`; Muse Code by rewriting only `tui.terminal_background` + `tui.theme` in `~/.config/muse/settings.json`; cswap by pinning `ui.theme` through `cswap config set`, since its terminal probe cannot see through tmux), and `dotfiles.sh` seeds/re-applies it per host. Neovim reads the mode at startup; fastfetch uses ANSI colors. Codex Desktop follows macOS through its own user-controlled appearance setting. Codex pins OpenAI Light/Dark syntax themes because its terminal-background probe can time out over SSH and fall back to dark on a light terminal. Claude Code has two stable themes, `custom:openai` (default) and `custom:anthropic`, chosen in `/theme`; `shell/theme-apply` replaces both host-local theme files so running sessions can reload the colors, and keeps either selection. The OpenAI variants inherit Ghostty’s ANSI palette and customize message, diff, and selection backgrounds; the Anthropic variants use Anthropic’s brand palette and keep only code syntax on Ghostty’s ANSI colors. Its status line uses matching terminal colors. Muse Code uses its built-in `default` theme in both modes, not the OpenAI palette; the pinned `tui.terminal_background` makes that default follow the light/dark toggle. It reads the selection at startup, so a switch applies on its next start.

## Skills, MCP Servers & Plugins

Never edit in `~/.claude/skills/` or `~/.codex/skills/` — those are symlinks. Check `agents/skills/README.md` for source.

Run `./dotfiles.sh` after changes to installation logic, skill wiring, or managed configuration. Instruction-only edits use the existing symlinks; run `./dotfiles.sh lint` and verify the affected links resolve instead.

## Testing Guidelines

- Validate installation, wiring, and managed configuration changes with `./dotfiles.sh` and affected symlink checks. For instruction-only edits, use `./dotfiles.sh lint`, `git diff --check`, and affected symlink checks.
- Run `./dotfiles.sh lint` when editing universal skills or skill-install logic.
- For skills with Python scripts, run `uv run pytest` on the relevant test file.
- If you add scripts, include at least one runnable verification path (a test or a documented command).

## Commit & Pull Request Guidelines

- Match existing history: imperative, concise subjects (`Add ...`, `Update ...`, `Remove ...`, `Refactor ...`).
- Keep commits atomic by logical change (docs vs scripts vs skill content).
- PRs include: purpose, changed paths, verification commands run, and any migration/symlink impact. Link related issues; add screenshots only for UI-facing documentation changes.
- **Peer sync is explicit-only**: run `dfs` only when the user explicitly requests it. Otherwise, do not run it or mention it in updates or the final response.

## Maintaining Docs

- **Global instructions**: edit `agents/AGENTS.md` only; it reaches both agents through symlinks — see `agents/eval/` for the parity check.
- **Update docs**: after structural changes (adding, removing, or renaming files/directories, skills, or configs), check whether `README.md` or `AGENTS.md` reference the affected paths and update them.

## Not Backed Up

OAuth tokens, command history, local settings, the host-local active theme (`~/.local/state/dotfiles-theme/`, so each machine keeps its own light/dark), per-project data, and cache files. API keys live in `~/.zshenv.local` (not in the repo, so `dfs` never carries them) — after adding a new `export *_API_KEY=` or `*_PLAN_KEY=` locally, run `synckeys` (a `shell/.functions` helper, not a `dotfiles.sh` subcommand) — dry-run first, then `synckeys apply` — to propagate it to the other machines.
