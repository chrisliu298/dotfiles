# agents/pi — Pi agent home

Config for [pi](https://pi.dev) (`pi` CLI by earendil-works), the 4th agent alongside
Claude/Codex/Grok. Everything here targets `~/.pi/agent/`.

| Path | Installed as | Notes |
|------|--------------|-------|
| `AGENTS.md` | symlink | One of the four canonical global instruction files — see root `CLAUDE.md`. |
| `settings.json` | symlink | Provider/model defaults, `packages`, theme pin. |
| `themes/{light,dark}.json` | **copied** by `theme-apply` | Verbatim copies of pi's built-in themes, `name` changed to `dotfiles`. |

Skills are not here — they are symlinked into `~/.pi/agent/skills/` from `agents/skills/`
by the `SKILLS` table in `dotfiles.sh`. Pi mirrors the Codex/Grok column (P == G).

## Extensions

Declared as `packages` in `settings.json`. Pi **auto-installs them on first launch**
(materialized under untracked `~/.pi/agent/npm/` and `~/.pi/agent/git/`), so a new machine
needs no `dotfiles.sh` step — `dfs` plus one `pi` launch is enough.

| Package | Why |
|---------|-----|
| `pi-subagents` | Parallel subagent dispatch. |
| `pi-web-access` | Stock pi has no web search or fetch at all. |
| `@plannotator/pi-extension` | `pi --plan` plan mode. |
| `context-mode` | Context inspection and pruning commands (`/ctx-*`). |
| `pi-hermes-memory` | Cross-session memory. Uses `better-sqlite3` (native) — see gotchas. |
| `pi-lens` | LSP diagnostics, autoformat, lint autofix, read-guard. |
| `pi-openai-server-compaction` | Codex-style server-side compaction — see below. |

### pi-openai-server-compaction

Pinned to `git:github.com/algal/pi-openai-server-compaction@8a3de2f`. Third-party and
**self-described as experimental**. It replaces pi's native text summarization with OpenAI's
Responses-API compaction protocol: on overflow it sends a `compaction_trigger` through
`POST /v1/responses` and stores the returned **encrypted** `compaction` item, the same path
Codex uses. That means compacted context lives server-side in a blob nobody can inspect.

Tradeoff, from the author's own held-out benchmark on product defaults: **78% exact recall
vs. 48%** for pi's default compactor — but at **4.58× the compaction output tokens** and a
**29% larger billed downstream context**, and the win was driven by large artifacts (three
small ones scored no better than the default). It is a recall-for-tokens trade, not a free
upgrade.

**Known risk:** its `package.json` declares all three pi peers as `>=0.80.9 <0.81.0`, while
we run pi 0.83.0 — it is outside its own declared compatibility range. Checked when pinning:
it uses none of the TypeBox APIs 0.83.0 removed, and it imports both `@earendil-works/pi-ai`
and `…/compat` (the extension loader aliases root → compat, so the 0.81 entrypoint move
doesn't bite). Neither check exercises a live compaction. Re-verify after any pi upgrade;
drop the package if a long session starts failing at the compaction boundary.

## Gotchas

- **`lastChangelogVersion` is runtime-written.** Pi rewrites it inside the tracked, symlinked
  `settings.json` after an update, which dirties the repo on whichever machine ran pi first.
  Commit the new value or `git checkout` it.
- **Native-module ABI breakage.** `pi-hermes-memory` uses `better-sqlite3`. A Node major
  upgrade breaks it (`NODE_MODULE_VERSION … requires …` → "Live session indexing failed").
  Fix: `npm --prefix ~/.pi/agent/npm rebuild better-sqlite3`.
- **Model IDs outside pi's registry degrade silently.** If `defaultModel` names a model the
  installed pi doesn't know, `buildFallbackModel` clones the provider's *default* model and
  swaps only the id — you get the wrong cost table and capabilities behind a one-line
  warning. Check the startup footer shows the model you expect, and upgrade pi rather than
  living with the fallback.
- **`pi-agent-browser-native` was tried and dropped.** It is only a bridge; it needs the
  `agent-browser` system binary plus a ~173MB Chrome-for-Testing download per machine, which
  `dfs` cannot carry, for a job `pi-web-access` mostly does.
