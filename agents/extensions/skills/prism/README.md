# Prism

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that strengthens any output through parallel multi-agent deliberation across multiple model lineages — Claude (subagents), [Codex](https://github.com/openai/codex) GPT-5.5, [DeepSeek](https://www.deepseek.com/) V4 Pro, and [Xiaomi MiMo](https://platform.xiaomimimo.com/) V2.5 Pro.**

> *White light looks simple until it hits a prism — then you see every color was there all along. One question, many angles, nothing hidden.*

Prism sends the same complete question to multiple independent agents, each answering from a different analytical lens. Convergence across diverse lenses is high-confidence signal; divergence surfaces tradeoffs that need explicit resolution.

Invoke with `/prism` or ask your agent to "use prism" on any task.

Prism was built by the process it teaches. Every revision — naming, protocol design, lens calibration, this README — was reviewed and improved by running `/prism` on itself: multiple agents deliberating from different lenses, then synthesizing into a stronger version. The skill sharpens itself.

## Table of Contents

- [Why](#why)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [Lenses](#lenses)
- [Parallax (Cross-Model)](#parallax-cross-model)
- [Contributors](#contributors)

---

## Why

A single agent gives you one model's perspective. Prism gives you multiple:

- **Catch blind spots** — independent agents examining the same problem from different angles find issues that any single perspective misses
- **Surface tradeoffs** — disagreement between agents reveals decisions that need explicit resolution rather than implicit assumption
- **Build confidence** — convergence across diverse lenses is stronger signal than a single agent's certainty

### Why not just ask twice?

Asking the same question twice gets you the same biases twice. Prism assigns each agent a different **lens** — a weighing posture that changes what they emphasize, not what they skip. Every agent still answers the full question end-to-end.

---

## How It Works

```
┌───────────────────────────────────────────────────────────────────────────┐
│  User question + shared context                                           │
├──────────┬──────────┬──────────┬─────────────┬─────────────┬──────────────┤
│   Self   │ Agent 1  │ Agent 2  │   Parallax  │   Parallax  │   Parallax   │
│ Integra- │ Lens: A  │ Lens: B  │   — Codex   │  — DeepSeek │    — MiMo    │
│   tor    │ (Claude) │ (Claude) │   Lens: C   │   Lens: D   │   Lens: E    │
│          │          │          │ (relay→GPT) │ (relay→DS4) │ (relay→MiMo) │
├──────────┴──────────┴──────────┴─────────────┴─────────────┴──────────────┤
│  Synthesis: consensus, contested, unique, gaps                            │
└───────────────────────────────────────────────────────────────────────────┘
```

Self is the primary agent (the one you're talking to). It uses the **Integrator Lens** — weighing holistic coherence, feasibility, and alignment with your goals — and forms its own position while dispatched agents run in parallel. Not every agent's answer is equally good: as integrator, Self judges each on the strength of its reasoning and evidence, rejecting weak or wrong answers rather than averaging them in.

1. **Freeze context** — build one shared evidence packet with all information needed
2. **Compose prompts** — word-for-word identical question and context across all agents, only the lens line differs
3. **Verify** — run pre-launch checks (redundancy, lens quality, count)
4. **Launch all concurrently** — subagents + all Parallax tiers in parallel, then self-review
5. **Wait for ALL** — no partial synthesis (one peer finishing first ≠ permission to ignore the others)
6. **Synthesize** — consensus, contested points, unique insights, blind spots, recommendation

**Default: 6 perspectives** — self + 5 dispatched agents (2 Claude subagents + 1 Codex parallax + 1 DeepSeek parallax + 1 MiMo parallax, all via [Relay](https://github.com/chrisliu298/relay)). Any parallax tier can be opted out individually by setting its count to `0`.

### Core rules

These are load-bearing constraints — everything else (lens choices, agent count above the minimum, synthesis format) is flexible guidance:

- **Redundancy, not division of labor** — every agent answers the full question end-to-end. If agents get different files, tasks, or deliverables, that is not Prism.
- **Identical prompts** — the Full Question and Context sections must be word-for-word identical across all dispatched agents. Only the lens line differs.

### Dispatch: the `prism-launch` launcher

Dispatch is handled by a small script, `scripts/prism-launch`, so the orchestrating agent never hand-renders prompts or hand-writes relay calls.

**Before** — the agent generated, *inline in the conversation*, a `sed` render plus a full relay heredoc for **every** cross-model call, then hand-counted the calls and tracked one completion ping per call:

```
   for EVERY run, the agent emits by hand:
   ┌──────────────────────────────────────────────────────────────┐
   │  sed render  +  relay heredoc   ──▶ relay call --to codex    │ ─┐
   │  sed render  +  relay heredoc   ──▶ relay call --to deepseek │ ─┤ 3 Bash
   │  sed render  +  relay heredoc   ──▶ relay call --to mimo     │ ─┘ relay calls
   │  Agent(prompt…)  Agent(prompt…) ──▶ 2 Claude subagents       │ ─── 2 Agent calls
   └──────────────────────────────────────────────────────────────┘
   then: manually reconcile the dispatch-shape count,
         and track 5 separate completion notifications
   ✗ #1 failure mode: forget one relay call (DeepSeek/MiMo)
   ✗ ~hundreds of boilerplate tokens reproduced verbatim each run
```

**After** — the agent writes one compact config, runs `prepare` (renders + validates + emits a manifest), then makes the subagent calls plus **one** backgrounded `parallax` call that fans out every peer and returns a single result:

```
   one config.json  (shared_packet + one line per peer / subagent)
        │
        ▼
   prism-launch prepare ─▶ renders all launchers from templates,
        │                  validates shape · effort · injection,
        │                  validates packet, writes manifest.json
        ▼
   ┌─ Agent(subagent 1) ─┐   Claude subagents stay in-conversation
   ├─ Agent(subagent 2) ─┤   (a shell can't launch the Agent tool;
   │                     │    `claude -p` is never used for Claude)
   └─ prism-launch parallax manifest.json   ◀── ONE backgrounded call
            │
            ├──▶ relay → codex    ─┐
            ├──▶ relay → deepseek  ┤  fans out concurrently,
            ├──▶ relay → mimo     ─┘  WAITS for all peers, writes result.json
            ▼
        ONE completion notification for the whole parallax tier
   ✓ dispatch-shape mismatch is structurally impossible
   ✓ agent emits ~10 lines of JSON, not N rendered prompts
   ✓ notifications drop from 5 to 3 (2 subagents + 1 parallax fan)
```

The launcher owns only the cross-model half — same-model subagents remain Agent-tool calls, so the notification floor is ~3, not 1. If `prism-launch` is unavailable, Prism falls back to the manual `sed`+heredoc flow.

---

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/prism.git ~/.claude/skills/prism
```

### Recommended: install Relay for Parallax

Prism's Parallax tiers dispatch cross-model agents via [Relay](https://github.com/chrisliu298/relay). Without Relay, Parallax falls back to same-model adversarial agents — functional but with reduced model diversity.

```bash
git clone https://github.com/chrisliu298/relay.git ~/.claude/skills/relay
```

**DeepSeek / MiMo prerequisite:** for the DeepSeek parallax tier, export `DEEPSEEK_API_KEY`; for the MiMo tier, export `MIMO_API_KEY` (e.g., in `~/.zshenv.local`). Both are reached via the `claude` CLI with the vendor's Anthropic-compatible endpoint, so no separate binary install is required beyond Claude Code itself.

---

## Usage

Tell your agent to deliberate:

> "Use prism to review my auth middleware changes"

> "I need a prism analysis on whether to use SQL or NoSQL for this"

Or invoke directly with `prism` — also available to subagents.

### Shorthand

Override dispatch defaults with positional args before the question:

```
prism <sub> <codex-count> <codex-effort> <ds-count> <mm-count> <question>
```

- `sub` — Claude subagent count (default `2`)
- `codex-count` — Codex parallax count (default `1`, `0` to skip)
- `codex-effort` — `m` / `x` only (default `m`; Codex relay exposes two effort tiers — medium and xhigh)
- `ds-count` — DeepSeek parallax count (default `1`, `0` to skip). DeepSeek always runs at `max` (DeepThink) — no effort knob.
- `mm-count` — MiMo parallax count (default `1`, `0` to skip). MiMo has no effort knob.

Examples:

- `prism 2 2 x 2 2 Which architecture should we pick?` — 2 subagents, 2 Codex (xhigh), 2 DeepSeek (max), 2 MiMo
- `prism 1 0 m 1 0 Same-model + DeepSeek only` — skip Codex and MiMo
- `prism 2 1 x 0 0 Should we launch X?` — Codex xhigh, no DeepSeek, no MiMo
- `prism Why does X?` — all defaults

### Example output

After all agents return, Prism synthesizes their findings into a short decision brief — answer first, actions second, rationale third, caveats last:

```
## Answer
Refactor auth to gateway-level validation with opaque tokens.

## Do now
1. Move token validation into gateway middleware.
2. Replace the comparison on `auth/middleware.go:45` with a timing-safe check.
3. Add integration tests for the token refresh flow.

## Why
- All lenses converged on gateway validation as the simpler trust boundary.
- Opaque tokens chosen over JWT: the security audit timeline doesn't leave room to harden self-contained token handling.
- Parallax (cross-model) caught the timing side-channel on line 45 — treat as a merge blocker.

## Watch / Dissent
JWT becomes preferable if offline cross-service verification becomes a hard requirement. That would change the token choice, not the gateway-level decision.
```

### What makes a good Prism task?

- Non-trivial decisions with real tradeoffs
- Ambiguous problems where reasonable people disagree
- High-stakes changes where a missed issue is costly
- Architecture and design choices
- Code reviews of complex changes

### What to skip Prism for

- Trivial lookups or deterministic transforms
- Single-correct-answer tasks (what's the syntax for X?)
- Tasks requiring parallel mutations of shared state
- Tasks where the relevant context can't fit into one shared evidence packet for every agent

---

## Lenses

A lens is a **weighing posture**, not a task variant. Every agent answers the full question — the lens changes what they emphasize.

### Suggested lenses by task type

| Task type | Lenses |
|-----------|--------|
| Code review | Correctness + Simplicity + Adversarial |
| Architecture / design | Evolutionary + Simplicity + Adversarial |
| Implementation | Correctness + Pragmatist + Adversarial |
| Diagnosis / root cause | Causal + Falsification + Risk |
| Option comparison | Simplicity + Feasibility + Disconfirming |
| Writing / communication | Clarity + Audience + Adversarial |
| Research / exploration | Breadth-Weighted + Depth-Weighted + Outsider (adversarial optional) |

The skill includes pre-launch checks that prevent common mistakes:

1. **Redundancy test** — ensures agents aren't dividing labor
2. **Lens quality test** — ensures lenses are distinct weighing postures; requires at least one adversarial lens for stress-testing tasks (decisions, designs, reviews, risk-bearing changes), optional for wide-research or exploratory tasks
3. **Count test** — ensures the right number of agents are dispatched

---

## Parallax (Cross-Model)

Parallax is the cross-model tier of Prism. It dispatches agents via [Relay](https://github.com/chrisliu298/relay) to **different models** — different training, different reasoning patterns, different blind spots. Prism currently supports three parallax tiers in parallel:

| Tier | Model | Effort scale | Strength |
|---|---|---|---|
| Codex | GPT-5.5 | `medium`/`xhigh` | Strong agentic coding, two-tier effort control |
| DeepSeek | DeepSeek V4 Pro (1.6T MoE, open-weight) | `max` only (DeepThink, no knob) | Independent vendor lineage, frontier reasoning; text-only |
| MiMo | Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active, 1M context, open-weight) | no knob | A third independent lineage, distinct from Anthropic and OpenAI; text-only |

Each tier is dispatched as a separate concurrent Relay call. All Parallax agents receive the same full question and context as every other agent — only the lens differs.

### Why model diversity matters

Same-model agents share systematic biases from training. A cross-model perspective catches issues that no amount of same-model redundancy will surface. With three parallax tiers, you can stack the diversity: when two or more of Codex, DeepSeek, and MiMo dissent in the same direction, that's a high-signal finding that independent training lineages agree the subagents missed something.

Assign each parallax tier a lens that maximizes diversity. For stress-testing tasks (e.g., subagents on Correctness and Simplicity), give one parallax Adversarial and another Falsification. For wide-research or exploratory tasks, use orthogonal exploratory lenses (Breadth-Weighted, Outsider, First-Principles) on the parallax tiers instead — Prism is also valuable when you want broad coverage rather than to attack a proposal. Never assign the same lens to two parallax tiers — that wastes a perspective.

### Without Relay

If Relay is not installed, Prism replaces all Parallax tiers with same-model agents and picks replacement lenses based on the task: structurally adversarial lenses (Adversarial, Falsification, Disconfirming) for stress-testing tasks, or orthogonal exploratory lenses (Breadth-Weighted, Outsider, First-Principles) for wide-research tasks. This partially compensates for missing model diversity. The user can also opt out of any tier explicitly by setting its count to `0`.

---

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** — protocol design and synthesis framework
- **Codex** — lens calibration and cross-model validation
- **DeepSeek V4 Pro** — second cross-model parallax tier added 2026-05
- **Xiaomi MiMo-V2.5-Pro** — third cross-model parallax tier added 2026-05
