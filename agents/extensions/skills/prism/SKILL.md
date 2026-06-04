---
name: prism
description: >-
  Dispatch multiple independent agents to answer the SAME complete question
  from different analytical lenses, then synthesize their perspectives.
  Use for non-trivial decisions, ambiguous tradeoffs, or high-stakes changes
  where a single perspective might miss something.
user-invocable: true
allowed-tools:
  - Agent
  - Bash
  - Read
  - Write
  - Grep
  - Glob
  - Skill
---

# Prism

**Claude-only.** If `ANTHROPIC_BASE_URL` contains `deepseek` or `xiaomimimo`, this skill is unavailable — stop and tell the user: "prism is Claude-only; a non-Claude session cannot orchestrate other models." Prism dispatches parallax via [[relay]], which itself refuses from non-Claude sessions.

Prism sends the **same complete question** to multiple independent agents. Each agent answers the **entire question end-to-end**. The only thing that changes between agents is the **lens**: what they prioritize and what tradeoffs they weigh more heavily.

## Core Principle

**Prism is redundancy, not division of labor.** Every agent gets the full question, full scope, and full deliverable. The lens changes **emphasis**, not **coverage**. If agents own different files, sections, or outputs, that is division of labor, not Prism.

Convergence across diverse lenses is high-confidence signal; divergence surfaces tradeoffs that need explicit resolution.

## Structure

| Tier | Tool | Role |
|------|------|------|
| Self | (none) | Your own analysis while agents run |
| Subagents | **Agent** | Same-model agents (Claude), one Agent call each |
| **Parallax — Codex** | **Bash** (`relay call --to codex`) | Cross-model agents via relay to GPT-5.5 |
| **Parallax — Grok Build** | **Bash** (`relay call --to grok-build`) | Cross-model agents via relay to xAI Grok Build (effort medium/high) |
| **Parallax — Grok Composer** | **Bash** (`relay call --to grok-composer`) | Cross-model agents via relay to xAI Composer 2.5 (fast; no effort knob) |
| **Parallax — DeepSeek** | **Bash** (`relay call --to deepseek`) | Cross-model agents via relay to DeepSeek V4 Pro |
| **Parallax — MiMo** | **Bash** (`relay call --to mimo`) | Cross-model agents via relay to Xiaomi MiMo-V2.5-Pro |

**Default: all six models at `N=1`** — self + 1 Claude subagent + 1 each of Codex, Grok Build, Grok Composer, DeepSeek, MiMo = **6 dispatched + self** (7 perspectives). Required dispatch: **`N` Agent calls + 1 backgrounded `prism-launch parallax` call that fans out the `5N` relay calls** (manual fallback: `5N` separate Bash relay calls). Self does not count. All six models are always included at the chosen `N`; the only way to deviate — exclude a tier, or give a tier its own count or effort — is an explicit natural-language modification (see Invocation Shorthand).

### Invocation Shorthand

Two layers: a dead-simple positional form for the symmetric common case, and natural language for any deviation.

**Positional — `prism [N] [m|xh] <question>`:**
- `N` — how many of **each** of the six models (Claude subagents, Codex, Grok Build, Grok Composer, DeepSeek, MiMo). Integer `≥ 1`, default `1`; reject `0` (to drop tiers, use a natural-language exclusion). Total dispatched = `6N` (each count is per model, so cost scales 6×); self does not count.
- `m|xh` — shared effort for the two tunable tiers (default `m`). The flag is **one knob with two settings**, but each setting maps to a *different word per tier* — Codex and Grok Build do not share an effort vocabulary:
  - `m` → Codex `medium` · Grok Build `medium`
  - `xh` → Codex `xhigh` · Grok Build `high`
  - Codex effort is **only** `medium` or `xhigh` (never `high`); Grok Build effort is **only** `medium` or `high` (never `xhigh`). Grok Composer, DeepSeek, and MiMo have no effort knob — always unset.

Both tokens are optional and **positional** — at most one `N`, then at most one effort, then the question (each token whitespace-delimited):
- **Slot 1:** a standalone integer → `N`; a standalone `m`/`xh` → effort (with `N` defaulting to `1`); anything else → the question starts here.
- **Slot 2** (only if Slot 1 was `N`): a standalone `m`/`xh` → effort; anything else → the question starts here.
- There is no third config slot, so once a slot isn't filled the rest is the question verbatim — a *second* integer, or any word, is always question text. Examples: `prism 2 3 reasons?` → `N=2`, question "3 reasons?"; `prism xh root cause?` → effort `xh`, question "root cause?"; `prism migration plan` → question "migration plan" (Slot 1 `migration` is neither a standalone integer nor `m`/`xh`).
- **Escape:** if the question's own first word is a bare integer, `m`, or `xh` and you want default config, put `--` first — everything after `--` is question text.

Examples:
- `prism Why does X?` — 1 of each, medium → 6 agents + self.
- `prism 2 Why does X?` — 2 of each, medium → 12 + self.
- `prism xh Why does X?` — 1 of each, high tier (Codex `xhigh`, Grok Build `high`).
- `prism 2 xh Why does X?` — 2 of each, high tier.
- `prism -- 2 reasons to refactor?` — default N=1, medium; the `--` makes the leading `2` question text instead of `N`, so the question is "2 reasons to refactor?".

**Natural-language modifications.** The positional form always dispatches all six models symmetrically; to deviate, state it in words **in a leading config clause before the question** (config is parsed only up to where the question begins — a modifier buried *after* the question starts is treated as question text, not config). Treat a phrase as a modification only when it pairs a **tier name with a config action** (a count, an exclusion word like no/skip/without, or an explicit effort level); a bare tier name inside the question — e.g. *"why is there no DeepSeek fallback?"* — is **not** a modification, so do not strip or reinterpret it. Resolve the modifications into an explicit per-tier `(count, effort)` config before launch. Supported:
- **Exclude a model** — "no DeepSeek", "skip Grok Composer", "without mimo" → that tier's count = `0` (simply not dispatched; warn the user that dropping a whole lineage reduces cross-model diversity).
- **Per-model count** — "2 Codex, 1 of the rest", "3 Claude subagents" → the named tier overrides `N`; unnamed tiers keep `N`.
- **Per-tier / manual effort** — "Codex at xhigh, Grok Build medium", "max effort on Codex only" → override the coupled `m`/`xh` default for the named tier(s). Map a natural-language effort qualifier to the tier-valid level: "high"/"max" → Codex `xhigh`, Grok Build `high`; "medium" → `medium`. Honor the per-tier vocabularies: Codex `medium`/`xhigh`, Grok Build `medium`/`high` — never emit Codex `high` or Grok Build `xhigh`.
- **Combinations** — "2 of each at xh but no Grok Composer".
- **Asymmetric example** (the old `prism 2 2x 0 0 2 2` migration): "2 of each at xh, but no Grok Build or Grok Composer, and 2 DeepSeek" → Claude 2, Codex 2 (xhigh), Grok ×0, DeepSeek 2, MiMo 2.

