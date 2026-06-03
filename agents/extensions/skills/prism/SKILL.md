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

**Claude-only.** If `ANTHROPIC_BASE_URL` contains `deepseek`, `xiaomimimo`, or `moonshot`, this skill is unavailable — stop and tell the user: "prism is Claude-only; a non-Claude session cannot orchestrate other models." Prism dispatches parallax via [[relay]], which itself refuses from non-Claude sessions.

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
| **Parallax — DeepSeek** | **Bash** (`relay call --to deepseek`) | Cross-model agents via relay to DeepSeek V4 Pro |
| **Parallax — MiMo** | **Bash** (`relay call --to mimo`) | Cross-model agents via relay to Xiaomi MiMo-V2.5-Pro |
| **Parallax — Kimi** | **Bash** (`relay call --to kimi`) | Cross-model agents via relay to Moonshot Kimi-K2.6 |

**Default: 7 perspectives** — self + 2 subagents + 1 Codex parallax + 1 DeepSeek parallax + 1 MiMo parallax + 1 Kimi parallax. Required dispatch: **2 Agent calls + 1 backgrounded `prism-launch parallax` call that fans out the 4 relay calls** (manual fallback: 4 separate Bash relay calls). Self does not count. All four Parallax tiers are included by default; opt out of any tier individually by setting its count to `0`.

### Invocation Shorthand

Override dispatch config with positional args before the question, or use natural language — both work.

**Positional:** `<sub> <codex-count> <codex-effort> <ds-count> <mm-count> <k-count> <question>`
- **sub** — number of same-model (Claude) subagents (default: 2)
- **codex-count** — number of Codex parallax agents (default: 1, `0` to opt out)
- **codex-effort** — Codex reasoning effort: `m` medium, `x` xhigh (default: `m`)
- **ds-count** — number of DeepSeek parallax agents (default: 1, `0` to opt out). DeepSeek always runs at `max` (DeepThink) — no effort knob.
- **mm-count** — number of MiMo parallax agents (default: 1, `0` to opt out). MiMo has no effort knob.
- **k-count** — number of Kimi parallax agents (default: 1, `0` to opt out). Kimi has no effort knob.

**Omission rule:** Positions fill left-to-right and you may stop at any point; remaining positions take their defaults. You cannot skip a position — to reach `k-count`, you must specify the five preceding positions (`sub`, `codex-count`, `codex-effort`, `ds-count`, `mm-count`). When `codex-count` is `0`, the following effort token is still consumed positionally (so the next digit lands in the right slot) and then ignored.

Examples:
- `prism 2 2 x 2 2 2 Which architecture should we pick?` — 2 sub, 2 Codex (xhigh), 2 DeepSeek (max), 2 MiMo, 2 Kimi
- `prism 3 2 x 1 1 1 Why does X happen?` — 3 sub, 2 Codex (xhigh), 1 DeepSeek (max), 1 MiMo, 1 Kimi
- `prism 1 0 m 1 0 0 Same-model + DeepSeek` — 1 sub, no Codex, 1 DeepSeek (max), no MiMo, no Kimi
- `prism 2 0 m 0 0 0 Solo-claude only` — 2 sub, no parallax at all (degraded — flag to user)
- `prism Why does X?` — all defaults: 2 sub, 1 Codex (medium), 1 DeepSeek (max), 1 MiMo, 1 Kimi
- `prism 3 Why does X?` — 3 sub, defaults for all four parallax tiers (omission rule: trailing positions take defaults)
- `prism 3 sub, 2 codex xhigh, 1 deepseek, 1 mimo, 1 kimi: Why does X?` — natural language works too

**Parsing:** Read tokens left-to-right. A token is config if it is a single digit or an effort letter (`m`/`x`). Map positionally in this order: digit → sub-count, digit → codex-count, letter → codex-effort, digit → ds-count, digit → mm-count, digit → k-count. The first non-matching token begins the question. Reject effort letters outside `{m, x}` with: "Codex effort must be m or x." Natural language config is also accepted.

