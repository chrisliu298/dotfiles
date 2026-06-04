# CLAUDE.md

Personal dotfiles and AI agent configurations for macOS with zsh. Managed by `dotfiles.sh` (symlinks to `~`).

> This is the **project-level** CLAUDE.md. Global user instructions are in `agents/claude/CLAUDE.md`.

## Structure

```
dotfiles/
├── dotfiles.sh              # Single entrypoint: setup
├── shell/                   # Zsh config (.zshrc, .zshenv, .aliases, .functions)
├── .config/                 # App configs (Neovim, tmux, btop)
├── .claude/skills/          # Project-local skills (dotfiles-only)
└── agents/
    ├── claude/              # Claude Code (~/.claude/) — CLAUDE.md, settings (copied), keybindings, hooks, statusline
    ├── codex/               # Codex (~/.codex/) — AGENTS.md
    ├── grok/                # Grok Build (~/.grok/) — AGENTS.md (relay/prism dispatch target)
    └── extensions/skills/   # Global skills (SKILL.md per skill)
```

## Setup

```bash
./dotfiles.sh  # Initialize submodules, symlink files, verify links
```

## Conventions

- **Shell load order**: `shell/.zshenv` (platform detection, env, PATH) → `shell/.zshrc` (plugins, sources `.aliases` + `.functions`)
- **Modern tools**: `fd` → find, `rg` → grep, `delta` → diff, `zoxide` → z (installed via Zinit, macOS ARM)
- **Platform detection**: `IS_MACOS` set in `shell/.zshenv`, used for macOS-only code
- **Python**: Use `uv` for virtual environments (`sv`, `us`, `ua`, `upi` aliases)
- **Prompt**: Starship (custom GitHub Dark gradient palette, config in `.config/starship/`)
- **Themes**: Ghostty (GitHub Dark), btop (GitHub Dark)

<important if="you are editing or creating skills">

## Editing Skills

Never edit in `~/.claude/skills/`, `~/.codex/skills/`, or `~/.grok/skills/` — those are symlinks. Check `agents/extensions/README.md` for source.

- **Own skills** (`agents/extensions/skills/`): Edit in this repo — this is the single source of truth.
- **Third-party skills** (cloned from GitHub): Edit in the source repo or fork
- **Best practices**: Read `agents/extensions/references/skill-best-practices.md` before creating or improving skills
- **Verify vendor guidance**: Before updating skills with vendor/model guidance, check against official current docs—don't preserve stale model names or deprecated API parameters.
- **Validate referenced paths**: When skill docs reference installed or symlinked paths, verify they exist after `./dotfiles.sh`.

Run `./dotfiles.sh` after changes to re-sync symlinks.

</important>

<important if="you are adding a new extension or skill to dotfiles">

## Adding Extensions

Managed by `SKILLS` table in `dotfiles.sh` (git-clone + symlink, no `npx skills`):

- **Local**: Add `<name>/SKILL.md` under `agents/extensions/skills/`, run `./dotfiles.sh`
- **Upstream**: Add `name|owner/repo/subpath|agents` entry to `SKILLS` table
- **Agent-specific**: Separate table entries per agent (e.g., `pdf` has different sources for claude vs codex)
- **Manual skills**: Add name to `MANUAL_SKILLS` array — skipped during auto-install, toggled with `./dotfiles.sh enable/disable <name>`
- **Project-local skills**: Place in `.claude/skills/<name>/` — available only in this repo, not globally
- **Install/update all**: `./dotfiles.sh`

Single SKILL.md per skill works in both agents. Include Claude-specific frontmatter (`allowed-tools`, `user-invocable`) — Codex ignores unknown keys.

</important>

<important if="you are committing and pushing changes to this repo">

## Sync After Push

After `git push` succeeds, run `dfs` to propagate changes to all peers (concurrent `git pull --ff-only` + `./dotfiles.sh` on each of `macbookpro16`, `macmini`, `l40s`; self is skipped automatically). Without this step, the other machines stay on the previous revision until manually synced.

From a non-interactive shell (e.g., an agent invoking it via a tool), use `zsh -c 'source ~/dotfiles/shell/.functions && dfs'` — no TTY required, and `dfs` is self-contained so `.zshrc` is not needed.

</important>

<important if="you are modifying CLAUDE.md, AGENTS.md, README.md, or project structure">

## Maintenance

- **Sync instructions**: `agents/claude/CLAUDE.md`, `agents/codex/AGENTS.md`, and `agents/grok/AGENTS.md` share working principles (compatibility diffs only — e.g. Codex's `update_plan`, Claude's `<important>` wrappers) — update all three when changing any
- **Update docs**: After structural changes, check if `README.md`, `CLAUDE.md`, or `AGENTS.md` reference affected paths

</important>

## Not Backed Up

OAuth tokens, command history, local settings, per-project data, and cache files. API keys live in `~/.zshenv.local` (not in the repo, so `dfs` never carries them) — after adding a new `export *_API_KEY=` or `*_PLAN_KEY=` locally, run `synckeys` (dry-run) then `synckeys apply` to propagate it to the other machines.
