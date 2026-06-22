# Prism

> A skill that asks **the same complete question** to several independent agents,
> each through a different **lens** (a weighing posture), then synthesizes their
> answers into one decision brief. Cross-model agreement is high-confidence signal;
> cross-model dissent is the highest-signal finding.
>
> **`SKILL.md` is the authoritative spec** — this README is the picture. **Claude-only.**

---

## The idea — redundancy, not division of labor

Every agent answers the **whole** question with the **full** context. Only the
*lens* changes — what each one weighs most heavily. Nobody owns a "part."

```
                        ┌──────────────────────────────┐
                        │     ONE complete question    │
                        └───────────────┬──────────────┘
                                        │  same Q · same context · same scope
        ┌──────────────┬────────────────┼────────────────┬──────────────┐
        ▼              ▼                ▼                ▼              ▼
    ┌────────┐     ┌────────┐       ┌────────┐       ┌────────┐     ┌────────┐
    │ lens A │     │ lens B │       │ lens C │       │ lens D │     │ lens E │  …
    │Adversa-│     │Correct-│       │Simpli- │       │First-  │     │Outsider│
    │ rial   │     │ ness   │       │ city   │       │Princ.  │     │        │
    └───┬────┘     └───┬────┘       └───┬────┘       └───┬────┘     └───┬────┘
        └──────────────┴───────┬────────┴────────────────┴──────────────┘
                               ▼
                       ┌───────────────┐
                       │  INTEGRATOR   │   weighs each on its merits, discards
                       │  synthesizes  │   the weak, surfaces cross-model dissent
                       └───────┬───────┘
                               ▼
                    ┌──────────────────────┐
                    │  one decision brief  │  verdict · conf · n/total agree
                    └──────────────────────┘
```

Convergence across diverse lenses = confidence. Divergence = a tradeoff to resolve.

---

## Architecture — three tiers + the relay bridge

```
┌───────────────────────────── Prism run (Claude-only) ─────────────────────────────┐
│                                                                                   │
│   ┌────────────────┐                                                              │
│   │   INTEGRATOR   │  ← THIS Claude: composes the packet, assigns lenses,         │
│   │  (no dispatch  │    dispatches everything, waits, then synthesizes.           │
│   │   tool — you)  │    Also runs its OWN lens while the others work.             │
│   └───────┬────────┘                                                              │
│           │  dispatches all agents CONCURRENTLY (never serialized)                │
│           │                                                                       │
│     ┌─────┴────────────────────────────────┐                                      │
│     ▼                                      ▼                                      │
│  ┌──────────────┐                   ┌──────────────────┐                          │
│  │  SUBAGENTS   │                   │     PARALLAX     │  cross-model, via `relay`│
│  │  Claude × N  │                   │   (peers × N)    │                          │
│  │  (Agent tool)│                   └─────────┬────────┘                          │
│  └──────────────┘                             │ one backgrounded fan-out          │
│   same model →          ┌─────┬──────────┬─────────┼────────┬────┬────┐           │
│   shared blind spots,   ▼     ▼          ▼         ▼        ▼    ▼    ▼           │
│   so convergence here   Codex Grok-Build Grok-Comp GLM Kimi DeepSeek MiMo         │
│   is DISCOUNTED        (GPT5.5) (xAI) (xAI fast) (z.ai) (Moon) (V4-Pro) (Xiaomi)  │
│                         └─────┴──────────┴─────────┴────────┴────┴────┘           │
│                              independent lineages → catch the blind spots the     │
│                              others share → dissent here carries OUTSIZED weight  │
└───────────────────────────────────────────────────────────────────────────────────┘
     Default N=1, M=0:  8×1+0 = 8 dispatched + self = 9 perspectives   (general: 8N+M dispatched, 8N+M+1 perspectives)
```

* **Subagents** are dispatched with the **Agent tool** (only Claude can).
* **Parallax** peers are dispatched through **`relay`**, which runs each model in
  the Claude Code harness (Codex via `codex exec`, Grok via its CLI, GLM/Kimi/DeepSeek/MiMo
  via `claude -p` with the weights swapped). A peer is a *full agent*, not an API call.

---

## Invocation

```
   prism  [N]  [M]  <question>
          │    │
          │    └─ M gpt-pro lenses (optional second number; default 0)
          └─ how many of EACH of the eight standard tiers (default 1; the full 8
             is the floor — a partial fan needs an explicit exclusion). Dispatched
             = 8N+M; perspectives = 8N+M+1. 0 = drop all eight (gpt-pro-only), M ≥ 1.

   No reasoning-effort knob — Codex always xhigh, Grok-Build always high.

   prism Why does X happen?             → auto-sized (anchor: 1 of each)
   prism 2 Which architecture?          → 2 of each, no gpt-pro
   prism 2 3 Bet-the-company call?      → 2 of each + 3 gpt-pro lenses
   prism 0 4 Which approach?            → gpt-pro-only: 4 lenses + self (no standard tiers)
   prism no deepseek, why X?            → natural-language deviations (exclude/count)
```