**Every run with `codex-count > 0` MUST include that many Bash relay calls to Codex; every run with `ds-count > 0` MUST include that many to DeepSeek; every run with `mm-count > 0` MUST include that many to MiMo; every run with `k-count > 0` MUST include that many to Kimi.** Do not skip, replace with a subagent, or defer. Exceptions: (1) user explicitly set the tier's count to `0`, or (2) `relay` is unavailable (substitute a same-model agent carrying that tier's assigned lens and warn the user about degradation). The dispatch-shape check verifies the counts before launch (Pre-Launch Check #5).

### Parallax (cross-model agents)

Parallax is dispatched via `relay` to **different models** (Codex, DeepSeek, MiMo, and/or Kimi). Invoke `relay` directly — not via a subagent that calls relay. The value of each tier is model diversity:

- **Codex** brings GPT-5.5's training, its strengths in agentic code review, and two effort tiers (`medium`/`xhigh`).
- **DeepSeek** brings an entirely independent training lineage (open-weight V4-Pro), distinct prompting conventions, and always runs at `max` (DeepThink).
- **MiMo** brings a third independent lineage (Xiaomi's open-weight MiMo-V2.5-Pro, 1.02T MoE / 42B active, 1M context), distinct again from both the Anthropic and OpenAI families. No effort knob.
- **Kimi** brings a fourth independent lineage (Moonshot AI's Kimi-K2.6, a frontier agentic-coding MoE), distinct again from the Anthropic, OpenAI, DeepSeek, and Xiaomi families. Thinking is on by default; no effort knob (binary on/off only).

**Tier strength and lens fit (heuristic, not a routing rule):** Claude Opus 4.7 (subagents) and GPT-5.5 (Codex) are roughly peers in raw reasoning capability and sit at the top. The independent-lineage parallax tiers — MiMo-V2.5-Pro, DeepSeek V4-Pro, and Kimi-K2.6 — are each meaningfully weaker on hard reasoning at peak effort, with MiMo slightly ahead of DeepSeek; Kimi-K2.6 is new here and unbenchmarked, so treat its placement as provisional (the vendor positions it as frontier — verify before trusting it with the heaviest-reasoning lens). The rough ranking is **Claude ≈ Codex > {MiMo ≳ DeepSeek, Kimi provisional}**. This does *not* reduce the weaker tiers' value — each independent training lineage catches blind spots the others share, which is the entire point of model diversity. The asymmetry should inform lens assignment only:

- **Subtle hard-reasoning lenses on risk-bearing questions** (Adversarial / Falsification / Disconfirming on a technical proposal where finding the non-obvious attack is the deliverable): prefer Claude subagent or Codex at `--effort xhigh`. If exactly one lens carries the heaviest reasoning load and it lands on a parallax tier, you've under-resourced the most decision-relevant role; when it must land on one anyway, prefer MiMo over DeepSeek.
- **Lenses where the value is a different prior** (Outsider, First-Principles, Disconfirming-via-different-frame, Breadth-Weighted, Risk, Alternative-Framing): give these to DeepSeek, MiMo, and Kimi. Their independent lineages are the asset; raw reasoning depth is not the bottleneck.
- **Parallax lenses comparably hard:** no swap needed.
- **Never drop DeepSeek, MiMo, or Kimi to "upgrade" a run.** Lineage diversity is non-substitutable; default tier inclusion is unchanged.

This affects assignment only. In synthesis, DeepSeek, MiMo, and Kimi dissent retain full cross-model weight — discount weak reasoning, never the model label. Treat the ranking as approximate; revisit when model versions change (the named model versions above are the canary — when they look stale, this section is stale).

Assign each tier a lens that maximizes diversity. **Default to orthogonal exploratory lenses** (Breadth-Weighted, Depth-Weighted, Outsider, First-Principles, Disconfirming-via-different-frame) — these almost always extract more from cross-model diversity than a second attack angle. **Reach for an adversarial lens (Adversarial, Falsification, Disconfirming) only when it is much more valuable than another orthogonal lens would be** — i.e., the deliverable hinges on finding a non-obvious flaw, attack, or failure mode, and no other dispatched lens is already covering that ground. When that bar is met, put it on the parallax tier best suited to the reasoning load (see "Tier strength and lens fit"); otherwise skip it. When using multiple parallax tiers, give each a distinct lens — never assign the same lens to two of Codex, DeepSeek, MiMo, or Kimi (that wastes a perspective), and don't stack two adversarial lenses unless the task genuinely demands independent attack frames.

Before writing any Parallax relay prompt, follow the per-peer prompting guidance in the [[relay]] skill — its **Prompting Codex** section (which directs you to the `gpt.md` + `codex.md` references) and **Prompting DeepSeek** section (which directs you to `deepseek.md`, including the repo-copy fallback if the symlinks are unavailable). Read those references before composing the prompt body, every time — not just once.

**Relay call syntax (exact)** — the command shapes Prism must emit:

```bash
# Codex parallax
relay call --to codex --name <slug> --effort <medium|xhigh> <<'BODY'
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

# Kimi parallax (no --effort — no effort knob)
relay call --to kimi --name <slug> <<'BODY'
<prompt content here>
BODY
```

Use a lowercase slug for `--name` (e.g., `prism-adversarial`), and never pass `--effort` or model flags on DeepSeek, MiMo, or Kimi (none has an effort knob). For all other invocation rules — `--name` required, `--to codex` as the default, non-empty heredoc, no model flags — follow the [[relay]] skill rather than restating them. For concurrency (backgrounding, timeouts), follow relay's Async / Parallel section.

**Inspecting Parallax results:** Only read the `.res.md` response file. Never read the `.log` sidecar — it contains the peer's full stderr, which is extremely long and token-heavy. The relay script's Bash output already surfaces diagnostic information for failure cases.

If `relay` is unavailable, replace all Parallax tiers with same-model subagents and warn the user. Each substitute carries the lens that tier was already assigned under the opt-in rule above — do not re-decide by task category. Relay being unavailable does not change whether adversarial coverage is valuable for this question.

**Constraint leakage risk (CRITICAL):** Relay peers may recurse unless the anti-recursion rule is explicit, early, and repeated. You MUST:
1. Put the anti-recursion warning at the top of every launcher prompt, before the file-read instruction.
2. Preserve the Constraints section verbatim in the shared context file — do not summarize or abbreviate.
3. Ensure the prohibition appears in both each launcher (short form) and the shared file (full form).
4. Tell each peer to ignore loaded skill descriptions for the dispatching/side-effecting skills (prism, relay, gpt-pro-relay, deep-research) — read-only analysis skills stay available.

Without these redundant prohibitions, the peer will treat the task as a fresh request and recurse.

**Effort selection for Parallax:** If the user specified `codex-effort` in the shorthand, map it to the relay flag value: `m` → `--effort medium`, `x` → `--effort xhigh`. Otherwise, pick the Codex effort by lens. DeepSeek, MiMo, and Kimi have no effort knob — every DeepSeek call runs at `max`, and MiMo and Kimi calls take no effort flag at all.

Codex parallax (`--effort` accepts `medium`/`xhigh`):

| Lens type | `--effort` | Rationale |
|-----------|-----------|-----------|
| Adversarial, Falsification, Disconfirming | `xhigh` | Needs deep reasoning to find subtle flaws |
| Everything else | `medium` | Balanced default; deeper reasoning adds latency without proportional quality gain |

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
- Invoke any skill that dispatches to, relays to, or coordinates another agent or model (prism, relay, gpt-pro-relay, deep-research), or call the codex CLI, the deepseek (ds/dsh), mimo (mm), or kimi (k) aliases, or any cross-model dispatch tool.
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
| `templates/launcher-relay-costar.tmpl` | Bash relay, any CO-STAR peer (DeepSeek, MiMo, Kimi) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |

There is **one relay template per prompting style**, not per peer — `prism-launch` selects it by the `template` field in the peer registry (`relay/peers.json`), so the byte-identical DeepSeek/MiMo/Kimi launchers are a single shared `launcher-relay-costar.tmpl`. The Codex template uses `<goal>`, `<context>`, `<constraints>`, `<your_lens>` (the GPT-5.5 prompting guide); the CO-STAR template uses `<context>`, `<objective>`, `<constraints>`, `<your_lens>`, `<response_format>` (XML-tagged conventions that suit independent-lineage models). The subagent template uses plain markdown. The anti-recursion warning appears at the top of every template.

Adding a relay target model is **one stanza in `relay/peers.json`** (transport, endpoint, key var, model id, optional extras, and a `template` style). No `prism-launch` edit is needed — the peer set, counts, effort rules, and template selection all derive from the registry. Add a new template file only if the peer needs a genuinely new prompting style (then set its `template` to match); a CO-STAR peer reuses `launcher-relay-costar.tmpl`.

### Dispatch via prism-launch

You do **not** render templates or hand-write relay heredocs. The `prism-launch` script — installed at `~/.claude/skills/prism/scripts/prism-launch` — owns the cross-model half of dispatch: it renders every launcher from the templates, validates dispatch shape mechanically, and fans all relay calls out as **one** backgrounded process that waits for every peer and writes a single structured result. This is the documented dispatch path — it eliminates the per-call `sed`+heredoc token cost and makes the most common failure (dispatch-shape mismatch) structurally impossible.

**Invoke it by its absolute path** — `~/.claude/skills/prism/scripts/prism-launch` — not the bare name. The bare command is on PATH only when the shell inherited the `.zshenv`-injected PATH; a sandboxed/non-zsh/reset-env agent shell will not have it, and a bare-name miss must NOT trigger the manual fallback. The absolute path is the script's real install location, so its templates resolve correctly with no extra handling. (`prism-launch` resolves its sibling `relay` the same way — by install path, falling back to PATH — so `parallax` dispatches even when `relay` is not on PATH either.)

It cannot dispatch Claude subagents — only Claude can invoke the Agent tool, and `claude -p` is never used for Claude here (it is only relay's transport for DeepSeek/MiMo/Kimi). So you still issue the subagent Agent-tool calls yourself.

**You write one compact config JSON** (instead of N `sed` renders), then run two commands:

```bash
# config: shared_packet path + one entry per parallax peer + one per subagent.
# (effort is codex-only: medium|xhigh. deepseek/mimo/kimi take no effort.)
cat > /tmp/prism-<id>-config.json <<'CFG'
{
  "shared_packet": "/tmp/prism-<id>.md",
  "parallax": [
    {"to":"codex","name":"adversarial","effort":"xhigh","lens":"Adversarial","lens_desc":"weigh the strongest attacks on the proposal"},
    {"to":"deepseek","name":"falsification","lens":"Falsification","lens_desc":"weigh what evidence would prove this wrong"},
    {"to":"mimo","name":"outsider","lens":"Outsider","lens_desc":"weigh how a newcomer would approach this"},
    {"to":"kimi","name":"first-principles","lens":"First-Principles","lens_desc":"weigh what the fundamentals imply ignoring convention"}
  ],
  "subagents": [
    {"lens":"Simplicity","lens_desc":"weigh the approach that requires the fewest moving parts"},
    {"lens":"Correctness","lens_desc":"weigh correctness guarantees and edge cases"}
  ]
}
CFG

# 1) prepare (foreground): validates packet/shape/effort/injection, renders all
#    launchers, writes <id>-manifest.json. Fails loudly if anything is off.
~/.claude/skills/prism/scripts/prism-launch prepare --config /tmp/prism-<id>-config.json

# 2) parallax (ONE backgrounded Bash call, run_in_background: true): fans out all
#    relay calls, waits for all, writes <id>-result.json with per-peer status.
#    (prepare prints this command with the same absolute path — copy it from there.)
~/.claude/skills/prism/scripts/prism-launch parallax /tmp/prism-<id>-manifest.json
```

`prepare` prints the rendered subagent launcher file paths — pass each file's **contents** as the prompt of an Agent-tool call. It validates `lens`/`lens_desc` (rejecting `</` and `{{` as an injection guard; comparison operators like `>` are allowed), enforces distinct lens names and distinct relay `name`s, rejects `effort` on DeepSeek/MiMo/Kimi, and rejects a `shared_packet` path containing whitespace. `parallax` writes `<id>-result.json` (`{id, expected, succeeded, failed, results:[{to,name,status,res,log}]}`) and prints each peer's `.res.md` path; read those on completion (the `log` field is relay's own diagnostics for a failed peer — never relay's token-heavy `.log` sidecar). Use `~/.claude/skills/prism/scripts/prism-launch parallax <manifest> --dry-run` to preview the exact relay commands without dispatching. Per-peer timeout defaults to 1800s (`PRISM_PEER_TIMEOUT`; set `=0` to disable the per-peer cap, leaving only the outer Bash-tool timeout); set the backgrounded Bash call's `timeout` above that (e.g. `1860000`).

**Manual fallback (last resort — only if the script file is genuinely missing):** A bare-name "command not found" is NOT a trigger — re-invoke by the absolute path above. The manual flow applies only when `~/.claude/skills/prism/scripts/prism-launch` does not exist at all (a broken install). First try to repair the install (`cd ~/dotfiles && ./dotfiles.sh`); if that is not possible, render each launcher with `sed -e 's|{{SHARED_PACKET_PATH}}|...|g' -e 's|{{LENS_NAME}}|...|g' -e 's|{{LENS_DESC}}|...|g' templates/launcher-<kind>.tmpl`, then dispatch one `relay call --to <peer> --name prism-<slug> [--effort <medium|xhigh>]` heredoc per parallax tier (background each, `timeout: 1860000`). This is the degraded pre-`prism-launch` flow; prefer the script.

## Pre-Launch Checks

Run these checks before launching. If any fails, rewrite and re-check. **When dispatching via `prism-launch` (the default path), `prepare` enforces checks 1, 2, 5, and 6 mechanically and aborts on failure, and `parallax` enforces check 0 (relay availability) before dispatch — you still own the judgment checks 3 (redundancy) and 4 (lens quality), which require semantic reasoning a script cannot do.** The descriptions below remain authoritative for the manual fallback and for understanding what `prism-launch` verifies.

0. **Relay availability test (if any parallax tier > 0):** Run `command -v relay` to check if the relay command is in PATH. This is the sole test — do not glob for relay files or references to determine availability. If the command exists, relay is available.

1. **Shared-file test:** Verify the shared context file was written and read back successfully. Confirm every rendered launcher references the same absolute file path. The shared file must be frozen before any dispatch.

2. **Slot-completion test:** After rendering all launcher prompts via `sed`, verify no `{{` placeholder tokens survive: `grep -c '{{' rendered_launcher`. Also confirm the shared packet path is absolute and identical across all rendered prompts, and that the anti-recursion warning is the first line of every launcher. For relay prompts (Codex, DeepSeek, MiMo, and Kimi), verify the XML skeleton is well-formed (`<context>`, `<objective>` or `<goal>`, `<constraints>`, `<your_lens>` tags present).

3. **Redundancy test:** Swap any two agents' lenses. If the prompts become incoherent, you have divided labor. This applies across tiers too — a Codex agent's lens and a DeepSeek agent's lens should be swappable in principle (only the prompt format differs).

4. **Lens quality test:** Each lens name must be a weighing posture (1-3 words), never a task or role. For each lens, write one sentence explaining what unique axis it covers that no other lens does. If two lenses would produce the same emphasis, replace one. **Adversarial coverage is opt-in, not default:** include a structurally adversarial lens (Adversarial, Falsification, Disconfirming, Risk, or similar) only when having one is *much more valuable* than spending that slot on another orthogonal lens — i.e., the answer turns on surfacing a non-obvious flaw, attack, or failure mode that no other lens is already covering. Before adding one, write one sentence naming the specific risk it exists to catch; if you can't, drop it and use an exploratory lens instead. This applies regardless of task category — a "risk-bearing" task (decision, design, code review, implementation, root-cause claim) does *not* automatically require an adversarial lens; judge whether stress-testing is the binding constraint for *this* question. **Conversely, the omission must also be deliberate:** if the task proposes, evaluates, or changes something and you include *no* adversarial-family lens, write one sentence naming which dispatched lens covers "what could go wrong." If none does, add one — it need not be a full Adversarial lens; a failure-mode-tilted variant of an exploratory lens (e.g., Depth-Weighted on failure modes) can suffice. Silent omission on such a task is a check failure, because an all-constructive dispatch can converge with false confidence when nothing was assigned to attack the proposal. Never assign the same lens to two of Codex, DeepSeek, MiMo, or Kimi — that wastes a perspective. If you do include an adversarial lens and it carries the heaviest reasoning load on a subtle technical question, confirm it is assigned to Claude or Codex (`xhigh`) rather than a parallax tier — and if a parallax tier must take it, prefer MiMo over DeepSeek (see "Tier strength and lens fit" in Parallax).

5. **Dispatch-shape test (CRITICAL):** Total dispatched agents (subagents + Codex parallax + DeepSeek parallax + MiMo parallax + Kimi parallax) must match the configured counts. Self does not count. Enumerate planned calls by type:
   - Bash relay calls with `--to codex` must equal `codex-count`.
   - Bash relay calls with `--to deepseek` (or whose env routes to DeepSeek) must equal `ds-count`.
   - Bash relay calls with `--to mimo` (or whose env routes to MiMo) must equal `mm-count`.
   - Bash relay calls with `--to kimi` (or whose env routes to Kimi) must equal `k-count`.
   - The rest are Agent calls and must equal `sub`.

   If any count mismatches, the dispatch is wrong — fix before launching. The most common failure is forgetting one of the parallax calls (DeepSeek, MiMo, or Kimi) and emitting fewer relay calls than `codex-count + ds-count + mm-count + k-count`.

6. **Effort test:** If the user specified `codex-effort` in the shorthand, confirm every Codex relay call uses the mapped level (`m` → `--effort medium`, `x` → `--effort xhigh`) — never pass the raw shorthand letter, the relay script rejects it. If omitted, confirm each Codex call uses the effort from the lens-based table (Effort selection for Parallax). State the Codex effort being applied. DeepSeek, MiMo, and Kimi calls must NOT pass `--effort` — DeepSeek always runs at `max`, and MiMo and Kimi have no effort knob. Reject Codex effort letters outside `{m, x}` at parse time.

### Division-of-labor diagnostic

If any of these differ between agent prompts, you've divided labor: scope, evidence, tools, output format, or deliverables.

## Lens Assignment

A lens is a **weighing posture**, not a task variant. Do not put the task noun in the lens name.

Choose lenses on **orthogonal tradeoff axes**. Before adding one, write one sentence explaining how it differs from every existing lens. If you cannot name a distinct axis, do not add it. Avoid more than 5 dispatched agents unless the task clearly supports that many distinct postures.

**`Disconfirming` vs `Disconfirming-via-different-frame`:** these are not interchangeable. `Disconfirming` is adversarial — it directly attacks a specific claim and is subject to the opt-in gate in the Lens quality test. `Disconfirming-via-different-frame` is exploratory — its value is an alternate prior or framing, not stress-testing — so it counts as an orthogonal default, not the adversarial slot. Do not relabel an attack posture as a frame to evade the opt-in gate.

### Suggested lenses by task type

Starting points — every lens still answers the full question. The adversarial slot (italicized below) is a *candidate*, not a default: keep it only if stress-testing is the binding constraint for this specific question (see Lens quality test); otherwise replace it with an orthogonal exploratory lens such as Outsider, First-Principles, or Depth-Weighted.

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
2. Assign lenses (run the redundancy and lens-quality checks — these are yours to judge), then write the compact config JSON (`shared_packet` + one `parallax` entry per peer + one `subagent` entry per lens). See "Dispatch via prism-launch".
3. **`~/.claude/skills/prism/scripts/prism-launch prepare --config /tmp/prism-<id>-config.json`** (foreground). This validates the packet and records its path (it does not copy or hash it — do not mutate the packet after this point), renders all launchers, runs checks 1/2/5/6, and writes `<id>-manifest.json`. If it exits non-zero, fix the config and re-run — nothing has been dispatched.
4. Launch all dispatched agents concurrently (`run_in_background: true`). **Dispatch checklist:**
   - **Parallax — ONE backgrounded Bash call:** `~/.claude/skills/prism/scripts/prism-launch parallax /tmp/prism-<id>-manifest.json` (set the Bash tool `timeout` above `PRISM_PEER_TIMEOUT`, e.g. `1860000`). This fans out every Codex/DeepSeek/MiMo/Kimi call, waits for all, and yields a single completion notification. Compose this call FIRST.
   - **Subagents:** one **Agent** tool call per subagent, using the contents of the rendered launcher file (`prepare` printed the paths) as the prompt. Never use `claude -p` for these.
   - The manifest's `counts` is the authoritative dispatch shape — there is no per-relay-call count to reconcile by hand, because `prism-launch` emits exactly the configured calls.

Do not poll or sleep-loop — the system notifies you when agents finish. (A bare-name "command not found" is not a fallback trigger — invoke by the absolute path above. The manual `sed`+heredoc flow applies only if the script file is genuinely missing, per "Manual fallback" above.)

### Step 2: Self-review

While agents run, form your own position independently. Your lens is **Integrator Lens** — you weigh holistic coherence, feasibility, and alignment with the user's goals. Write your tentative recommendation before opening any agent output.

Since you composed the prompts and chose the lenses, your self-review is not fully independent. When dispatched agents diverge from your position, give their perspectives slightly more weight on points you may have anchored on during prompt design.

### Step 3: Wait for ALL agents (HARD GATE)

**Do not synthesize, summarize, or present results until EVERY dispatched agent — including all Parallax tiers — has returned.** This is a hard gate, not a suggestion. Having "enough" subagents is never a reason to skip the remaining agents. The whole point of Parallax is model diversity — proceeding without it defeats the purpose of Prism. One peer finishing first (Codex, DeepSeek, MiMo, or Kimi) is never permission to ignore the others.

**Parallax is slow — that is normal and expected.** Relay calls routinely take 2-5x longer than same-model subagents. DeepSeek calls (always at DeepThink `max`), MiMo calls, Kimi calls (thinking on by default), and Codex calls at `--effort xhigh` are the slowest. Do not diagnose, retry, report failure, or proceed while a background task is running. With `prism-launch parallax`, **all parallax peers finish under a single completion notification** (the fan waits for every peer before signaling) — so a default run yields ~3 notifications: one per subagent plus one for the whole parallax batch. Until both the parallax notification and every subagent notification have arrived, the run is healthy. Do not tell the user you are "still waiting" or suggest proceeding without any tier.

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

Scan each agent's output for recursion indicators: mentions of "dispatching," "subagent," "relay call," "Prism run," or synthesis-style structure (Consensus/Contested/Unique sections). Flag matches for review — the agent may have spawned nested agents, producing contaminated reasoning.

### Step 4: Synthesize

Write a decision brief, not a lens-by-lens report. The user should understand the recommendation and next action in seconds, not minutes.

**Default budget: ~150-300 words.** If you're writing more, you're hedging or scaffolding — compress. Deliverables are bounded by the artifact, not commentary.

**Default structure (in this order):**

1. **Answer** — 1-3 sentences stating the recommendation or conclusion directly. For deliverable questions (code, plan, document), the artifact is the answer — put it here, before rationale.

2. **Do now** — 1-3 ranked actions, verb-first. Only immediate actions worth ranking. No "consider" or "maybe" unless tied to a concrete trigger.

3. **Why** — 2-4 bullets of decisive reasoning. Fold confidence inline when it helps ("Moderate confidence — Parallax dissented on X"). Surface cross-model agreement or dissent here only when it materially changes confidence.

4. **Watch / Dissent** — 0-3 concrete triggers that would change the recommendation, or the single strongest dissent stated fairly with how you weighed it. Skip entirely if nothing is decision-relevant. Never manufacture caveats.

**Mode adaptation (pick before writing):**

- **Converged** (lenses + Parallax agree): Answer + Do now + short Why only. Skip Watch/Dissent.
- **Material disagreement**: Add `Tradeoff` or `Decision point` after Why — name the two options, what each optimizes, why you chose. Dissent stays in Watch/Dissent.
- **Cross-model break** (subagents converge, one or more Parallax tiers dissent): cap confidence at moderate. Lead Watch/Dissent with the Parallax argument — cross-model disagreement is the highest-signal finding and must not be buried. When two or more parallax peers (Codex, DeepSeek, MiMo, Kimi) dissent in the *same direction*, treat this as an especially strong signal (independent model lineages agree the subagents missed something).
- **Deliverable**: artifact in Answer; Why becomes design rationale; Do now covers integration/review steps.

**Banned in the main path:**

- Per-lens attribution ("Agent A said…", "The Simplicity lens noted…"). Move to an optional `<details>Per-lens notes</details>` appendix at the very bottom only if the user asked, or if disagreement is deep enough to require lens-level audit.
- Synthesis narration ("Weighing the perspectives…", "After considering the arguments…"). The recommendation carries the reasoning.
- Generic contingencies ("if requirements change"). Only concrete, observable triggers.
- Standalone `Confidence and basis` / `Key dissent` / `Contingencies` sections. Their content folds into Why and Watch/Dissent, and only when decision-relevant.

**Cross-model weighting (internal — surfaces through Why):**

- **Not all answers are equally good — judge each on its merits and reject the weak ones.** Running the assigned lens does not guarantee a sound answer: an agent can produce shallow reasoning, a wrong premise, a misread of the question, or a confident claim with no support. The integrator's job is to *identify and discard* those answers, not to average every response together. Weight by the strength of an answer's reasoning and evidence, not by the fact that an agent produced it (discount weak reasoning, never the model label). Dropping a low-quality answer entirely is a valid, expected outcome — say so in Why when a notable perspective was set aside.
- Same-model convergence is signal but discounted — shared training = shared blind spots.
- Parallax (cross-model) confirmation or dissent carries outsized weight — model diversity is prism's entire point.
- A single well-reasoned point can beat multi-agent consensus driven by shared priors.

If you cannot articulate why dissent is wrong, downgrade confidence in Why rather than expanding dissent into a paragraph.

The synthesis reflects your judgment as integrator — agents are advisors, not a voting bloc. Convergence is evidence, not a vote.

### Step 5: Grounding check

Re-read the user's original question. Verify:

- Your synthesis answers it directly. If they asked for a deliverable, you produced one.
- The first section tells the user what to do.
- No lens-by-lens summary appears outside an optional appendix.
- Every retained dissent, caveat, or trigger changes a decision, confidence level, or next action.

Optionally delete all Prism temp files — they share the `/tmp/prism-<unique-id>` prefix: shared context (`.md`), config, manifest, rendered launchers (`-launcher-*.md`), parallax out logs (`-out-*.log`), and result sentinel (`-result.json`). A single `rm -f /tmp/prism-<unique-id>*` covers them.

## Guards

- **No recursion (HARD RULE):** Dispatched agents must never spawn child agents or invoke any dispatching skill (prism, relay, gpt-pro-relay, deep-research, or any cross-model dispatch tool). Read-only analysis skills are permitted. The Constraints section and launcher prompts both enforce this — do not weaken or omit either. For Parallax, keep the anti-recursion warning at the top of every heredoc (Codex, DeepSeek, MiMo, and Kimi launchers).
- **No contamination:** Write the shared context file and compose all launcher prompts before any launch. Do not modify the shared file or revise prompts after seeing early agent outputs.
- **No all-same-model dispatch (HARD RULE):** The dispatched parallax peers must equal `codex-count + ds-count + mm-count + k-count`. Via `prism-launch`, the manifest's `counts` derives this from the config, and the single `parallax` call emits exactly those peers — so the historical "forgot a relay call" failure cannot occur. In the manual fallback, the total count of Bash relay calls must equal that sum; if the planned dispatch has zero relay calls but any configured count is non-zero, fix before launching.
- **No early synthesis (HARD RULE):** Do not synthesize until every dispatched agent has returned its completion notification. "Subagents are done, Codex relay is still running" or "Codex came back, DeepSeek is still running" are not reasons to proceed — they are the expected state. Proceeding without any tier's results voids the entire Prism run.
- **No side effects:** Dispatched agents must not edit files, commit, push, or invoke any skill with side effects (e.g., push, xurl, todo, goal-drive). Read-only analysis skills are allowed. The only permitted write is the relay response file (.res.md).

## Degrees of Freedom

The core principle (redundancy, not division of labor), the prompt template structure, and the hard completion gate are load-bearing constraints — do not relax them. Everything else — lens choices, synthesis categories, agent count beyond the minimum, pre-launch check order — is flexible guidance that you should adapt to the task.

**Synthesis adaptation:** The default structure (Answer, Do now, Why, Watch/Dissent — see Step 4) suits most analysis and decision questions. But the integrator should actively adapt the synthesis frame when the task calls for it — merge sections, reorder, or add task-specific sections. A deliverable question needs the artifact front and center in Answer with design rationale behind it; a pure risk assessment might elevate Watch/Dissent above Why. Rigid adherence to the default structure when it doesn't fit the question is a failure of integration.

## When to Use Prism

Use Prism when a task benefits from diverse, redundant judgment and the shared context fits cleanly across all agents.

Skip Prism for trivial lookups, deterministic transforms, single-correct-answer tasks, or tasks requiring parallel mutations of shared state.