`N` and `m`/`xh` set the symmetric baseline; named modifications override specific tiers on top of it (an explicit exclusion overrides the "all six always included" default; on conflicting clauses the more specific or later one wins). Resolve to a final per-tier table, then dispatch exactly that — every tier with resolved count > 0 MUST be dispatched at that count (do not skip, substitute, or defer; exception: `relay` unavailable → substitute a same-model subagent carrying that tier's lens and warn). You — the orchestrator — own resolving the shorthand and NL into the dispatch records; `prepare` then validates the *authored* dispatch file and emits the authoritative manifest counts, but it cannot know your intended `N`, so confirm the resolved shape matches your intent before running it (Pre-Launch Check #5).

### Parallax (cross-model agents)

Parallax is dispatched via `relay` to **different models** (Codex, Grok Build, Grok Composer, DeepSeek, MiMo). Invoke `relay` directly — not via a subagent that calls relay. The value of each tier is model diversity:

- **Codex** brings GPT-5.5's training, its strengths in agentic code review, and two effort tiers (`medium`/`xhigh`).
- **Grok Build** brings xAI's independent lineage (agentic coding model `grok-build`), distinct from the Anthropic and OpenAI families, with effort tiers `medium`/`high`.
- **Grok Composer** is xAI's fast variant (Composer 2.5, `grok-composer-2.5-fast`) — **same xAI lineage as Grok Build**, optimized for speed, no effort knob. It adds little *independent* diversity beyond Grok Build, so treat the two Grok tiers as one vendor slot when assigning diversity lenses; reach for Composer when you want a fast xAI take rather than a distinct lineage.
- **DeepSeek** brings an entirely independent training lineage (open-weight V4-Pro), distinct prompting conventions, and always runs at `max` (DeepThink).
- **MiMo** brings a third independent lineage (Xiaomi's open-weight MiMo-V2.5-Pro, 1.02T MoE / 42B active, 1M context), distinct again from both the Anthropic and OpenAI families. No effort knob.

**Tier strength and lens fit (heuristic, not a routing rule):** Claude Opus 4.7 (subagents) and GPT-5.5 (Codex) are roughly peers in raw reasoning capability and sit at the top. The independent-lineage parallax tiers — MiMo-V2.5-Pro and DeepSeek V4-Pro — are each meaningfully weaker on hard reasoning at peak effort, with MiMo slightly ahead of DeepSeek. Grok Build (xAI) is new here and unbenchmarked — treat its placement as provisional (plausibly near the Codex tier on coding; verify before trusting it with the heaviest-reasoning lens), and Grok Composer (its fast variant) weaker still. The rough ranking is **Claude ≈ Codex > {Grok Build provisional, MiMo ≳ DeepSeek} > Grok Composer**. This does *not* reduce the weaker tiers' value — each independent training lineage catches blind spots the others share, which is the entire point of model diversity. The asymmetry should inform lens assignment only:

- **Subtle hard-reasoning lenses on risk-bearing questions** (Adversarial / Falsification / Disconfirming on a technical proposal where finding the non-obvious attack is the deliverable): prefer Claude subagent or Codex at `--effort xhigh`. If exactly one lens carries the heaviest reasoning load and it lands on a parallax tier, you've under-resourced the most decision-relevant role; when it must land on one anyway, prefer MiMo over DeepSeek.
- **Lenses where the value is a different prior** (Outsider, First-Principles, Disconfirming-via-different-frame, Breadth-Weighted, Risk, Alternative-Framing): give these to DeepSeek and MiMo. Their independent lineages are the asset; raw reasoning depth is not the bottleneck.
- **Parallax lenses comparably hard:** no swap needed.
- **Never drop DeepSeek or MiMo to "upgrade" a run.** Lineage diversity is non-substitutable; default tier inclusion is unchanged.

This affects assignment only. In synthesis, DeepSeek and MiMo dissent retain full cross-model weight — discount weak reasoning, never the model label. Treat the ranking as approximate; revisit when model versions change (the named model versions above are the canary — when they look stale, this section is stale).

Assign each tier a lens that maximizes diversity. **Default to orthogonal exploratory lenses** (Breadth-Weighted, Depth-Weighted, Outsider, First-Principles, Disconfirming-via-different-frame) — these almost always extract more from cross-model diversity than a second attack angle. **Reach for an adversarial lens (Adversarial, Falsification, Disconfirming) only when it is much more valuable than another orthogonal lens would be** — i.e., the deliverable hinges on finding a non-obvious flaw, attack, or failure mode, and no other dispatched lens is already covering that ground. When that bar is met, put it on the parallax tier best suited to the reasoning load (see "Tier strength and lens fit"); otherwise skip it. When using multiple parallax tiers, give each a distinct lens — never assign the same lens to two of Codex, DeepSeek, MiMo, or the Grok tiers (that wastes a perspective). Treat grok-build + grok-composer as **one** vendor slot: don't give them two different diversity lenses as if independent (they share the xAI lineage). And don't stack two adversarial lenses unless the task genuinely demands independent attack frames.

You do **not** need to strictly follow each peer's model-specific prompting guide (the [[relay]] skill's **Prompting Codex** / **Prompting DeepSeek** references) when composing Parallax prompts. Prism sends the **same shared prompt** to every model, so tailoring the body per peer would break the identical-prompt invariant — and the launcher templates already handle the only per-peer difference that matters (the wrapper format: Codex's `<goal>` style vs the CO-STAR XML for independent-lineage peers). What still matters is that the shared prompt is **high-quality**: a clear, outcome-first shared packet (Full Question + Context + Constraints) and sharp, distinct lens descriptions. Optimize the prompt's quality, not its per-model fit. (Those references remain useful if you ever hand-tune a single relay call outside Prism.)

**Relay call syntax (exact)** — the command shapes Prism must emit:

```bash
# Codex parallax
relay call --to codex --name <slug> --effort <medium|xhigh> <<'BODY'
<prompt content here>
BODY

# Grok Build parallax (prism uses effort medium|high)
relay call --to grok-build --name <slug> --effort <medium|high> <<'BODY'
<prompt content here>
BODY

# Grok Composer parallax (no --effort — fast model, no effort knob)
relay call --to grok-composer --name <slug> <<'BODY'
<prompt content here>
BODY

# DeepSeek parallax (no --effort — always max)
relay call --to deepseek --name <slug> <<'BODY'
<prompt content here>
BODY

# MiMo parallax (no --effort — no effort knob)
relay call --to mimo --name <slug> <<'BODY'
<prompt content here>
BODY
```

Use a lowercase slug for `--name` (e.g., `prism-adversarial`). Grok Build takes `--effort medium|high`; Codex takes `--effort medium|xhigh`; never pass `--effort` or model flags on DeepSeek, MiMo, or Grok Composer (none has an effort knob). For all other invocation rules — `--name` required, `--to codex` as the default, non-empty heredoc, no model flags — follow the [[relay]] skill rather than restating them. For concurrency (backgrounding, timeouts), follow relay's Async / Parallel section.

**Inspecting Parallax results:** Only read the `.res.md` response file. Never read the `.log` sidecar — it contains the peer's full stderr, which is extremely long and token-heavy. The relay script's Bash output already surfaces diagnostic information for failure cases.

If `relay` is unavailable, replace all Parallax tiers with same-model subagents and warn the user. Each substitute carries the lens that tier was already assigned — do not re-decide by task category. Relay being unavailable does not change whether adversarial coverage is valuable for this question.

**Constraint leakage risk (CRITICAL):** Relay peers may recurse unless the anti-recursion rule is explicit, early, and repeated. You MUST:
1. Put the anti-recursion warning at the top of every launcher prompt, before the file-read instruction.
2. Preserve the Constraints section verbatim in the shared context file — do not summarize or abbreviate.
3. Ensure the prohibition appears in both each launcher (short form) and the shared file (full form).
4. Tell each peer to ignore loaded skill descriptions for the dispatching/side-effecting skills (prism, relay, gpt-pro-relay, deep-research) — read-only analysis skills stay available.

Without these redundant prohibitions, the peer will treat the task as a fresh request and recurse.

**Effort selection for Parallax:** The run-level flag sets the two tunable tiers together — `m` → Codex `--effort medium` + Grok Build `--effort medium`; `xh` → Codex `--effort xhigh` + Grok Build `--effort high` (default `m`). A natural-language modification overrides one tier independently (e.g. "Codex xhigh" alone, or "Grok Build medium"): Codex accepts `medium`/`xhigh` only, Grok Build accepts `medium`/`high` only — never Codex `high`, never Grok Build `xhigh`. DeepSeek, MiMo, and Grok Composer have no effort knob — DeepSeek always runs at `max`; MiMo and Grok Composer take no effort flag at all. Reach for `xh` (or a per-tier override) when a heavy adversarial/falsification lens lands on Codex or Grok Build and needs deeper reasoning; otherwise `m` is the balanced default.

### Subagents

Same-model agents dispatched via the Agent tool. Each gets a distinct lens. **Prism subagents are logical leaf nodes** — their prompts must forbid subagent spawning, dispatching-skill invocation (prism, relay, gpt-pro-relay, deep-research, any cross-model dispatch), and side effects, while permitting read-only analysis skills (see Constraints in the Shared Packet Template). Launch all agents concurrently before starting self-review.

## Side-Effect Safety

Dispatched agents are **read-only** — no edits, commits, deploys, or external side effects. The only exception is the relay response file (`.res.md`) named in a `Reply:` directive. The primary agent may implement changes after synthesis if the user requested a deliverable.

## Shared Context

Build one shared evidence packet (Full Question + Context + Constraints) before composing prompts. Prefer compact digests over full file dumps. Write it to a temporary file once; every agent receives a short launcher prompt referencing this file plus its unique lens. If the packet cannot be duplicated cleanly across all agents, the task is too large for Prism.

**Reference materials (REQUIRED):** Before building the shared packet, identify all reference materials relevant to the question — CLAUDE.md files, READMEs, config files, documentation, skill definitions, style guides, or any file an agent would need to reason about the task. Include the **absolute paths** of these files in the Context section of the shared packet so every agent can read them. Agents cannot discover references on their own; if a path is not listed, the agent will not consult it.

### Shared Packet Template

Write this to `/tmp/prism-<unique-id>.md` using the Write tool (one call, before any dispatch). Use a unique identifier (e.g., timestamp + random suffix) to prevent collisions between concurrent Prism runs.

```
## Full Question

{User's COMPLETE question/task, unchanged. Identical across all agents.}

## Context

{Shared evidence packet. Identical across all agents.}

### Reference Materials

{List absolute paths to every file relevant to the question — CLAUDE.md, READMEs, configs, docs, skill files, style guides, etc. Agents MUST read these before answering.}

- /path/to/relevant/file1
- /path/to/relevant/file2
- ...

## Constraints

You are a read-only leaf node. Produce analysis text only.

You MAY use skills/tools that only read, fetch, or analyze (read files, search the repo, fetch web pages or PDFs).

You must NOT:
- Spawn subagents or any nested agent.
- Invoke any skill that dispatches to, relays to, or coordinates another agent or model (prism, relay, gpt-pro-relay, deep-research), or call the codex or grok CLIs, the deepseek (ds/dsh) or mimo (mm) aliases, or any cross-model dispatch tool.
- Edit files, commit, push, or trigger any external side effect, or invoke a skill that does (e.g., push, xurl, todo, goal-drive).
- Act on loaded skill descriptions that would make you recurse or cause side effects (e.g., prism, relay, gpt-pro-relay, deep-research) — those are for standalone use, not this context.

The ONLY file you may write is the relay response file (.res.md) named in this request's `Reply:` directive, if present; that write is required by the relay protocol.

Answer the question directly. If it is too broad for one response, note the limitation and answer what you can.
```

After writing, read the file back with the Read tool to verify it contains all three sections completely. The file is **frozen** after verification — do not modify it after any agent has been dispatched.

### Launcher Templates

Launcher prompts are stored as committed template files in the `templates/` directory alongside this SKILL.md. Each template uses `{{PLACEHOLDER}}` slots filled by the `prism-launch` script at dispatch time (see "Dispatch via prism-launch" below). This ensures the "identical prompts" invariant is enforced mechanically — the boilerplate is never regenerated, only the lens-specific values are emitted.

**Template files:**

| File | Used for | Slots |
|------|----------|-------|
| `templates/launcher-subagent.tmpl` | Agent tool (same-model subagents) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |
| `templates/launcher-relay-codex.tmpl` | Bash relay, Codex (GPT `<goal>` style) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |
| `templates/launcher-relay-costar.tmpl` | Bash relay, any CO-STAR peer (DeepSeek, MiMo, Grok Build, Grok Composer) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |

There is **one relay template per prompting style**, not per peer — `prism-launch` selects it by the `template` field in the peer registry (`relay/peers.json`), so the byte-identical DeepSeek/MiMo/Grok launchers are a single shared `launcher-relay-costar.tmpl`. The Codex template uses `<goal>`, `<context>`, `<constraints>`, `<your_lens>` (the GPT-5.5 prompting guide); the CO-STAR template uses `<context>`, `<objective>`, `<constraints>`, `<your_lens>`, `<response_format>` (XML-tagged conventions that suit independent-lineage models). The subagent template uses plain markdown. The anti-recursion warning appears at the top of every template.

Adding a relay target model is **one stanza in `relay/peers.json`** (transport, endpoint, key var, model id, optional extras, and a `template` style). No `prism-launch` edit is needed — the peer set, counts, effort rules, and template selection all derive from the registry. Add a new template file only if the peer needs a genuinely new prompting style (then set its `template` to match); a CO-STAR peer reuses `launcher-relay-costar.tmpl`.

### Dispatch via prism-launch

You do **not** render templates or hand-write relay heredocs. The `prism-launch` script — installed at `~/.claude/skills/prism/scripts/prism-launch` — owns the cross-model half of dispatch: it renders every launcher from the templates, validates dispatch shape mechanically, and fans all relay calls out as **one** backgrounded process that waits for every peer and writes a single structured result. This is the documented dispatch path — it eliminates the per-call `sed`+heredoc token cost and makes the most common failure (dispatch-shape mismatch) structurally impossible.

**Invoke it by its absolute path** — `~/.claude/skills/prism/scripts/prism-launch` — not the bare name. The bare command is on PATH only when the shell inherited the `.zshenv`-injected PATH; a sandboxed/non-zsh/reset-env agent shell will not have it, and a bare-name miss must NOT trigger the manual fallback. The absolute path is the script's real install location, so its templates resolve correctly with no extra handling. (`prism-launch` resolves its sibling `relay` the same way — by install path, falling back to PATH — so `parallax` dispatches even when `relay` is not on PATH either.)

It cannot dispatch Claude subagents — only Claude can invoke the Agent tool, and `claude -p` is never used for Claude here (it is only relay's transport for DeepSeek/MiMo). So you still issue the subagent Agent-tool calls yourself.

**You write one line-oriented dispatch file with the Write tool** (one record per agent — never a shell heredoc), then run two commands. The dispatch format is plain `Key: value` lines in blank-line-separated records: no braces, commas, quoting, or escaping, so a free-text lens description can't break it the way hand-authored JSON can. Authoring the config as raw JSON is no longer the default — writing literal text with the Write tool is what removes the escaping surface.

Write `/tmp/prism-<id>.dispatch` with the **Write tool**:

```text
Shared-Packet: /tmp/prism-<id>.md

Type: parallax
To: codex
Name: adversarial
Effort: m
Lens: Adversarial
Lens-Desc: weigh the strongest attacks on the proposal

Type: parallax
To: grok-build
Effort: m
Lens: First-Principles
Lens-Desc: weigh how this looks rebuilt from the goal up

Type: parallax
To: grok-composer
Lens: Pragmatist
Lens-Desc: weigh the fastest workable path

Type: parallax
To: deepseek
Lens: Falsification
Lens-Desc: weigh what evidence would prove this wrong

Type: parallax
To: mimo
Lens: Outsider
Lens-Desc: weigh how a newcomer would approach this

Type: subagent
Lens: Simplicity
Lens-Desc: weigh the approach that requires the fewest moving parts
```

This is the canonical default — all six models at `N=1`, effort `m`. For an `xh` run, Codex's record carries `Effort: x` and Grok Build's `Effort: h`. (The dispatch file accepts the single-letter forms or the full words; `prism-launch` normalizes them — `x`→`xhigh`, `h`→`high`, `m`→`medium` — so the run-level `xh` flag becomes `Effort: x` on Codex and `Effort: h` on Grok Build, never `Effort: x` on Grok Build.)

Format rules: `Shared-Packet:` appears once. Each record starts at `Type: parallax|subagent`; blank lines separate records and `#` begins a comment. For `parallax`, `To:`/`Lens:`/`Lens-Desc:` are required, `Name:` is optional (defaults to the slugified lens), and `Effort:` is for peers with an effort knob — Codex (`m`/`medium` or `x`/`xhigh`) and Grok Build (`m`/`medium` or `h`/`high`); `-` or omitted = none — DeepSeek/MiMo/Grok Composer take none. For `subagent`, only `Lens:`/`Lens-Desc:` are needed. Everything after the **first** `:` is the literal value, so quotes, colons, `>`, `<`, and single braces in a description are fine — except the reserved tokens `</` and `{{` (the injection guard), which `prepare` rejects with a rephrase hint.

```bash
# 1) prepare (foreground): compiles the dispatch file into the canonical config,
#    validates packet/shape/effort/injection, renders all launchers, writes
#    <id>-manifest.json. Fails loudly if anything is off.
~/.claude/skills/prism/scripts/prism-launch prepare --dispatch /tmp/prism-<id>.dispatch

# 2) parallax (ONE backgrounded Bash call, run_in_background: true): fans out all
#    relay calls, waits for all, writes <id>-result.json with per-peer status.
#    (prepare prints this command with the same absolute path — copy it from there.)
~/.claude/skills/prism/scripts/prism-launch parallax /tmp/prism-<id>-manifest.json
```

`prepare` normalizes the dispatch file into `/tmp/prism-<id>-config.normalized.json` (the canonical JSON, kept for audit) before validating. **`prepare --config <config.json>` remains supported** as the machine/escape-hatch interface — it accepts that same JSON shape directly, also written with the Write tool (literal content, never a heredoc). Both paths run identical validation, rendering, and manifest logic; `--dispatch` is just a literal-text front-end that removes the JSON-escaping surface.

`prepare` prints the rendered subagent launcher file paths — pass each file's **contents** as the prompt of an Agent-tool call. It validates `lens`/`lens_desc` (rejecting `</` and `{{` as an injection guard; comparison operators like `>` are allowed), enforces distinct lens names and distinct relay `name`s, rejects `effort` on DeepSeek/MiMo/Grok Composer, and rejects a `shared_packet` path containing whitespace. `parallax` writes `<id>-result.json` (`{id, expected, succeeded, failed, results:[{to,name,status,res,log}]}`) and prints each peer's `.res.md` path; read those on completion (the `log` field is relay's own diagnostics for a failed peer — never relay's token-heavy `.log` sidecar). Use `~/.claude/skills/prism/scripts/prism-launch parallax <manifest> --dry-run` to preview the exact relay commands without dispatching. Per-peer timeout defaults to 1800s (`PRISM_PEER_TIMEOUT`; set `=0` to disable the per-peer cap, leaving only the outer Bash-tool timeout); set the backgrounded Bash call's `timeout` above that (e.g. `1860000`).

**Manual fallback (last resort — only if the script file is genuinely missing):** A bare-name "command not found" is NOT a trigger — re-invoke by the absolute path above. The manual flow applies only when `~/.claude/skills/prism/scripts/prism-launch` does not exist at all (a broken install). First try to repair the install (`cd ~/dotfiles && ./dotfiles.sh`); if that is not possible, render each launcher with `sed -e 's|{{SHARED_PACKET_PATH}}|...|g' -e 's|{{LENS_NAME}}|...|g' -e 's|{{LENS_DESC}}|...|g' templates/launcher-<kind>.tmpl`, then dispatch one `relay call --to <peer> --name prism-<slug> [--effort <medium|xhigh>]` heredoc per parallax tier (background each, `timeout: 1860000`). This is the degraded pre-`prism-launch` flow; prefer the script.

## Pre-Launch Checks

Run these checks before launching. If any fails, rewrite and re-check. **When dispatching via `prism-launch` (the default path), `prepare` enforces checks 1, 2, 5, and 6 mechanically and aborts on failure, and `parallax` enforces check 0 (relay availability) before dispatch — you still own the judgment checks 3 (redundancy) and 4 (lens quality), which require semantic reasoning a script cannot do.** The descriptions below remain authoritative for the manual fallback and for understanding what `prism-launch` verifies.

0. **Relay availability test (if any parallax tier > 0):** Run `command -v relay` to check if the relay command is in PATH. This is the sole test — do not glob for relay files or references to determine availability. If the command exists, relay is available.

1. **Shared-file test:** Verify the shared context file was written and read back successfully. Confirm every rendered launcher references the same absolute file path. The shared file must be frozen before any dispatch.

2. **Slot-completion test:** After rendering all launcher prompts via `sed`, verify no `{{` placeholder tokens survive: `grep -c '{{' rendered_launcher`. Also confirm the shared packet path is absolute and identical across all rendered prompts, and that the anti-recursion warning is the first line of every launcher. For relay prompts (Codex, DeepSeek, MiMo, Grok Build, Grok Composer), verify the XML skeleton is well-formed (`<context>`, `<objective>` or `<goal>`, `<constraints>`, `<your_lens>` tags present).

3. **Redundancy test:** Swap any two agents' lenses. If the prompts become incoherent, you have divided labor. This applies across tiers too — a Codex agent's lens and a DeepSeek agent's lens should be swappable in principle (only the prompt format differs).

4. **Lens quality test:** Each lens name must be a weighing posture (1-3 words), never a task or role. For each lens, write one sentence explaining what unique axis it covers that no other lens does. If two lenses would produce the same emphasis, replace one. **Adversarial coverage is opt-in, not default:** include a structurally adversarial lens (Adversarial, Falsification, Disconfirming, Risk, or similar) only when having one is *much more valuable* than spending that slot on another orthogonal lens — i.e., the answer turns on surfacing a non-obvious flaw, attack, or failure mode that no other lens is already covering. Before adding one, write one sentence naming the specific risk it exists to catch; if you can't, drop it and use an exploratory lens instead. This applies regardless of task category — a "risk-bearing" task (decision, design, code review, implementation, root-cause claim) does *not* automatically require an adversarial lens; judge whether stress-testing is the binding constraint for *this* question. **Conversely, the omission must also be deliberate:** if the task proposes, evaluates, or changes something and you include *no* adversarial-family lens, write one sentence naming which dispatched lens covers "what could go wrong." If none does, add one — it need not be a full Adversarial lens; a failure-mode-tilted variant of an exploratory lens (e.g., Depth-Weighted on failure modes) can suffice. Silent omission on such a task is a check failure, because an all-constructive dispatch can converge with false confidence when nothing was assigned to attack the proposal. Never assign the same lens to two of Codex, DeepSeek, MiMo, or the Grok tiers — that wastes a perspective. If you do include an adversarial lens and it carries the heaviest reasoning load on a subtle technical question, confirm it is assigned to Claude or Codex (`xhigh`) rather than a parallax tier — and if a parallax tier must take it, prefer MiMo over DeepSeek (see "Tier strength and lens fit" in Parallax).

5. **Dispatch-shape test (CRITICAL):** First resolve the config — every tier's count defaults to `N`, then apply any natural-language modifications (exclusions → `0`, per-tier counts). Total dispatched agents (Claude subagents + the five parallax tiers) must equal the resolved per-tier counts; self does not count. Enumerate planned calls by type — `--to codex`, `--to grok-build`, `--to grok-composer`, `--to deepseek`, `--to mimo` each equal to that tier's resolved count, and Agent calls equal to the resolved Claude-subagent count. The default symmetric run is `N` of each: `5N` relay calls + `N` Agent calls. If any count mismatches the resolved config, fix before launching. The most common failure is emitting fewer relay calls than the resolved parallax total.

6. **Effort test:** Confirm the run-level flag is applied to both tunable tiers — `m` → Codex `--effort medium` + Grok Build `--effort medium`; `xh` → Codex `--effort xhigh` + Grok Build `--effort high` (default `m`). Where a natural-language modification overrode a tier, confirm that tier uses the stated level instead. Honor the per-tier vocabularies: Codex is **only** `medium`/`xhigh` (reject `high`), Grok Build is **only** `medium`/`high` (reject `xhigh`). Never pass a raw `m`/`xh` flag to relay — map to the full word. DeepSeek, MiMo, and Grok Composer calls must NOT pass `--effort`. State the Codex and Grok Build effort being applied.

### Division-of-labor diagnostic

If any of these differ between agent prompts, you've divided labor: scope, evidence, tools, output format, or deliverables.

## Lens Assignment

A lens is a **weighing posture**, not a task variant. Do not put the task noun in the lens name.

Choose lenses on **orthogonal tradeoff axes**. Before adding one, write one sentence explaining how it differs from every existing lens. If you cannot name a distinct axis, do not add it. The symmetric default dispatches six agents (one per model), so aim for **six distinct postures**; if the task can't support that many, exclude a tier via natural language rather than giving two agents the same lens. At `N ≥ 2` (multiple agents per model), give each copy a distinct lens where the task supports it; deliberate same-*posture* redundancy to reduce variance on a pivotal question is allowed, but each agent still needs a **distinct lens name** (e.g. `Adversarial-A` / `Adversarial-B`) — `prism-launch` rejects duplicate names. Note that `N=1` gives only one Claude subagent slot: when a risk-bearing question wants its adversarial lens on Claude or Codex (Check #4), either accept it on Codex at `xh`, bump `N`, or exclude a Parallax tier via NL to free a Claude slot.

**`Disconfirming` vs `Disconfirming-via-different-frame`:** these are not interchangeable. `Disconfirming` is adversarial — it directly attacks a specific claim and is subject to the opt-in gate in the Lens quality test. `Disconfirming-via-different-frame` is exploratory — its value is an alternate prior or framing, not stress-testing — so it counts as an orthogonal default, not the adversarial slot. Do not relabel an attack posture as a frame to evade the opt-in gate.

### Suggested lenses by task type

Starting points — every lens still answers the full question. These are 3-lens cores; the symmetric default dispatches **six** agents, so extend each set to six distinct postures with orthogonal exploratory lenses (Outsider, First-Principles, Depth-Weighted, Breadth-Weighted, Disconfirming-via-different-frame). The adversarial slot (italicized below) is a *candidate*, not a default: keep it only if stress-testing is the binding constraint for this specific question (see Lens quality test); otherwise replace it with an orthogonal exploratory lens.

- **Code review**: Correctness + Simplicity + *Adversarial*
- **Architecture / design**: Evolutionary + Simplicity + *Adversarial*
- **Implementation**: Correctness + Pragmatist + *Adversarial*
- **Diagnosis / root cause**: Causal + *Falsification* + *Risk*
- **Option comparison**: Simplicity + Feasibility + *Disconfirming*
- **Writing / communication**: Clarity + Audience + *Adversarial*
- **Research / exploration**: Breadth-Weighted + Depth-Weighted + Outsider (add *Disconfirming* only if there's a specific claim to stress-test)
- **Decision / strategy**: First-Principles + *Disconfirming* + Expansionist + Outsider + Executor

## Execution

### Step 1: Freeze context, compose, verify, launch

1. Build one canonical shared packet (Full Question + Context + Constraints). Write it to `/tmp/prism-<unique-id>.md` with the Write tool.
2. Assign lenses (run the redundancy and lens-quality checks — these are yours to judge), then write the line-oriented dispatch file (`/tmp/prism-<id>.dispatch`) with the Write tool — `Shared-Packet:` plus one record per parallax peer and per subagent. See "Dispatch via prism-launch". (The `--config` JSON form is still accepted as an escape hatch.)
3. **`~/.claude/skills/prism/scripts/prism-launch prepare --dispatch /tmp/prism-<id>.dispatch`** (foreground). This compiles the dispatch file into the canonical config, validates the packet and records its path (it does not copy or hash it — do not mutate the packet after this point), renders all launchers, runs checks 1/2/5/6, and writes `<id>-manifest.json`. If it exits non-zero, fix the dispatch file and re-run — nothing has been dispatched.
4. Launch all dispatched agents concurrently (`run_in_background: true`). **Dispatch checklist:**
   - **Parallax — ONE backgrounded Bash call:** `~/.claude/skills/prism/scripts/prism-launch parallax /tmp/prism-<id>-manifest.json` (set the Bash tool `timeout` above `PRISM_PEER_TIMEOUT`, e.g. `1860000`). This fans out every Codex/DeepSeek/MiMo/Grok call, waits for all, and yields a single completion notification. Compose this call FIRST.
   - **Subagents:** one **Agent** tool call per subagent, using the contents of the rendered launcher file (`prepare` printed the paths) as the prompt. Never use `claude -p` for these.
   - The manifest's `counts` is the authoritative dispatch shape — there is no per-relay-call count to reconcile by hand, because `prism-launch` emits exactly the configured calls.

Do not poll or sleep-loop — the system notifies you when agents finish. (A bare-name "command not found" is not a fallback trigger — invoke by the absolute path above. The manual `sed`+heredoc flow applies only if the script file is genuinely missing, per "Manual fallback" above.)

### Step 2: Self-review

While agents run, form your own position independently. Your lens is **Integrator Lens** — you weigh holistic coherence, feasibility, and alignment with the user's goals. Write your tentative recommendation before opening any agent output.

Since you composed the prompts and chose the lenses, your self-review is not fully independent. When dispatched agents diverge from your position, give their perspectives slightly more weight on points you may have anchored on during prompt design.

### Step 3: Wait for ALL agents (HARD GATE)

**Do not synthesize, summarize, or present results until EVERY dispatched agent — including all Parallax tiers — has returned.** This is a hard gate, not a suggestion. Having "enough" subagents is never a reason to skip the remaining agents. The whole point of Parallax is model diversity — proceeding without it defeats the purpose of Prism. One peer finishing first (Codex, DeepSeek, MiMo, or Grok) is never permission to ignore the others.

**Parallax is slow — that is normal and expected.** Relay calls routinely take 2-5x longer than same-model subagents. DeepSeek calls (always at DeepThink `max`), MiMo calls, Grok Build calls at `--effort high`, and Codex calls at `--effort xhigh` are the slowest. Do not diagnose, retry, report failure, or proceed while a background task is running. With `prism-launch parallax`, **all parallax peers finish under a single completion notification** (the fan waits for every peer before signaling) — so a default `N=1` run yields 2 notifications: the one subagent plus the whole parallax batch (higher `N` adds one per extra subagent). Until both the parallax notification and every subagent notification have arrived, the run is healthy. Do not tell the user you are "still waiting" or suggest proceeding without any tier.

**What to do while waiting:** Work on your self-review (Step 2). If self-review is done, wait silently. Do not synthesize partial results.

**Handling failures (after completion notification only):**

- **Relay transport failure:** After the parallax notification, read `<id>-result.json` — any peer with `status: "error"` failed. Retry just that peer with a single `relay call --to <peer> --name prism-<slug> [--effort ...] < <its launcher file>` (do not re-run the whole fan). Check the Bash output for the diagnosed cause; do not read the `.log` sidecar — it is extremely long and token-heavy.
- **Answer-quality failure** (empty, truncated, off-topic): Offer the user: (a) retry, (b) proceed with reduced perspectives, or (c) abort.
- **Only these post-notification failures justify proceeding without Parallax.** "It's taking a long time" is never a failure.

### Step 3.5: Safety check

Before synthesizing, verify no dispatched agent modified the working tree:

```bash
git diff --stat HEAD
```

If the diff shows unexpected changes, flag them to the user before proceeding. Discard the offending agent's output — an agent that violated read-only constraints may have reasoned from a corrupted state.

Scan each agent's output for recursion indicators: mentions of "dispatching," "subagent," "relay call," "Prism run," or synthesis-style structure (a `▶` verdict line, a model-tier tally, `Dissent:`/`Why:`/`Do now:` sections, or older `Consensus/Contested/Unique` sections). Flag matches for review — the agent may have spawned nested agents, producing contaminated reasoning.

### Step 4: Synthesize

Write a skim-first, verdict-led synthesis, not a lens-by-lens report. The user should grasp the recommendation in seconds, not minutes.

**Default budget: ~100-150 words in the visible main path.** If you're writing more, you're hedging or scaffolding — compress. Deliverables are bounded by the artifact; the optional appendix is uncounted.

The reader should grasp the recommendation, confidence, and any cross-model dissent in the first ~3 seconds, then read on only for the reasoning. The verdict line carries the first three; the body carries the reasoning.

**Default skeleton — the verdict line is fixed and always first; the body below it flexes by mode (see Mode adaptation):**

1. **Verdict line** — one line, the first thing the eye hits. Fixed token order, `·`-separated:

   `▶ <verdict, aim ≤12 words> · conf: <High|Moderate|Low> · <n>/<total> agree[ · ⚠ dissent]`

   - `<n>/<total>` counts **perspectives that returned, including self** (the default `N=1` run is `/7`: self + 6 dispatched) — *not* dispatched-only, *not* lineages. The tally below counts *lineages*; the two denominators intentionally differ. (Self is a perspective here even though it does not count toward *dispatch* shape elsewhere.)
   - For an **exploratory question** with no proposition to vote on, swap `<n>/<total> agree` for `<n>/<total> aligned` (or `· converging` / `· divergent`) and let `▶` state the synthesized finding rather than a recommendation. Confidence is still shown.
   - Confidence is **always shown** — the *absence* of a `⚠ dissent` clause is itself the all-clear signal.
   - The `⚠ dissent` clause appears **only** when a dispatched agent dissents. On a cross-model break the tally and Dissent line already name the peers, so the verdict clause stays a bare `⚠ dissent`; name a peer inline (`⚠ DeepSeek dissent`) only for a minor dissent that has no tally. `⚠` is the only routine glyph — reserve it for dissent; never decorate confidence or the verdict with emoji or boxes.
   - Deliverable: the verdict line points at the artifact (`▶ See migration plan below · conf: High · 7/7 agree`), which follows immediately.

2. **Model-tier tally** — one line, **only on a cross-model break** (a parallax lineage dissents). Group by model lineage (not by lens): each dispatched lineage with `✓` (aligned) or `⚠` (dissented), then the takeaway.

   `Claude ✓  Codex ✓  DeepSeek ⚠  MiMo ⚠   → 2 independent lineages dissent, same direction`

   Omit on full convergence (all `✓` — the header's `n/n agree` already says so) and on an intra-lineage split (a by-lineage tally cannot show a split *inside* one lineage — use the `Tradeoff:` line instead). List only the lineages actually dispatched (treat the two Grok tiers as one `Grok` lineage). A lineage that ran several agents collapses to one `✓`/`⚠`: mark `⚠` if **any** member raised a cross-model dissent you could not refute (a lineage's dissent is never averaged away by its other members agreeing), and resolve its aligned position by strongest reasoning, not majority vote. This tally is the **one sanctioned exception** to the per-lens-attribution ban below: it attributes by *lineage* (the load-bearing cross-model signal), never lens-by-lens.

3. **Dissent** — its own labeled line **on a cross-model break**, placed above Why: the peer(s), the *specific* argument, and what would resolve it ("DeepSeek+MiMo: shared state needed for atomic txns — bounded by the spike gate; revisit if p99 > 50ms"). When dissent is minor, fold it into a Why bullet instead. Never compress dissent to a bare model name — the argument and its resolution path are the signal.

4. **Why** — 2-4 tight bullets of decisive reasoning. Each bullet is conclusion **plus** its basis ("Removes the shared-state layer — root cause of 3/5 recent incidents"), never a bare label ("simpler"). Fold confidence basis in when it helps.

5. **Do now** — 1-3 verb-first actions, often a single arrow chain (`spike B → kill the A RFC → freeze schema`). Skip if the verdict is itself the action.

**Mode adaptation (the verdict line never moves; the body flexes):**

| Mode | Tally | Dissent line | Body |
|------|-------|--------------|------|
| **Converged** — all perspectives agree | omit | omit | Why (+ Do now). Often 3-5 lines total. |
| **Material disagreement** — ≥2 agents oppose on the core question (not peripheral caveats), not following lineage cleanly | omit | fold into Why | `Tradeoff:` (the two options + what each optimizes) before Do now |
| **Cross-model break** — subagents converge, a parallax lineage dissents | **mandatory** | **leads the body**, above Why | cap confidence at Moderate |
| **Deliverable** | per the run | per the run | artifact right after the verdict line; Why = design rationale; Do now = integration/review |

- On a **cross-model break**, two or more parallax peers (Codex, DeepSeek, MiMo, Grok) dissenting in the *same direction* is an especially strong signal — say so. The Moderate cap fires only when a *parallax* lineage dissents.
- **All-subagent run** (no parallax dispatched — e.g. every cross-model tier excluded via natural language): a cross-model break is impossible, so within-Claude splits are **Material disagreement** however clean the split looks — no tally, no Moderate cap. Flag the missing cross-model diversity, since the `⚠`-absence all-clear cannot mean cross-model corroboration here.

**Banned in the main path:**

- Per-lens attribution ("the Simplicity lens noted…", "Agent A said…"). The model-tier **tally line is the sole exception** (by lineage, not lens). Deeper per-lens notes go in an optional `<details>Per-lens detail</details>` appendix at the very bottom — only if the user asked, or disagreement is deep enough to need a lens-level audit.
- Synthesis narration ("Weighing the perspectives…", "After considering the arguments…"). The verdict line and Why carry the reasoning.
- Generic contingencies ("if requirements change"). Only concrete, observable triggers.
- Routine chrome: emoji beyond the reserved `⚠`, ASCII-art boxes, traffic-light symbols. Use words for confidence; `▶` for the verdict line; `✓`/`⚠` in the tally. A plain `→` (or `then`) as a prose separator in a Do-now chain or a tally takeaway is fine — it is text, not chrome.
- Standalone `Confidence and basis` / `Key dissent` / `Contingencies` sections. Their content folds into the verdict line, Dissent line, and Why — and only when decision-relevant.

**Cross-model weighting (internal — surfaces through the verdict line, tally, and Why):**

- **Not all answers are equally good — judge each on its merits and reject the weak ones.** Running the assigned lens does not guarantee a sound answer: an agent can produce shallow reasoning, a wrong premise, a misread of the question, or a confident claim with no support. The integrator's job is to *identify and discard* those answers, not to average every response together. Weight by the strength of an answer's reasoning and evidence, not by the fact that an agent produced it (discount weak reasoning, never the model label). Dropping a low-quality answer entirely is a valid, expected outcome — say so in Why when a notable perspective was set aside.
- Same-model convergence is signal but discounted — shared training = shared blind spots.
- Parallax (cross-model) confirmation or dissent carries outsized weight — model diversity is prism's entire point.
- A single well-reasoned point can beat multi-agent consensus driven by shared priors.

If you cannot articulate why dissent is wrong, downgrade confidence on the verdict line rather than expanding dissent into a paragraph.

The synthesis reflects your judgment as integrator — agents are advisors, not a voting bloc. The tally line shows lineage alignment; it does not cast votes that decide the answer. Convergence is evidence, not a vote.

### Step 5: Grounding check

Re-read the user's original question. Verify:

- Your synthesis answers it directly. If they asked for a deliverable, you produced one.
- The verdict line leads, in fixed token order (`▶ verdict · conf: … · n/total agree[ · ⚠ dissent]`), and confidence is shown.
- On a cross-model break, the tally line and a dedicated Dissent line are present and sit above Why; on a material disagreement a `Tradeoff:` line carries the split (no tally); on full convergence all three are omitted.
- No per-lens summary appears in the main path — the model-tier tally is by lineage, not lens; lens-by-lens notes live only in an optional appendix.
- Every retained dissent, caveat, or trigger changes a decision, confidence level, or next action.

Optionally delete all Prism temp files — they share the `/tmp/prism-<unique-id>` prefix: shared context (`.md`), dispatch file (`.dispatch`), normalized/config JSON (`-config*.json`), manifest, rendered launchers (`-launcher-*.md`), parallax out logs (`-out-*.log`), and result sentinel (`-result.json`). A single `rm -f /tmp/prism-<unique-id>*` covers them.

## Guards

- **No recursion (HARD RULE):** Dispatched agents must never spawn child agents or invoke any dispatching skill (prism, relay, gpt-pro-relay, deep-research, or any cross-model dispatch tool). Read-only analysis skills are permitted. The Constraints section and launcher prompts both enforce this — do not weaken or omit either. For Parallax, keep the anti-recursion warning at the top of every heredoc (Codex, DeepSeek, MiMo, Grok launchers).
- **No contamination:** Write the shared context file and compose all launcher prompts before any launch. Do not modify the shared file or revise prompts after seeing early agent outputs.
- **No all-same-model dispatch (HARD RULE):** The dispatched parallax peers must equal the resolved parallax counts — `5N` by default (`N` each of Codex, Grok Build, Grok Composer, DeepSeek, MiMo), minus any tier excluded by natural language. Via `prism-launch`, the manifest's `counts` derives this from the config, and the single `parallax` call emits exactly those peers — so the historical "forgot a relay call" failure cannot occur. In the manual fallback, the total count of Bash relay calls must equal that sum; if the planned dispatch has zero relay calls but any configured count is non-zero, fix before launching.
- **No early synthesis (HARD RULE):** Do not synthesize until every dispatched agent has returned its completion notification. "Subagents are done, Codex relay is still running" or "Codex came back, DeepSeek is still running" are not reasons to proceed — they are the expected state. Proceeding without any tier's results voids the entire Prism run.
- **No side effects:** Dispatched agents must not edit files, commit, push, or invoke any skill with side effects (e.g., push, xurl, todo, goal-drive). Read-only analysis skills are allowed. The only permitted write is the relay response file (.res.md).

## Degrees of Freedom

The core principle (redundancy, not division of labor), the prompt template structure, and the hard completion gate are load-bearing constraints — do not relax them. Everything else — lens choices, synthesis categories, agent count beyond the minimum, pre-launch check order — is flexible guidance that you should adapt to the task.

**Synthesis adaptation:** The verdict line is fixed (always first, fixed token order — see Step 4); the body below it (tally, Dissent, Why, Do now) flexes to the task. The integrator should actively adapt the body frame when the task calls for it — merge sections, reorder, or add task-specific sections. A deliverable question puts the artifact immediately after the verdict line with design rationale behind it; a pure risk assessment might elevate the Dissent line and triggers above Why. Rigid adherence to the body structure when it doesn't fit the question is a failure of integration — but the verdict line stays put regardless, so the reader's first-glance scan always works.

## When to Use Prism

Use Prism when a task benefits from diverse, redundant judgment and the shared context fits cleanly across all agents.

Skip Prism for trivial lookups, deterministic transforms, single-correct-answer tasks, or tasks requiring parallel mutations of shared state.