---

## How a run flows (and where `prism-launch` fits)

`prism-launch` (in `scripts/`) owns the mechanical half: it renders prompts from
templates, validates the dispatch shape, and fans out the relay calls as ONE
backgrounded process. The Integrator stays in the loop for the judgment.

```
 YOU (Integrator)                    prism-launch                         agents
 ════════════════                    ════════════                         ══════

 1  write packet ──────────►  /tmp/prism-<id>.md          ## Full Question
                                   └─ prepare injects ──►  ## Context
                                      ## Constraints       (Constraints owned by
                                      (verbatim, safe)      the script — not you)

 2  scaffold ──► fill ─────►  /tmp/prism-<id>.dispatch     one record per lens
    (--preset pre-fills 8 lenses)        Type/To/Lens

 3  prepare ───────────────►  ┌────────────────────────────────────────────┐
                              │ validate · render launchers · write        │
                              │ <id>-manifest.json (authoritative shape)   │
                              └────────────────────────────────────────────┘
       ◄── prints: ▸ the `parallax` command   ▸ "wait for K notifications"
                   ▸ each subagent launcher's CONTENTS (paste straight in)

 4  launch — ALL at once (run_in_background):
       ├─ Agent call × N ───────────────────────────────────────►  Claude subagents
       │                                                               │
       └─ parallax (bg) ─► ┌── relay ──► codex ───────┐                │
                           ├── relay ──► grok-build   │                │
                           ├── relay ──► grok-composer├─► <id>-result.json
                           ├── relay ──► glm          │   + .relay/…res.md (×peer)
                           ├── relay ──► kimi         │                │
                           ├── relay ──► deepseek     │                │
                           └── relay ──► mimo ────────┘                │
                                                                       ▼
 5  WAIT for every notification ░░░░░░░ HARD GATE ░░░░░ (no early synthesis)
       ~K notifications: one per subagent + one for the whole parallax batch

 6  results ───────────────►  prism-launch results <manifest>
       ◄── [done ] codex   prism-correctness   /…/….res.md
           [ERROR] mimo     prism-outsider      (failed — retry)
       └─ retry one peer:  parallax <manifest> --only mimo

 7  synthesize ─────────────►  verdict · conf · n/total agree [ · ⚠ dissent ]
                               (read each .res.md; weigh; write the brief)
       └─ large/high-volume runs (≥~12, or outputs crowd context): digest
          <manifest> first, then deep-read only the dissenting / weak /
          novel-rationale / tie-break .res.md

 8  clean ─────────────────►  prism-launch clean <id>     rm -f /tmp/prism-<id>*
```

---

## `prism-launch` subcommands

```
  scaffold  [--n N] [--preset TYPE] [--packet PATH]
              └ print a fill-in dispatch skeleton (the Prism-Mode: full / Prism-N / Prism-M
                roster contract + records in canonical order; effort is CLI-derived, never authored).
                --preset review|design|diagnosis|compare|research|decision|writing
                pre-fills eight lenses by task type (N=1).

  prepare   --dispatch <file>     (or --config <json>)  [--expect-n N] [--expect-m M]
              └ validate, render every launcher from templates, write the manifest,
                inject ## Constraints into the packet if absent. ROSTER CONTRACT (--dispatch):
                a Prism-Mode line is REQUIRED — Prism-Mode: full + Prism-N runs a DEFAULT
                fail-closed floor check (every standard tier + subagents at N, gpt-pro at
                Prism-M, aborting on a missing/off-count tier); a reduced roster needs
                Prism-Mode: partial + a verbatim Partial-User-Quote (recorded in manifest
                .shape). --config stays lenient. CLI --expect-n/-m still work and override
                the contract's N/M.

  parallax  <manifest>            [--dry-run] [--only <peer>]
              └ fan out all relay calls as ONE backgrounded process; --dry-run shows
                the commands; --only retries a single peer and merges the result.

  results   <manifest>            └ print each peer's status + .res.md path; non-zero
                                    exit if any failed.

  digest    <manifest> [--out P]  └ extract each peer's ## Digest block into one small
                                    lineage-tagged file (large- or high-volume-run
                                    synthesis; subagent + self digests are already in
                                    the conversation).

  clean     <id | packet-path>    └ rm -f /tmp/prism-<id>*  (guarded against globs).
```

---

