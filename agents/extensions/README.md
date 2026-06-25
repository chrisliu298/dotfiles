# Extensions

Agent extensions for Claude, Codex, and Grok. **Skills**, **MCP servers**, and a curated set of **plugins** are managed by `dotfiles.sh`.

| Type | What it does | Managed by |
|------|--------------|------------|
| Skill | Injects domain knowledge via SKILL.md prompts | `SKILLS` table in `dotfiles.sh` |
| MCP server | Exposes external tools via Model Context Protocol | `MCP_SERVERS` table in `dotfiles.sh` |
| Plugin | Bundles commands, agents, hooks, and skills | `PLUGINS` table in `dotfiles.sh` (user scope) |

## Skills

Single source of truth: own skills live in `agents/extensions/skills/`; community/third-party skills are cloned to `~/.cache/skills-src/`. Both are symlinked into per-agent skill dirs:

- Claude → `~/.claude/skills/`
- Codex  → `~/.codex/skills/`
- Grok   → `~/.grok/skills/` (relay/prism dispatch target; mirrors the Codex set)

Each `SKILL.md` works across all three agents. Claude-specific frontmatter (`allowed-tools`, `user-invocable`, `effort`) is ignored by Codex and Grok. Per-agent scope is set via explicit `SKILLS` entries in `dotfiles.sh` (e.g., relay and prism are claude-only).

Toggle manual skills with `./dotfiles.sh enable/disable <name>`; list status via `./dotfiles.sh skills`.

### Skill matrix

Columns: **C**laude · Code**x** · **G**rok. Legend: ✓ auto-installed · ✱ manual (opt-in via `enable`) · — not wired to this agent.

> GLM, Kimi, DeepSeek, and MiMo are all reached **through** Claude Code as the harness (each is a `claude` session pointed at that model's endpoint) via the `glm`/`km`/`ds`/`mm` aliases (see `shell/.functions`), so they inherit the Claude column directly (no separate skill dir). **Grok** is a relay/prism dispatch target (no interactive alias) with its own `~/.grok/skills/` mirror of the Codex set — so its column equals Code**x**. The Claude-only orchestration skills (relay, prism, goal-loop, keep-warm, crons, skill-creator) stay off Codex/Grok; relay and prism are additionally guarded so a dispatched peer can't trigger them.

**Enabled** (✓ auto-installed):

| Skill | C | X | G | Source · Description |
|-------|:-:|:-:|:-:|----------------------|
| arxiv-reader            | ✓ | ✓ | ✓ | local — Read arxiv via TeX / HF markdown / HTML fallback |
| crons                   | ✓ | — | — | local — Durable manifest + re-arm for the recurring /loop cron fleet (Claude-only; preparer-not-actuator, no false assurance) |
| defuddle                | ✓ | ✓ | ✓ | [kepano/obsidian-skills][c-df] — Clean markdown extraction |
| digest                  | ✓ | ✓ | ✓ | local — Re-layer a dense reply into a fast-to-skim form |
| exec-status             | ✓ | ✓ | ✓ | local — Maintain a plain-English STATUS.md executive briefing for long autonomous runs |
| goal-drive              | ✓ | ✓ | ✓ | local — Drive a goal artifact (GOAL.md / checklist / phased doc) to verified done |
| goal-elicit             | ✓ | ✓ | ✓ | local — Multi-round interview → verifiable Goal Contract |
| goal-loop               | ✓ | — | — | local — Stepped elicit→review→fix loop (composes goal-elicit/goal-drive/prism; default review is prism, Claude-only) |
| gpt-pro-relay           | ✓ | ✓ | ✓ | local — SSH to ChatGPT Pro Extended on macmini |
| humanizer               | ✓ | ✓ | ✓ | [blader/humanizer][c-hu] — Remove AI signatures from text |
| jina                    | ✓ | ✓ | ✓ | local — Fetch web content / search via Jina AI |
| keep-warm               | ✓ | — | — | local — Cache heartbeat (uses Claude-only scheduling tools) |
| mental-seal             | ✓ | ✓ | ✓ | local — Hold ONE supreme priority front-of-mind via a visible user-owned SEAL.md vow (hook-free, C/X/G) |
| pdf                     | ✓ | ✓ | ✓ | [anthropics/skills][c-pdf-a] (Claude) / [openai/skills][c-pdf-o] (Codex/Grok) — PDF read/edit |
| prism                   | ✓ | — | — | local — Multi-perspective parallel review (Claude-only caller; dispatches parallax to Codex + Grok + GLM + Kimi + DeepSeek + MiMo via relay) |
| push                    | ✓ | ✓ | ✓ | local — Push to remote (auto-picks single vs atomic commits) |
| rehydrate               | ✓ | ✓ | ✓ | local — Recover post-compaction detail from the raw session transcript |
| relay                   | ✓ | — | — | local — Cross-agent relay from Claude to Codex/Grok/GLM/Kimi/DeepSeek/MiMo (Claude-only caller) |
| skill-creator           | ✓ | — | — | [anthropics/skills][c-sc] — Create / edit / benchmark skills |
| todo                    | ✓ | ✓ | ✓ | local — TODO.md tracking across sessions |
| xurl                    | ✓ | ✓ | ✓ | local — X/Twitter via the `xurl` CLI |

**Disabled** (✱ manual, opt-in via `./dotfiles.sh enable <name>`):

| Skill | C | X | G | Source · Description |
|-------|:-:|:-:|:-:|----------------------|
| autoresearch            | ✱ | ✱ | ✱ | local — Karpathy-faithful experiment loop |
| deslop                  | ✱ | ✱ | ✱ | local — Strip AI-slop from code changes |
| interviewer             | ✱ | ✱ | ✱ | local — Mock AI/ML technical interviews |
| prompt-engineer         | ✱ | ✱ | ✱ | local — Prompt writing per-vendor best practices |

> Note: SKILL.md supports an optional Claude-only `effort` frontmatter (`medium` / `high` / `max`) to set thinking budget per skill. Currently unset on every skill in this repo — they all inherit the session default.

[c-df]: https://github.com/kepano/obsidian-skills
[c-hu]: https://github.com/blader/humanizer
[c-pdf-a]: https://github.com/anthropics/skills
[c-pdf-o]: https://github.com/openai/skills
[c-sc]: https://github.com/anthropics/skills

### Discovery quirks (not managed here)

- **Plugin-provided skills**: Some skills (e.g., `code-simplifier`) come from Claude marketplace plugins and live in `~/.claude/skills/` as regular directories, not symlinks.

## MCP Servers

| Server | Purpose | Agents |
|--------|---------|--------|
| chrome-devtools | Chrome DevTools bridge for browser automation | Codex |
| codex | Codex MCP server for cross-agent tool access | Codex |

## Plugins

Managed by the `PLUGINS` table in `dotfiles.sh` — each is installed and enabled at **user scope** on every run (`name|marketplace`):

| Plugin | Marketplace | Purpose |
|--------|-------------|---------|
| code-simplifier | claude-plugins-official | Simplify/refactor changed code |

User scope keeps them available across all projects (vs. per-project pinning, which drifts between machines). Plugin install state lives in `~/.claude/plugins/` and is **not** synced by `dfs` — `./dotfiles.sh` reconciles it on each machine. Other marketplace plugins can still be added ad hoc with `claude plugin install`.