## Run artifacts (all under one `/tmp/prism-<id>` prefix)

```
  /tmp/prism-<id>.md                       shared packet  (Q + Context + Constraints)
  /tmp/prism-<id>.dispatch                 line-oriented lens records (what you author)
  /tmp/prism-<id>-config.normalized.json   compiled config (audit trail)
  /tmp/prism-<id>-manifest.json            authoritative dispatch shape  ◄─ parallax/results read this
  /tmp/prism-<id>-launcher-*.md            rendered prompts (one per agent)
  /tmp/prism-<id>-result.json              per-peer status + .res.md paths
  /tmp/prism-<id>-digest.md                peers' ## Digest blocks, lineage-tagged (large runs)
  .relay/<ts>-<pid>-prism-<lens>.res.md    each peer's response   ◄─ READ THESE
  .relay/<…>.log  /  …-out-prism-*.log     peer stderr — NEVER read (token-heavy)
```

---

## The synthesis output

Skim-first: the reader grasps the recommendation, confidence, and any cross-model
dissent in seconds, then reads on only for the reasoning.

```
  Pick Option B (event-driven) · conf: Moderate · 4/6 agree · ⚠ DeepSeek+MiMo dissent
  Claude ✓  Codex ✓  DeepSeek ⚠  MiMo ⚠   → 2 independent lineages dissent, same direction
  Dissent — DeepSeek+MiMo: shared state needed for atomic txns; bounded by the spike gate.
  Why
  • Removes the shared-state bottleneck behind 3/5 recent incidents
  • Migration is incremental, not big-bang (Codex confirmed)
  Do now: spike B's hot path → kill the A RFC → freeze schema
```

The **model-tier tally** (by lineage, not lens) appears only on a cross-model break;
a long header may instead render as a two-column `Verdict | Confidence | …` table.

---

## What feeds the machinery

```
  prism/
  ├── SKILL.md                    ◄── authoritative rules (read this to operate)
  ├── README.md                   ◄── you are here (the picture)
  ├── scripts/
  │   ├── prism-launch            dispatch engine (the subcommands above)
  │   └── test-prism-launch.sh    no-network suite (fake-relay for dispatch)
  └── templates/
      ├── launcher-subagent.tmpl       Claude subagent prompt (plain markdown)
      ├── launcher-relay-codex.tmpl    Codex / GPT  — <goal> style
      ├── launcher-relay-costar.tmpl   Grok/GLM/Kimi/DeepSeek/MiMo — CO-STAR XML
      ├── lens-catalog.json            single source: lens descriptions, axis
      │                                families, and --preset sets (scaffold reads it)
      ├── shared-constraints.md        canonical read-only / anti-recursion block
      │                                (prepare injects this; never hand-copied)
      ├── shared-how-to-answer.md      canonical "## How to answer" block
      │                                (prepare injects this; never hand-copied)
      └── shared-grounding.md          canonical "## Grounding external facts" block
                                       (prepare injects this for every agent; gpt-pro
                                       inherits it via the packet)
            ▲ reads templates + the catalog + the registry
            │
  relay/peers.json   ◄── single source of truth: which peers exist, their effort
                         knobs (effort_values, ordered low→high — prism derives the
                         top/last as the fixed effort), transports, launcher-template
                         style, and each standard tier's order + lineage (scaffold
                         order, peershape, and digest lineage all derive from these).
                         `relay` and `prism-launch` both read it — add a peer in
                         one stanza.
```

---

## Load-bearing guarantees (do not relax — see SKILL.md)

```
  ┌─ Redundancy, not division ─ every agent gets the whole question.
  ├─ Hard completion gate ───── synthesize only after EVERY agent returns.
  ├─ No recursion ───────────── a dispatched peer must never re-enter prism/relay;
  │                             the anti-recursion block is injected verbatim + the
  │                             RELAY_PEER guard refuses a nested launch.
  ├─ Read-only leaf agents ──── peers/subagents produce analysis only (one .res.md write).
  └─ Effort (fixed, CLI-derived) ─ Codex xhigh · Grok-Build high, derived from peers.json — never authored.
```

---

## Reference detail (relocated from SKILL.md — the runbook points here)

### Parallax peers

| Peer | Model | Lineage | Effort | Notes |
|---|---|---|---|---|
| `codex` | GPT-5.5 | OpenAI | `xhigh` | agentic code-review strength |
| `grok-build` | Grok Build | xAI | `high` | independent of Anthropic/OpenAI |
| `grok-composer` | Composer 2.5 fast | xAI (same as grok-build) | — | fast variant; quick xAI take |
| `glm` | GLM-5.2 | Zhipu / z.ai (Anthropic-compatible endpoint) | pinned `max` | `reasoning_effort: max`, like DeepSeek |
| `kimi` | Kimi K2.7-Code | Moonshot (Kimi-for-Coding plan, `api.kimi.com/coding/`) | thinking pinned | `CLAUDE_CODE_EFFORT_LEVEL=max` selects K2.7-Code; ignores `--effort` |
| `deepseek` | DeepSeek V4-Pro | DeepSeek (open-weight) | `max` (DeepThink) | |
| `mimo` | MiMo-V2.5-Pro | Xiaomi (open-weight) | — | |

Grok Build + Grok Composer are **two dispatched tiers** but **one lineage** for lens-assignment and synthesis weighting. Web: every peer effectively has WebFetch + WebSearch — the two native gaps (MiMo WebSearch, GLM WebFetch) each have a verified Jina fallback. `relay/peers.json` is the single source of truth for endpoints, effort knobs, and launcher-template style.

### Manifest count caveat

`8N+M` is the orchestrator-level dispatched count. The manifest's `counts.dispatched_total` is the **standard-tier subtotal only** (parallax + subagents — `= 8N` on a full symmetric run, the actual record count on a partial); gpt-pro is tracked separately in `counts.gptpro` (`prism-launch` does not dispatch gpt-pro — the orchestrator does). So on a full run a `grep` of `dispatched_total` yields `8N`, not `8N+M` — add `counts.gptpro` for the full figure.

### gpt-pro lane (architecture + recovery)

gpt-pro is **orchestrator-direct** — not a relay peer and not in the `parallax` fan: a 5–20 min lens would block the fast relay batch, and its *inline-everything → stdout → run-id-recovery* shape is unlike relay's *read-a-file → write `.res.md`* contract. `prism-launch` composes (in `prepare`) and collects (in `results`/`digest`) the gpt-pro lane, but the transport, run-ids, reattach recovery, exit-code demux, and the macmini concurrency semaphore live wholly in the [[gpt-pro-relay]] wrapper. Exit-code recovery (authoritative in gpt-pro-relay): `0` use it · `124`/`255` reattach with the literal run-id (`gpt-pro --run-id <id>`, same envelope) · `1` inspect `reason`, don't blindly resubmit · `2` fix the call (no quota burned) · `3` engine cap, terminal · `4` fresh-submit only after a reattach proved never-landed. **Never raise `GPT_PRO_MAX_PARALLEL`** (account anti-abuse risk).

### Suggested lenses by task type (`scaffold --preset`)

Starting points — every lens still answers the full question. The **authoritative ordered arrays live in `templates/lens-catalog.json` (`.presets`)** (heaviest-reasoning-first for tier placement); edit a preset there. The italicized adversarial-family slot is a *candidate*, not a default — keep it only if stress-testing is the binding constraint for the question.

- **Code review**: *Adversarial* + Correctness + Simplicity + Depth-Weighted + Temporal + Outsider + Stakeholder + Causal
- **Architecture / design**: First-Principles + *Adversarial* + Simplicity + Stakeholder + Temporal + Empirical + Breadth-Weighted + Causal
- **Implementation** (no preset — compose by hand): Correctness + Pragmatist + *Adversarial* + Depth-Weighted + Outsider + Temporal + Stakeholder + Causal
- **Diagnosis / root cause**: Causal + *Falsification* + Empirical + Depth-Weighted + Temporal + Outsider + Stakeholder + Pragmatist
- **Option comparison**: First-Principles + Empirical + Simplicity + Stakeholder + Temporal + *Disconfirming* + Breadth-Weighted + Causal
- **Writing / communication**: Clarity + Audience + *Adversarial* + Simplicity + Outsider + Empirical + Depth-Weighted + Temporal
- **Research / exploration**: First-Principles + Breadth-Weighted + Depth-Weighted + Outsider + Empirical + Lateral-Generative + Temporal + Stakeholder
- **Decision / strategy**: First-Principles + Empirical + Stakeholder + Temporal + Pragmatist + *Disconfirming* + Breadth-Weighted + Causal

The lens menu (descriptions, axis families) is also single-sourced in `lens-catalog.json` and stays open — mint a task-specific lens when you can name its axis in one sentence.

### Adding a peer / standard tier

Transport + launcher-template style is one `relay/peers.json` stanza (a standard tier also sets `order` + `lineage` — scaffold order, peershape, and digest lineage all derive from it). For a new **standard tier**, additionally add one lens to each `--preset` set in `templates/lens-catalog.json` (the scaffold count-guard fails closed until they match) and update the "8 tiers" / `8N` counts in `SKILL.md`.

---

*When in doubt, `SKILL.md` is authoritative. This README just shows the shape.*
