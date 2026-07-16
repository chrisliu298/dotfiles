---
name: prism
description: >-
  Dispatch multiple independent agents to answer the SAME complete question
  from different analytical lenses, then synthesize. Reach for this by default,
  without waiting to be asked, when redundant cross-model judgment could change
  the decision: ambiguous architecture/design tradeoffs, high-stakes or
  hard-to-reverse changes, competing root-cause hypotheses, or
  failure-mode-sensitive reviews — and whenever you would otherwise spawn 2+
  independent reviewers for one question. Skip for trivial lookups, deterministic
  transforms, routine small edits, mechanical syncs, and single-correct-answer
  tasks. With no leading number, autonomously decide N and gpt-pro from
  the question every time (N=1 is the bottom-rung anchor, never a lazy default);
  with an explicit number (e.g. `prism 2 1`), honor it verbatim and skip
  auto-sizing. There is no reasoning-effort knob. Scale above the anchor only
  when decision risk justifies the 8N-agent cost.
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

**Claude-only.** If `ANTHROPIC_BASE_URL` contains `deepseek`, `xiaomimimo`, `z.ai`, or `kimi.com`, this skill is unavailable — stop and tell the user: "prism is Claude-only; a non-Claude session cannot orchestrate other models." Prism dispatches parallax via [[relay]], which itself refuses from non-Claude sessions.

Prism sends the **same complete question** to multiple independent agents. Each agent answers the **entire question end-to-end**. The only thing that changes between agents is the **lens**: what they prioritize and what tradeoffs they weigh more heavily.

## Operator quick reference

A skim card + execution TOC for the orchestrating Claude — every line points to its authoritative section below; nothing here overrides them.

- **Invoke:** `prism [N|Nns] [M] <question>`. A leading number, the terse `Nns` no-subagents token, or a natural-language tier modifier ⇒ honor it verbatim; **no** number ⇒ auto-size (anchor `N=1`). See *Invocation*.
- **The 8 standard tiers:** Claude subagent · GPT · Grok Build · Grok Composer · GLM · Kimi · DeepSeek · MiMo. gpt-pro is a *separate opt-in* tier (`M`, default 0). See *Counting Contract*.
- **Counts:** dispatched = `8N+M`; perspectives = dispatched + self. The full 8-tier fan at `N` is the **floor** — drop or skew a tier *only* on explicit user instruction.
- **No-subagents (external-only):** user says "no subagents" or the terse `Nns` (e.g. `prism 1ns 1`) → drop only the Claude tier, keep the 7 parallax (+ gpt-pro); dispatched `7N+M`, self the lone Claude perspective. Recognized + floor-checked via `PL scaffold --no-subagents` → `Prism-Mode: partial` + `Variant: no-subagents` (not a bare partial). User-only. See *Counting Contract* → No-subagents shape.
- **Effort:** never authored — GPT `xhigh` (deliberately not `max` or `ultra` — `ultra` is a multi-agent topology, not a leaf depth tier, and `max`'s single-leaf depth isn't validated to beat `xhigh` on a redundant fan), Grok Build `high`, derived from the registry; the rest have no knob.
- **Run** (see *Execution Spine*): write packet `/tmp/prism-<id>.md` → `scaffold` (prints the `Prism-Mode: full` roster contract to stdout, for reference) → **Write** the dispatch directly with your lenses (never `scaffold > file` then edit) → `prepare --dispatch …` (default fail-closed floor check on the contract) → launch **all at once** (1 backgrounded `parallax` + one Agent call per subagent — **zero in a no-subagents run** — + `M` gpt-pro) → **wait for every notification** → `results` / `digest` → synthesize verdict-first. A reduced roster needs an explicit `Prism-Mode: partial` + `Partial-User-Quote:` waiver.
- **Hard gates:** no synthesis until *every* agent returns; dispatched agents are read-only (no cross-model recursion or side effects; own same-model subagents OK); **never** revert the working tree. See *Guards*.
- **Local files:** attach repo files with `Include:` dispatch lines (repeatable; `/abs`, `@base-relative`, or single-level glob; `Include-Base:`/`Include-From:`/`Include-Tree:` too). `prepare` resolves them via `filectx` → generates the packet's `### Reference Materials` (relay/subagent tiers **read** the paths) **and** the gpt-pro **inline** list — one source, secret-scanned, fail-closed. `scaffold` pre-prints the commented slot. Mutually exclusive with hand-written `Reference:` / `### Reference Materials`. See *Shared Context*.
- **Script:** `~/.claude/skills/prism/scripts/prism-launch` (always the absolute path).

## Core Principle

**Prism is redundancy, not division of labor.** Every agent gets the full question, full scope, and full deliverable. The lens changes **emphasis**, not **coverage**. If agents own different files, sections, or outputs, that is division of labor, not Prism.

Convergence across diverse lenses is high-confidence signal; divergence surfaces tradeoffs that need explicit resolution.

## Counting Contract (authoritative — every count in this skill derives from here; never restate bare numbers elsewhere)

Prism has exactly **eight standard tiers**, each dispatched at count `N`: **Claude subagent · GPT · Grok Build · Grok Composer · GLM · Kimi · DeepSeek · MiMo** (= 1 Claude subagent via the Agent tool + 7 parallax tiers via relay). gpt-pro is a separate opt-in tier (`M`), never one of the 8.

- **`N`** — the per-tier count of the **8 standard tiers**. In the symmetric shape every standard tier gets `N`.
- **`M`** — the **gpt-pro** count: a **separate opt-in tier, independent of `N`, default `0`**. GPT-Pro is **never one of the 8** and never consumes a standard-tier slot.
- **Self** (the orchestrator / Integrator) — a **perspective, never a dispatched agent**: adds `0` to dispatched, `+1` to perspectives.

| Quantity | Formula |
|---|---|
| **Dispatched agents** (symmetric) | **`8N + M`** |
| **Dispatched agents** (after explicit exclusions / per-tier overrides) | `Σ(resolved counts over the 8 standard tiers) + M` |
| **Perspectives** (the synthesis `n/total`, incl. self) | **dispatched `+ 1`** |

At `N=1, M=0`: `8×1 + 0 = 8` dispatched, `8 + self = 9` perspectives. **"9" denotes only this** — never reuse a bare agent count without showing its `8N+M` derivation. (`prism-launch`'s manifest reports `counts.dispatched_total` as the standard-tier subtotal — parallax + subagents, which `= 8N` on a full symmetric run but is the actual record count on a partial — never including gpt-pro (tracked separately in `counts."gpt-pro"`); see README for the grep caveat.)

**Grok counts as two:** Grok Build and Grok Composer are **two separately-dispatched agents** (each at count `N`); they collapse to **one lineage only for lens-assignment and synthesis weighting** (see the Grok counting guardrail under Parallax). "One vendor slot" is **never** a dispatch-count rule.

**No-subagents shape (the recognized external-only run):** the user may drop **only the Claude subagent tier** and keep the full parallax fan (+ optional gpt-pro) — "no subagents" / "no Claude subagents". This is the asymmetric `Σ` row with the subagent tier at 0: **dispatched = `7N + M`, perspectives = `7N + M + 1`** (self is the lone Claude perspective). `N` is **not** redefined — it is still the per-standard-tier count; one tier is just pinned to 0. It is a *recognized, floor-checked* reduced shape — `prepare` asserts all 7 parallax tiers at `N` + zero subagents — declared as `Prism-Mode: partial` + `Variant: no-subagents` (the one partial shape that keeps `Prism-N`/`Prism-M`), not a new top-level mode and not a bare partial. Distinct from `N=0` (which drops parallax **too** → gpt-pro-only); `N=0` with "no subagents" is just the gpt-pro-only shape. See Invocation → Natural-language modifications and *Execution Spine* → Roster contract.

**Dispatch invariant (HARD RULE — mechanically enforced by `prepare`):** every tier whose resolved count is `> 0` MUST be dispatched at exactly that count — no silent drops, substitutions, or merges. The **full 8-tier fan at `N` is the floor**: the orchestrator **never self-initiates a partial or asymmetric group**. A tier drops to `0` or takes a non-`N` count **only** when the user explicitly says so (an exclusion or per-tier count — see Invocation → Natural-language modifications); autonomous sizing picks `N` but always across **all 8**. `N=0` (drop all eight standard tiers, gpt-pro-only) is itself a user-stated config and is legal only with `M ≥ 1`. On the `--dispatch` path `prepare` enforces this fail-closed via the `Prism-Mode` contract (see *Execution Spine* → Roster contract). A run that drops a family for cost, latency, or a flaky/overloaded peer (e.g. GLM 529s) is the exact defect this blocks — unavailability is a *post-dispatch* `result.json` `status: error` (retry with `parallax --only <peer>`), never a reason to omit the record.

**The floor is a dispatch-time contract — it is NEVER satisfied by post-hoc salvage of an unverified artifact.** A lens that dies *after* dispatch is a **result to report honestly**, not a hole to paper over: resubmit it, or take an explicitly user-authorized partial. Mind the asymmetry the `--only` out hides: a parallax peer has a cheap in-place retry (`parallax --only <peer>`), **gpt-pro has none** — its only recovery is a fresh, quota-costing run with a new run-id, so a dead gpt-pro lens is a **user decision, not a self-service retry**. An orchestrator holding a dead gpt-pro lens therefore has no legal move that preserves the floor by itself — that is expected. Reaching into the run dir to make the count come out right is the defect this rule names (see *Handling failures* → Provenance failure).

`N=1, M=0` is the bottom-rung anchor (not a fire-without-thinking default): all eight standard tiers once, gpt-pro absent, self added only as a perspective. A bare invocation always routes through **Choosing N and gpt-pro** and never emits this by shortcut.

## Invocation

Two layers: a dead-simple positional form for the symmetric common case, and natural language for any deviation.

**Positional — `prism [N|Nns] [M] <question>`:**
- `N` — how many of **each** of the eight models. Integer `≥ 0`, default `1`. `N ≥ 1` dispatches `N` of every standard tier. **`N = 0` excludes all eight standard tiers at once** (the terse "gpt-pro-only") and is legal **only when `M ≥ 1`**; `prism 0` / `prism 0 0` is rejected (zero dispatched agents is not a Prism run). To drop *some* tiers, use a natural-language exclusion instead. `N` is the symmetric **floor** applied to all 8 tiers — deviating requires an explicit user modification.
- **`Nns` — the terse no-subagents form.** A first token of `<int>ns` (e.g. `1ns`, `2ns`) means **N=`<int>` in no-subagents mode**: drop only the Claude subagent tier, keep the 7 parallax tiers at `N` (+ gpt-pro at `M`). It is the exact equivalent of `prism <int> [M] no subagents <question>` and resolves to the same `Prism-Mode: partial` + `Variant: no-subagents` shape (emit it with `PL scaffold --no-subagents --n <int> --m <M>`). `ns` attaches only to the **first** token; `M` stays a bare integer (`prism 1ns 1 <q>` → N=1, no-subagents, M=1 → 7 + 1 + self = `/9`). `0ns` is just the gpt-pro-only shape (N=0 already drops parallax too) — legal only with `M ≥ 1`. **User-only**, like every tier exclusion.
- `M` — how many **gpt-pro** lenses to add. Integer `≥ 0`, default `0`; **independent of `N`** (never dispatched unless given). Naming it is the cost consent — it burns real Pro quota and runs 5–20 min/lens (see GPT-Pro tier).

**There is no reasoning-effort token.** Effort is fixed per tier — GPT `xhigh`, Grok Build `high`; the rest have no knob. You never choose effort.

The parser consumes **up to two leading whitespace-delimited integers**, left-to-right: first is `N` (or the `Nns` no-subagents form), second is `M`. The first token that is **not** a bare integer (or `<int>ns`) begins the question; everything from there is verbatim question text.
- **Escape:** if the question's own first word is a bare integer **or matches `<int>ns`** (e.g. a nanoseconds question — `1ns latency budget?`), put `--` first — everything after `--` is question text (`prism -- 3 reasons to refactor?`, `prism -- 1ns latency budget?`). `--` is not a config token; it leaves zero config tokens, so the invocation routes to the autonomous decision, not a pinned baseline.

Examples (a leading number skips auto-sizing; **no** number → autonomous decision):
- `prism Why does X?` — no number → autonomously decide `N` and `M`.
- `prism 2 Why does X?` — explicit: 2 of each, no gpt-pro → 16 dispatched + self = 17 perspectives.
- `prism 2 3 Why does X?` — explicit: 2 of each **plus** 3 gpt-pro lenses → 16 + 3 + self = 20.
- `prism 0 4 Which approach?` — `N=0` drops all eight standard tiers; 4 gpt-pro lenses → 0 + 4 + self = 5 (gpt-pro-only). `prism 0` alone is rejected.
- `prism 1ns 1 Why does X?` — no-subagents: drop the Claude tier, 7 parallax ×1 + 1 gpt-pro → 7×1+1 = 8 dispatched + self = `/9`. Same as `prism 1 1 no subagents Why does X?`.
- `prism 2ns Which design?` — no-subagents, N=2, M=0 → 14 parallax + self = `/15`.
- `prism -- 2 reasons to refactor?` — the `--` makes the leading `2` question text; `N`/`M` decided autonomously.

`M`'s accepted natural-language synonyms in the leading config zone are `<M> gpt-pro` and `plus <M> gpt-pro lenses`.

**Natural-language modifications.** The positional form always dispatches all eight models symmetrically; to deviate, state it in words **in a leading config clause before the question** (config is parsed only up to where the question begins — a modifier buried *after* the question starts is question text, not config). Treat a phrase as a modification only when it pairs a **tier name with a config action** (a count, or an exclusion word like no/skip/without); a bare tier name inside the question — e.g. *"why is there no DeepSeek fallback?"* — is **not** a modification, so do not strip or reinterpret it. Resolve modifications into an explicit per-tier count before launch. Supported:
- **Exclude a model** — "no DeepSeek", "skip Grok Composer", "without mimo" → that tier's count = `0` (warn the user that dropping a whole lineage reduces cross-model diversity).
- **No subagents (external-only)** — "no subagents", "no Claude subagents", "without subagents", or the terse positional **`Nns`** (`prism 1ns 1 …`) → the **Claude subagent tier** alone drops to `0`; all 7 parallax tiers stay at `N` (+ gpt-pro at `M`). Resolve it to the recognized shape `Prism-Mode: partial` + `Variant: no-subagents` + `Prism-N`/`Prism-M` + `Partial-User-Quote` (**not** a bare partial — the Variant keeps the floor check). Emit it with `PL scaffold --no-subagents [--n N] [--m M] [--preset T]`. **User-only, never auto-selected.** Self becomes the lone Claude perspective; note that in synthesis (Step 4 → No-subagent run).
- **Per-model count** — "2 GPT, 1 of the rest", "3 Claude subagents" → the named tier overrides `N`; unnamed tiers keep `N`.
- **Combinations** — "2 of each but no Grok Composer".
- **Asymmetric example**: "2 of each, but no Grok Build or Grok Composer, and 2 DeepSeek" → Claude 2, GPT 2, **Grok Build 0, Grok Composer 0** (name both tiers — never "Grok ×0"), GLM 2, Kimi 2, DeepSeek 2, MiMo 2 → Σ = 12 dispatched, 13 perspectives.

`N` (and the optional `M`) set the symmetric baseline; named modifications override specific tiers on top of it (an explicit exclusion overrides the "all eight always included" default; on conflicting clauses the more specific or later one wins). You — the orchestrator — own resolving the shorthand and NL into the dispatch records **and into the `Prism-Mode` contract** (`full` + `Prism-N` for the symmetric default; `partial` + `Partial-User-Quote` only when the user explicitly asked for a reduced set; see *Execution Spine* → Roster contract). The `relay`-unavailable exception (substitute a same-model subagent carrying that tier's lens and warn) keeps the tier present, not dropped.

### Config-presence gate (the routing decision)

Before anything else, the parser's result routes the invocation down exactly one of two paths — keyed on **what the parser resolved**, never on a re-reading of the raw string:

- **Any config token present** — a leading integer (`N`, or `N M`), the terse `Nns` no-subagents token, *or* a leading natural-language modification (a tier name paired with a count or exclusion) → **honor it verbatim and skip auto-sizing.** `M` defaults to `0` and all eight tiers are included unless a modification says otherwise — a *stated default*, not an autonomous decision. Do not consult the decision table; do not "improve" the user's `N` or `M`. `prism 2 <q>` is `N=2`/`M=0`, full stop. (One validity check, not an "improvement": `N=0` is honored only with `M ≥ 1`; `prism 0` / `prism 0 0` is rejected.)
- **Zero config tokens** (the question begins immediately; `--` also lands here) → **autonomously decide** `N` and `M` per **Choosing N and gpt-pro**. Run that decision every time; the absence of a number is never permission to fire the baseline without reasoning.

A bare tier name *inside the question* ("why is there no DeepSeek fallback?") is **not** a config token — it does not flip the gate to the explicit path.

### Choosing N and gpt-pro (decide autonomously — don't ask)

**This section runs only when the Config-presence gate routed you here — i.e. no leading number.** On a bare question, pick `N` and `M` yourself — do not ask. Use the smallest run whose extra perspectives could change the action, confidence, or rollback plan. **Default down:** each `+1` to `N` adds a full eight-model slate and slower synthesis; never raise `N` just to "be thorough." **Start at the bottom rung and justify each step up:** land on the *lowest* row whose situation actually matches; if you cannot name the specific extra perspective an added agent would contribute, you are at the anchor.

| Situation | N |
|---|---|
| Bottom rung (anchor — start here) — a Prism-worthy decision one good pass could settle | 1 |
| Several viable options or stakeholder tradeoffs where breadth matters more than depth | 2 |
| Exceptional blast radius, or a decision still underdetermined after framing | 3 |
| Beyond N=3 | only on explicit user request or documented exceptional complexity — note the larger run shape in the launch status line, not as a gate |

**gpt-pro (default M=0 — usually skip):** gpt-pro is the opt-in premium tier on **two co-equal axes — Deep Reasoning and Research-Grounded Judgment** (top-tier reasoning, plus the only tier that browses by default in a front-loaded run). It spends real ChatGPT Pro quota and runs 5–20 min/lens, so the eight-model lineup is the default and gpt-pro is the rare exception. Auto-add **one** lens (`M=1`) only when the decision is genuinely high-stakes or hard-to-reverse **and** one of those two axes is the binding constraint: the hardest reasoning in the run, or live external research whose value is the research-plus-reasoning synthesis the standard tiers can't match. **"Needs the web" alone is not enough** — every tier browses, so route to gpt-pro only when research must be reasoned over at the strongest tier. Give gpt-pro the posture matching the binding axis (see GPT-Pro tier). Use **`M=2`** (one Deep-Reasoning + one Research-Grounded) only for an exceptional, multi-faceted high-stakes call; never auto-add more than 2. You fire it yourself and just launch — do **not** pause for a confirmation or abort gate.

Note the resolved shape and its source as a one-line status line as you launch — **always show the `8N+M` arithmetic, never a bare headcount**: `<auto-sized|explicit> · N=<n>, M=<m> · dispatched 8×<n>+<m>=<D> · +self=<D+1> perspectives` (for an asymmetric run, replace `8×<n>+<m>` with the resolved per-tier sum and name the non-`N` tiers). A wrong count is then self-evidently wrong (`8×2+0=16`, never a bare `9`). Not a confirmation gate; never pause for the user to approve or redirect.

## Agents and lanes

| Tier | Tool | Role |
|------|------|------|
| Self | (none) | Your own analysis while agents run |
| Subagents | **Agent** | Same-model agents (Claude), one Agent call each |
| Parallax (×7) | **Bash** (`relay call --to <peer>`) | Cross-model agents via relay: GPT · Grok Build · Grok Composer · GLM · Kimi · DeepSeek · MiMo |
| GPT-Pro (opt-in) | **Bash** (`gpt-pro < prompt.md`) | Additive ChatGPT Pro Extended lenses via [[gpt-pro-relay]]; composed by `prepare`, fired orchestrator-direct; **not** a relay peer / not in the parallax fan; slow + quota-burning; off by default |

### Parallax (cross-model agents)

Parallax is dispatched via `relay` to **different models**. Invoke `relay` directly — not via a subagent that calls relay. The value of each tier is **model-lineage diversity**:

| Peer | Lineage | Effort | Note |
|---|---|---|---|
| `gpt` | OpenAI | `xhigh` | agentic code-review strength |
| `grok-build` | xAI | `high` | independent of Anthropic/OpenAI |
| `grok-composer` | xAI (same as grok-build) | none | fast variant; reach for a quick xAI take |
| `glm` | Zhipu/z.ai | none (pinned max) | independent lineage |
| `kimi` | Moonshot | none (K3 is thinking-only, effort `max`) | independent lineage |
| `deepseek` | DeepSeek (open-weight) | none (max/DeepThink) | independent lineage |
| `mimo` | Xiaomi (open-weight) | none | independent lineage |

(Full per-model version/endpoint/plan detail lives in README; it is reference, not runbook.)

**Grok counting guardrail:** Grok Build and Grok Composer are **two separate standard tiers**, both dispatched at count `N` — never merge them into one call or drop one because they share lineage. "Treat the two Grok tiers as **one vendor slot**" is a **lens-assignment + synthesis-weighting rule only** (don't give them two independent diversity lenses), **never** a dispatch-count rule.

**Tier strength and lens fit (heuristic for lens assignment, not a routing rule):** reasoning-capability tiering (operator-assessed; revisit as versions change) — **gpt-pro (when opted in) ≳ Claude ≈ GPT > {GLM, Kimi, Grok Build, Grok Composer} > {DeepSeek, MiMo}**. This informs lens *placement*, not inclusion — **never drop GLM, Kimi, DeepSeek, or MiMo to "upgrade" a run**; lineage diversity is non-substitutable:
- **Subtle hard-reasoning lenses on risk-bearing questions** (Adversarial / Falsification / Disconfirming where finding the non-obvious attack is the deliverable): prefer Claude subagent or GPT (`xhigh`). If a parallax tier must take it, prefer a middle-tier peer (GLM, Kimi, or Grok Build) over the bottom tier (DeepSeek/MiMo).
- **Lenses where the value is a different prior** (Outsider, First-Principles, Reframe, Breadth-Weighted, Lateral-Generative, Stakeholder): give these to the independent lineages (GLM, Kimi, DeepSeek, MiMo) — their lineage is the asset; raw reasoning depth is not the bottleneck.

In synthesis every tier's dissent keeps full cross-model weight (discount weak reasoning, never the model label).

**Same shared prompt.** Don't tailor the prompt body per peer — Prism sends the **same shared prompt** to every model (the launcher templates handle the only per-peer difference: GPT `<goal>` vs CO-STAR XML). Optimize shared-prompt quality (an outcome-first packet + sharp, distinct lens descriptions), not per-model fit.

**Web access is not a dispatch concern — don't verify it.** Every peer can reach the web (native WebSearch + WebFetch, with verified Jina fallbacks for the two native gaps — MiMo WebSearch, GLM WebFetch; see [[relay]]). By default Prism front-loads stable evidence in the packet (Reference Materials) so agents reason over it rather than re-searching; the shared `## Grounding external facts` block (injected for every agent) directs each to verify any external / time-sensitive fact against a live source instead of answering from memory. When the *whole task* is live research, each agent researches independently (see *Shared Context* → Independent research). Either way, do **not** spend a dispatch-time step checking web support.

**Relay call syntax** — `prism-launch parallax` emits these for you (deriving each peer's fixed `--effort` from the registry); this is also the manual-fallback form:

```bash
relay call --to <peer> --name prism-<slug> [--effort <effort>] <<'BODY'
<prompt content here>
BODY
```

Only GPT (`--effort xhigh`) and Grok Build (`--effort high`) carry `--effort`; the rest omit it. For all other relay rules (`--name` required, non-empty heredoc, no model flags, concurrency) follow the [[relay]] skill.

**Inspecting results:** Read only the `.res.md` response file — never the `.log` sidecar (token-heavy stderr; the Bash output already surfaces failure diagnostics).

If `relay` is unavailable, replace all Parallax tiers with same-model subagents and warn the user. Each substitute carries the lens that tier was already assigned — do not re-decide by task category. **Exception — a no-subagents run (HARD RULE):** this fallback is **forbidden** when the user excluded subagents (the substitutes would reintroduce the very Agent calls they banned). Instead: if `M ≥ 1`, degrade to gpt-pro-only (the `N=0` shape) **only with the user's explicit OK**; if `M = 0`, **refuse** (offer: retry relay, or re-run allowing subagents). Both lanes down ⇒ refuse — self alone is not a Prism run.

**Constraint leakage risk (CRITICAL):** Relay peers may recurse unless the anti-recursion rule is explicit, early, and repeated. You MUST:
1. Put the anti-recursion warning at the top of every launcher prompt, before the file-read instruction.
2. Preserve the Constraints section verbatim in the shared context file — do not summarize or abbreviate.
3. Ensure the prohibition appears in both each launcher (short form) and the shared file (full form).
4. Tell each peer to ignore loaded skill descriptions for the dispatching/side-effecting skills (prism, relay, gpt-pro-relay, deep-research) — read-only analysis skills stay available.

Without these redundant prohibitions, the peer treats the task as a fresh request and recurses. (`prepare` checks only that each rendered launcher's first line starts with `CRITICAL:` — the content above is guaranteed by the committed templates for the script path, and is yours to emit for any hand-built launcher.)

### Subagents

Same-model agents dispatched via the Agent tool. Each gets a distinct lens. **Prism subagents may spawn their own same-model subagents at their discretion** (they're told they are spawned Prism agents; any child stays terminal — read-only, no further spawning, no cross-model dispatch, no response-file write) — but their prompts forbid starting a nested Prism run, invoking any cross-model dispatch skill (prism, relay, gpt-pro-relay, deep-research) or calling another model, and side effects, while permitting read-only analysis skills (see Constraints in the Shared Packet Template). Launch all agents concurrently before starting self-review.

### GPT-Pro tier (opt-in)

Dispatched only when the user gave `M > 0`; default count `0`. gpt-pro is **orchestrator-direct**: `prism-launch` composes each launcher for you, but **you fire the `gpt-pro` calls yourself** (one backgrounded Bash call per lens, concurrent with the parallax fan and Agent calls). It is **not** a relay peer and **not** in the `parallax` fan — never add it to `relay/peers.json` or the parallax batch (a 5–20 min lens would block the fast relay results). Each gpt-pro lens is its **own** completion notification (included in `prepare`'s printed count); collect with `prism-launch results`/`digest`. **Never raise `GPT_PRO_MAX_PARALLEL` from prism** (account anti-abuse risk).

**Gate — if `M > 0`, read `references/gpt-pro.md` before authoring the `Type: gpt-pro` dispatch records or launching.** It owns the record/posture format + canonical example, the launch command (timeout/PATH fallback), notification accounting, and collect/recovery. `prepare` validates gpt-pro records fail-closed (posture enum, key names, declared references, 5 MB caps), so a skipped read surfaces as a `prepare` bounce, not a silent defect.

## Shared Context

Build one shared evidence packet (Full Question + Context; `prepare` injects the canonical Constraints, How-to-answer, and Grounding blocks) before composing prompts. Prefer compact digests over full file dumps. Write it to a temporary file once; every agent receives a short launcher referencing this file plus its unique lens. If the packet cannot be duplicated cleanly across all agents, the task is too large for Prism.

**Neutral framing (author the packet objectively):** The packet is shared, redundant input, so any slant in it primes *every* agent the same way and manufactures false consensus — the exact failure Prism exists to avoid. Frame the Full Question, sub-questions, and lens notes to prime **no verdict**: describe *what to weigh*, never *what to conclude*. Keep your own tentative answer, ranked hypothesis, or expected outcome **out** of the packet — that belongs in your private pre-position (Step 2: Self-review), weighed *against* the fan, not broadcast to it as a shared prior. No leading language or thumb-on-the-scale emphasis; a lens note tilts *attention*, not the answer. If the user's own question arrives slanted, preserve it **verbatim** (don't sanitize or reframe it — see the template's *unchanged* Full Question) but don't amplify the slant in the Context you add, and flag it in your Step 2 pre-position so synthesis can watch for a fan that merely echoed the framing.

**Reference materials (REQUIRED):** Before building the packet, identify all reference materials relevant to the question — CLAUDE.md files, READMEs, configs, docs, skill definitions, style guides, or any file an agent would need. Agents cannot discover references on their own; if a file is not listed, the agent will not consult it.

- **Preferred — `Include:` in the dispatch.** Add `Include: <spec>` lines to the dispatch file (`/abs`, `@base-relative`, or single-level glob; plus `Include-Base:`, `Include-From: <list-file>`, `Include-Tree: <dir>`). At `prepare` time `filectx` resolves them once — generating the packet's `### Reference Materials` for the path-reading tiers **and** the gpt-pro inline list — validated, deduped, and **secret-scanned, fail-closed** (a **best-effort** deny-list of common secret files/token formats — `.env`, keys, `AKIA…`/`sk-…`/`ghp_…` etc. — refused; it is not exhaustive, so still review what you attach; override one path by excerpting it or `FILECTX_SECRETS=warn`). `scaffold` pre-prints the commented `Include:` slot, so you see the affordance every time. **`Include:` is the single source — it cannot coexist with hand-written `Reference:` keys or a `### Reference Materials` block in the packet.**
- **Manual fallback.** You may still hand-author a `### Reference Materials` list of **absolute paths** in the packet's Context (and/or `Reference:` keys for the gpt-pro-only inline list). Use this for a bespoke split or when `filectx` is unavailable; otherwise prefer `Include:`.

**Independent research for live-research tasks:** When the task requires *online* research — current facts, fresh docs, version-specific behavior, anything not settled in the repo or packet — do **not** have the orchestrator research it once and front-load the findings (a single front-loaded evidence set collapses cross-lens/cross-model diversity into a shared-evidence monoculture). Instead, state in the packet the **exact** live question(s) to answer plus any **common evidence floor** (a few authoritative sources every agent must consult and may *extend*, never replace), and direct **each agent to research the live question independently, to sufficiency rather than exhaustion, and cite + list the sources it used.** This stays redundancy, not division of labor — every agent still answers the *whole* question; only evidence-gathering is parallelized. The common floor keeps divergence comparable, and the listed sources let synthesis distinguish an information asymmetry from a genuine reasoning split (Step 4 / Step 5). Still front-load **stable** context (repo files, CLAUDE.md, configs, the question) via Reference Materials — the carve-out is for *live* evidence only and is never an excuse to skip the packet. If a research-tilted lens lands on a tier that can't reach a needed source, route that lens to a full-web tier or front-load that one source **for all agents** (labeled as provided, so the packet stays identical) — never front-load it for the gapped tier alone.

### Shared Packet Template

Write this to `/tmp/prism-<unique-id>.md` with the Write tool (one call, before any dispatch; use a unique id to avoid collisions between concurrent runs). **Write only Full Question + Context** — attach files via `Include:` in the **dispatch** (`prepare` generates the `### Reference Materials` section from them; hand-author that block here only as a manual fallback, and never alongside `Include:`). `prepare` injects `## Constraints`, `## How to answer`, and `## Grounding external facts` when absent, so you never hand-copy them.

```
## Full Question

{User's COMPLETE question/task, unchanged. Identical across all agents.}

## Context

{Shared evidence packet. Identical across all agents. Nest ALL domain content here as `###` subsections — background, constraints, sub-questions, lens notes. `## Full Question` and `## Context` are the only top-level `##` sections you author.}

<!-- Reference Materials: attach files via `Include:` lines in the DISPATCH (see Shared Context →
     Reference materials). `prepare` generates the packet's `### Reference Materials` from them,
     secret-scanned. ONLY hand-author a `### Reference Materials` block here as a manual fallback
     when NOT using Include — having both makes `prepare` abort (fail-closed, by design). -->

### Live research (omit unless the task needs live online facts)

{Name the EXACT question(s) each agent must research independently, plus any common-floor sources. Do NOT front-load findings. See the Independent research rule.}
```

`prepare` appends the canonical blocks (`templates/shared-{constraints,how-to-answer,grounding}.md`) only when absent — idempotent, so re-runs never double them. **It keys on the exact reserved heading, so a prefix-collision heading that is not the exact `##` (`## Constraints on the program`, `## How to answer the question`, …) fails closed naming the offender — keep domain content under `## Context` as `###` subsections.** To override one deliberately, author that exact `##` heading yourself (Constraints then still **fails closed** without the anti-recursion sentinel). The packet is **frozen** after `prepare` runs; agents read it live.

Launcher prompts are committed templates in `templates/` with `{{PLACEHOLDER}}` slots filled by `prism-launch` (one relay template per prompting style, selected by `relay/peers.json`'s `template` field; anti-recursion is the first line of every template). Don't hand-regenerate them. (Adding a peer/template is a `peers.json` + `lens-catalog.json` change — see README.)

## Execution Spine

The authoritative run path. `PL` = `~/.claude/skills/prism/scripts/prism-launch` — **always the absolute path**, never the bare name (the bare command is on PATH only when the shell inherited `.zshenv`; a sandboxed/non-zsh shell will not have it, and a bare-name miss must NOT trigger the manual fallback). Every subcommand needs `jq` in PATH. `prism-launch` cannot dispatch Claude subagents (only Claude can invoke the Agent tool, never `claude -p`) — you issue those Agent calls yourself.

**1. Resolve the invocation shape** (per *Invocation* + the Config-presence gate) and emit the `8N+M` status line.

**2. Write the shared packet** `/tmp/prism-<id>.md` — just `## Full Question` + `## Context` (attach files via `Include:` in the dispatch, not a hand-written block). Add a `### Live research` block only if the answer depends on live online facts (don't front-load findings). `prepare` injects Constraints / How-to-answer / Grounding.

**3. Write the dispatch file** `/tmp/prism-<id>.dispatch` **with the Write tool** (one record per agent — never a shell heredoc, and **never `scaffold > file` then edit it**). Run `PL scaffold --n <N>` first to **print** the `Prism-Mode` contract + all records in canonical order to stdout — use that output as a **copy-from template**, then author the whole dispatch in **one Write call**, replacing the `FILL` lens names + descriptions. (Authoring a brand-new file with Write needs no prior Read; *redirecting* scaffold into the dispatch and then editing it forces a wasted Read, because the harness does not track shell-created files. The line format below exists precisely so the Write tool can author it with no escaping.) At `N ≥ 2`, give each copy a **distinct** lens name — e.g. `Adversarial-A`/`-B` — `prepare` rejects duplicates. `--preset review|design|diagnosis|compare|research|decision|writing` pre-fills eight lenses (N=1), often leaving **zero** FILLs to replace. **Fastest path when a preset fits:** `PL scaffold --preset <type> --packet /tmp/prism-<id>.md --out /tmp/prism-<id>.dispatch` writes a complete, prepare-ready dispatch **directly to the file** (no Write/Edit step at all) — `--out` requires `--preset` + `--packet` so it can only ever emit a zero-FILL file (a FILL skeleton written to a file would just re-create the Read trap). **For gpt-pro:** add `--m <M>` (to any scaffold form) to emit `M` ready `Type: gpt-pro` records with canonical postures — no hand-writing the gpt-pro format; `--n 0 --m <M>` scaffolds a gpt-pro-only run (`Prism-N: 0`, legal only with `M ≥ 1`). **For a no-subagents (external-only) run** (user asked to drop the Claude subagent tier): `PL scaffold --no-subagents [--n N] [--m M] [--preset T]` emits the recognized `Prism-Mode: partial` + `Variant: no-subagents` shape (7 parallax at `N`, zero subagents) — add `--partial-user-quote "<user's words>"` with `--out`. The format is plain `Key: value` lines in blank-line-separated records — no braces/commas/quoting/escaping.

`scaffold --n <N>` prints this exact canonical contract + all eight records to stdout — copy from there. **The full annotated example + exhaustive key grammar (record types, required keys, the `Effort:`-rejected and injection-token rules) live in `references/dispatch-shapes.md`; read it when hand-authoring beyond what `scaffold` prints** (custom lenses, `N>1`, exclusions, no-subagents, gpt-pro-only, or after a `prepare` bounce).

**Roster contract** (top-level lines — `scaffold` emits them, so full is the path of least resistance):

```text
Prism-Mode: full
# Prism-N: every standard tier + subagents must be present at N (the floor check).
Prism-N: 1
# Prism-M: gpt-pro count.
Prism-M: 0
```

`prepare` then runs a **default, fail-closed** floor check: if any standard tier is missing or off-count it aborts naming the tier, before any launcher or manifest is written.

**Authorizing a reduced roster (the one authoritative how-to).** A partial roster is allowed **only when the user explicitly asked for it** (an exclusion or subset in their own words — never your inference, and never "cost / it's slow / it's flaky / these are enough"). Declare it as a high-friction, audited waiver — the double-confirm:

```text
Prism-Mode: partial
Partial-User-Quote: "<paste the user's exact words, verbatim, in double quotes>"
```

Rules: `partial` **omits** `Prism-N`/`Prism-M` (the shape is asymmetric — the records *are* the shape). The quote is stored **verbatim** — paste the user's actual words, do not paraphrase (an unverifiable paraphrase defeats the audit; `prepare` records it but cannot prove it). `prepare` records the quote + dropped tiers in the manifest `.shape` and prints a loud `⚠ PARTIAL` warning; **cite that quote in your synthesis** so a fabricated authorization is visible to the user. A `partial` with no (or whitespace-only) quote, or any `--dispatch` with **no** `Prism-Mode` line, is rejected — the enforcement cannot be dodged by omission.

**No-subagents run — the one recognized, floor-checked reduced shape.** When the user asks to drop *only* the Claude subagent tier (keeping the parallax fan), don't hand-author a bare partial — let `scaffold --no-subagents` emit it, or write the `Variant` form yourself:

```text
Prism-Mode: partial
Variant: no-subagents
Prism-N: 1
Prism-M: 0
Partial-User-Quote: "no subagents"
```

This is the **only** partial shape that keeps `Prism-N`/`Prism-M`: the Variant makes `prepare` floor-check the kept tiers (all 7 parallax at `N`, **zero** subagents, gpt-pro at `M`) — so an external-only run gets the same completeness guarantee a `full` run does, without a new top-level mode. Because it is a principled, diversity-preserving shape (not a suspicious drop), `prepare` prints a **calm informational line, not `⚠ PARTIAL`** — but it still records + expects the quote (it is a user-authorized tier exclusion; cite it in synthesis). `Variant:` is rejected on `Prism-Mode: full`, and only `no-subagents` is defined. **Fastest path:** `PL scaffold --no-subagents --preset <type> --packet … --out … --partial-user-quote "<user's words>"` writes a zero-FILL, prepare-ready external-only dispatch (the heaviest preset lens shifts onto GPT `xhigh`, so adversarial coverage survives the dropped subagent slot).

**4. Prepare** (foreground): `PL prepare --dispatch /tmp/prism-<id>.dispatch`. It compiles the dispatch into a normalized config (kept for audit), validates, renders all launchers, prints each subagent launcher's contents inline + the parallax command + the expected notification count, and writes `<id>-manifest.json`. If it exits non-zero, fix the packet/dispatch and re-run — nothing has been dispatched. (Note: `prepare` injects the canonical blocks into the packet *before* it validates the dispatch, so a failed run can leave the packet already mutated on disk — **Read it again before editing it**.) (`prepare --config <config.json>` is the lenient raw-JSON escape hatch; `--expect-n N [--expect-m M]` still works and OVERRIDES the contract's N/M on a **full/unchecked** run — useful on `--config`. It is **ignored on any `partial` run, including `Variant: no-subagents`** (prepare prints a note): there the floor uses the dispatch's own `Prism-N`/`Prism-M`, so edit those, not `--expect-*`. See "What prepare enforces" below.)

**5. Launch all lanes concurrently** (`run_in_background: true`) — do not serialize:
- **Parallax — ONE backgrounded Bash call:** `PL parallax /tmp/prism-<id>-manifest.json` (set the Bash `timeout` above `PRISM_PEER_TIMEOUT` (default 3600s), e.g. `3660000`). Fans out every relay call, waits for all, yields one completion notification.
- **Subagents:** one **Agent** call per subagent, using the launcher contents `prepare` printed inline (never `claude -p`). **In a no-subagents run there are zero subagent records → issue zero Agent calls** (`prepare` prints no subagent launchers; the only Claude perspective is self).
- **GPT-Pro (only if `M > 0`):** fire one backgrounded `gpt-pro < … > … 2> …` Bash call per lens (`timeout: 7260000`) — the exact line `prepare` printed.

Do not poll or sleep-loop — the system notifies you when agents finish.

**6. Wait for ALL** (HARD GATE — see Step 3 below), then **7. Safety check + collect** (Step 3.5; `PL results <manifest>` → read `.res.md`; `PL digest` first for large/high-volume runs), then **8. Synthesize** (Step 4) and optionally `PL clean <id>`. (`results` exit codes: `0` all done · `1` a peer/lens failed — retry with `parallax --only` · `2` a lane still pending, e.g. gpt-pro — not a failure, but not ready to synthesize. It covers **parallax + gpt-pro only** and checks the result against the manifest's full peer set (a partial result reads as `2`/INCOMPLETE, never done); confirm each **subagent** completion notification separately — they have no on-disk artifact.)

**What `prepare` enforces** (so this prose can defer to it on the `--dispatch` path): fail-closed on packet sections, misplaced dispatch keys, canonical-block injection, the launcher `CRITICAL:` prefix, dispatch shape, the `full`/`partial`/`Variant: no-subagents` floor checks, effort derivation, duplicate lens/slug, gpt-pro references + 5 MB caps, `N=0` legality, injection tokens, and zero-records — **the full per-check inventory lives in `references/dispatch-shapes.md`** (read it when diagnosing a `prepare` bounce). **What you still own:** parsing the invocation + Config-presence gate; choosing N/M; whether a `partial` quote is genuinely user-authored; non-duplicative lenses (the two checks below); live-research instructions; launching all lanes concurrently; waiting for all; self-review; synthesis.

**Pre-launch judgment checks (yours — not script-enforced):**
- **Redundancy test:** Swap any two agents' lenses. If the prompts become incoherent, you have divided labor (tell-tale: scope, evidence, tools, output format, or deliverables differ between prompts). Applies across tiers too — a GPT lens and a DeepSeek lens should be swappable in principle (only the prompt format differs).
- **Lens quality test:**
  - Each lens name is a weighing posture (1-3 words), never a task or role.
  - **Select by axis family — at most one per family** (see Lens Axes); field a second from a family only when you can state how the two differ *on this task*.
  - **Adversarial coverage is opt-in:** include an adversarial-family lens (Adversarial, Falsification, Disconfirming, Risk) only when the answer turns on surfacing a non-obvious flaw/attack/failure-mode no other lens covers — name the specific risk first; if you can't, use an exploratory lens. **But omission must be deliberate:** if the task proposes/evaluates/changes something and you field *no* adversarial lens, name which lens covers "what could go wrong"; if none does, add one. Silent omission is a check failure.
  - Never assign the same lens to two of GPT, GLM, Kimi, DeepSeek, MiMo, or the Grok tiers.
  - If an adversarial lens carries the heaviest reasoning load on a subtle technical question, assign it to Claude or GPT (`xhigh`); if a parallax tier must take it, prefer a middle-tier peer over DeepSeek/MiMo.

**Manual fallback (TRUE last resort — only if the script file is genuinely missing):** A bare-name "command not found" is **NOT** a trigger — re-invoke by the absolute path. The manual flow applies **only** when `~/.claude/skills/prism/scripts/prism-launch` does not exist at all (a broken install); it bypasses **every** mechanical guard, so never reach for it to "move faster" or to dodge a floor-check failure (that failure is the system working — fix the dispatch). **The invariant holds even here: enforce the FULL roster yourself — no family omitted unless the user explicitly authorized it.** First repair the install (`cd ~/dotfiles && ./dotfiles.sh`); **if repair is impossible, read `references/recovery.md`** for the launcher-render + per-peer relay dispatch procedure.

### Step 2: Self-review

While agents run, form your own position independently. Your lens is **Integrator Lens** — you weigh holistic coherence, feasibility, and alignment with the user's goals. Write your tentative recommendation before opening any agent output.

Since you composed the prompts and chose the lenses, your self-review is not fully independent. When dispatched agents diverge from your position, give their perspectives slightly more weight on points you may have anchored on during prompt design.

### Step 3: Wait for ALL agents (HARD GATE)

**Do not synthesize, summarize, or present results until EVERY dispatched agent — including all Parallax tiers and every GPT-Pro lens — has returned.** This is a hard gate, not a suggestion. Having "enough" subagents is never a reason to skip the remaining agents. One peer finishing first (GPT, Grok, GLM, Kimi, DeepSeek, MiMo, or the parallax batch) is never permission to ignore the others — and **gpt-pro is expected to be the last to return**, so "everything but gpt-pro is done" is the expected state, never a reason to synthesize.

**Parallax is slow, gpt-pro slowest** — relay calls routinely take 2-5x longer than subagents; a gpt-pro lens is 5–20 min. Do not diagnose, retry, report failure, or proceed while a background task is running. With `prism-launch parallax`, **all parallax peers finish under a single completion notification**; **each gpt-pro lens is its own notification**. So the notification count = (1 per subagent) + (1 for the parallax batch, if any) + (1 per gpt-pro lens) — `prism-launch prepare` prints the full count; wait for exactly what it printed. While waiting, work on your self-review (Step 2), then wait silently.

**Handling failures (after completion notification only):**
- **Relay transport failure:** run `prism-launch results <manifest>` — any peer with `status: "error"` failed. Retry just that peer with `prism-launch parallax <manifest> --only <peer-name>` (backgrounded; re-dispatches one peer and merges the result back — do not re-run the whole fan). Don't read the `.log` sidecar.
- **Answer-quality failure** (empty, truncated, off-topic): Offer the user: (a) retry, (b) proceed with reduced perspectives, or (c) abort.
- **Provenance failure** (the answer can't be attributed to the model it was dispatched to — a gpt-pro run with `status: "error"`, any model-audit failure): the lens is **VOID regardless of how good the text looks**. A complete, well-formed, on-topic answer from an *unverified* model is precisely what the audit rejects — **quality is not evidence of provenance**, so "the response is complete, so fetch it from the run dir" is the defect, not the recovery. Never read a failed run's answer file into a lens, digest, tally, or synthesis — neither `response.md` nor the `response.rejected.md` the engine renames it to when the model audit rejects a turn. Same three options — but for gpt-pro (a) is a **fresh run with a new run-id**, which re-burns 5–20 min of Pro quota, so the **user decides**; there is no in-place retry and no override for the audit (see GPT-Pro tier).
- **Only these post-notification failures justify proceeding without Parallax.** "It's taking a long time" is never a failure.

### Step 3.5: Safety check

Before synthesizing, check whether a dispatched agent violated read-only by writing to the working tree:

```bash
git diff --stat HEAD
```

**NEVER revert, restore, checkout, stash, reset, or clean the working tree — not even changes that look "unexpected" (HARD RULE).** `git diff` here is **read-only detection only**; you never "clean up" what it shows. The tree may hold *uncommitted* work that is **not yours**: the user's in-progress edits, or a **concurrent prism / Claude Code session** in the same repo. Discarding it is **unrecoverable** — this is a real incident (a concurrent prism run wiped an uncommitted change it found but had not made), not a hypothetical.

If the diff shows changes, do **not** assume your agents made them, and do **not** auto-attribute or undo them — **flag them to the user and let them decide.** "Discard the offending agent's output" means *ignore that agent's `.res.md` text in synthesis*; it is **never** a git operation on the tree. If you need a clean baseline, commit your *own* work first — never revert someone else's.

Scan each agent's output for **cross-model recursion** indicators: a nested Prism run, a `relay call`, or dispatch to another model (a model-tier tally or synthesis-style `Dissent:`/`Why:`/`Do now:` structure hints it ran its own Prism). An agent using its *own* same-model subagents is now permitted — do not flag that; flag only a nested Prism run or cross-model dispatch, which contaminates the lens's independence.

### Step 4: Synthesize

Write a skim-first, verdict-led synthesis, not a lens-by-lens report — the reader should grasp the recommendation, confidence, and any cross-model dissent in seconds. The verdict line carries those three; the body carries the reasoning.

**Default budget: ~100-150 words in the visible main path.** If you're writing more, you're hedging or scaffolding — compress. Deliverables are bounded by the artifact; the optional appendix is uncounted.

**Large or high-volume runs — read digests first, deep-read selectively.** Every agent ends its answer with a `## Digest` block. When reading every full `.res.md` would degrade synthesis — by default at ~12+ dispatched (N≥2), but also a smaller run whose combined outputs are large (verbose lenses, gpt-pro lenses present, near a context limit) — run `PL digest <manifest>` to extract each parallax peer's digest into one small lineage-tagged file; read that plus each subagent's digest (already in your conversation) to form the verdict and by-lineage tally, then deep-read the full `.res.md` **only** for peers whose digest dissents, looks weak/off-topic, advances a materially novel rationale or `Dissent/caveat` even while its Position aligns, or is the tie-breaker. The digest **compacts inputs, it never decides** — you compute the verdict, confidence, and tally yourself, and must read a dissenter's raw words before capping confidence on it. At N=1 the full reads are usually cheap — skip the digest unless volume warrants.

**Default skeleton — the verdict line is fixed and always first; the body below it flexes by mode (see Mode adaptation):**

1. **Verdict line** — one line, the first thing the eye hits. Fixed token order, `·`-separated:

   `<verdict, aim ≤12 words> · conf: <High|Moderate|Low> · <n>/<total> agree[ · ⚠ dissent]`

   - `<n>/<total>` counts **perspectives that returned, including self** (= `8N+M+1` per the **Counting Contract**: the default `N=1` run is `/9` = self + 8 dispatched; `prism 2` (no gpt-pro) is `/17`; **add each returned gpt-pro lens** — `prism 2 2` that fully returns is `/19`; a gpt-pro-only `prism 0 4` is `/5`; a **no-subagents** run is `7N+M+1` — `prism no subagents` is `/8`) — *not* dispatched-only, *not* lineages. A gpt-pro lens that failed terminally does **not** count toward `total`; name the missing perspective rather than silently shrinking the denominator. The tally below counts *lineages*; the two denominators intentionally differ. (Self is a perspective here even though it does not count toward *dispatch* shape elsewhere.)
   - For an **exploratory question** with no proposition to vote on, swap `<n>/<total> agree` for `<n>/<total> aligned` (or `· converging` / `· divergent`) and let the verdict line state the synthesized finding. Confidence is still shown.
   - Confidence is **always shown** — the *absence* of a `⚠ dissent` clause is itself the all-clear signal.
   - The `⚠ dissent` clause appears **only** when a dispatched agent dissents. On a cross-model break the tally and Dissent line already name the peers, so the verdict clause stays a bare `⚠ dissent`; name a peer inline (`⚠ DeepSeek dissent`) only for a minor dissent that has no tally. `⚠` is the only routine glyph — reserve it for dissent.
   - Deliverable: the verdict line points at the artifact (`See migration plan below · conf: High · 9/9 agree`), which follows immediately.
   - **Render the header as a compact two-column table whenever it is dense — independent of whether the run converged.** "Dense" is any one of: the verdict needs more than ~12 words, there is a caveat or secondary item, or there is a dissent note. A caveat gets its **own row**; never pack it into the verdict clause. Same fields, same content, far more readable:

     | Summary | Detail |
     |---|---|
     | **Verdict** | NO-SHIP as-is — fix the cluster, then ship |
     | **Confidence** | High |
     | **Consensus** | 6 reviewers convergent — 1 severity split, 1 finding discounted |
     | **Caveat** | 1 latent high-severity item to resolve first *(omit row if none)* |
     | **Dissent** | DeepSeek+MiMo, same direction *(omit the row when there is none)* |

     Use the single `·`-separated line **only** when verdict + confidence + tally genuinely fit one short line. When in doubt, table it.

2. **Model-tier tally** — one line, **only on a cross-model break** (a parallax lineage dissents). Group by model lineage (not by lens): each dispatched lineage with `✓` (aligned) or `⚠` (dissented), then the takeaway.

   `Claude ✓  GPT ✓  DeepSeek ⚠  MiMo ⚠   → 2 independent lineages dissent, same direction`

   Omit on full convergence and on an intra-lineage split (use the `Tradeoff:` line instead). List only the lineages actually dispatched (treat the two Grok tiers as one `Grok` lineage; gpt-pro is its **own** `GPT-Pro` lineage, kept separate from GPT despite the shared OpenAI family). A lineage that ran several agents collapses to one `✓`/`⚠`: mark `⚠` if **any** member raised a cross-model dissent you could not refute, and resolve its aligned position by strongest reasoning, not majority vote. This tally is the **one sanctioned exception** to the per-lens-attribution ban: it attributes by *lineage*, never lens-by-lens.

3. **Dissent** — its own labeled line **on a cross-model break**, placed above Why: the peer(s), the *specific* argument, and what would resolve it ("DeepSeek+MiMo: shared state needed for atomic txns — bounded by the spike gate; revisit if p99 > 50ms"). With two or more distinct dissents, a `Peer(s) | Argument | Resolution / trigger` table beats stacked lines. When dissent is minor, fold it into a Why bullet. Never compress dissent to a bare model name — the argument and its resolution path are the signal.

4. **Why** — 2-4 tight bullets of decisive reasoning. Each bullet is conclusion **plus** its basis ("Removes the shared-state layer — root cause of 3/5 recent incidents"), never a bare label ("simpler").

5. **Do now** — 1-3 verb-first actions, often a single arrow chain (`spike B → kill the A RFC → freeze schema`). Skip if the verdict is itself the action.

**Mode adaptation (the verdict line never moves; the body flexes):**

| Mode | Tally | Dissent line | Body |
|------|-------|--------------|------|
| **Converged** — all perspectives agree | omit | omit | Why (+ Do now). Often 3-5 lines total. |
| **Material disagreement** — ≥2 agents oppose on the core question, not following lineage cleanly | omit | fold into Why | `Tradeoff:` (the two options + what each optimizes) before Do now |
| **Cross-model break** — subagents converge, a parallax or gpt-pro lineage dissents | **mandatory** | **leads the body**, above Why | cap confidence at Moderate |
| **Deliverable** | per the run | per the run | artifact right after the verdict line; Why = design rationale; Do now = integration/review |

- On a **cross-model break**, two or more cross-model peers (GPT, GLM, Kimi, DeepSeek, MiMo, Grok, **gpt-pro**) dissenting in the *same direction* is an especially strong signal — say so. The Moderate cap fires when any **external non-Claude lineage** dissents. One caveat: when a dissent turns on a *cited external fact the other agents never had* — gpt-pro in a front-loaded run, or any tier on a live-research run where each surfaced different sources — that is an **information asymmetry, not a shared-blind-spot signal** — spot-check the cited source, propagate the fact, and re-judge rather than reflexively capping.
- **All-subagent run** (no parallax dispatched): a cross-model break is impossible, so within-Claude splits are **Material disagreement** however clean — no tally, no Moderate cap. Flag the missing cross-model diversity.
- **No-subagent run** (the recognized external-only shape — no Claude subagent dispatched): the mirror image. `n/total = 7N + M + 1`; **self is the lone Claude perspective** (and is *not* independent — you composed the lenses, so weight dispatched dissent slightly higher). The tally lists only the dispatched non-Claude lineages — there is **no `Claude ✓` row** (self is never in the tally). Same-model-blind-spot discounting all but vanishes (no Claude fan to discount); every dissent is cross-model, so the Moderate cap fires readily and the cross-model-break mode is effectively the default. Cite the `Partial-User-Quote` that authorized dropping the tier.
- **`Tradeoff:`** (material disagreement) is an option comparison — render as a small table (`Option | Optimizes | Cost / risk`), not prose.

**Banned in the main path:**
- Per-lens attribution ("the Simplicity lens noted…", "Agent A said…"). The model-tier **tally line is the sole exception** (by lineage, not lens). Deeper per-lens notes go in an optional `<details>` appendix at the very bottom — only if the user asked, or disagreement is deep enough to need a lens-level audit.
- Synthesis narration ("Weighing the perspectives…"). The verdict line and Why carry the reasoning.
- Generic contingencies ("if requirements change"). Only concrete, observable triggers.
- Routine chrome: emoji beyond the reserved `⚠`, ASCII-art boxes, traffic-light symbols. Use words for confidence and `✓`/`⚠` in the tally. A plain `→` as a prose separator is fine — it is text, not chrome.
- Standalone `Confidence and basis` / `Key dissent` / `Contingencies` sections. Their content folds into the verdict line, Dissent line, and Why.

**Cross-model weighting (internal — surfaces through the verdict line, tally, and Why):**
- Judge each answer on its reasoning and evidence, not on the fact that an agent produced it (discount weak reasoning, never the model label). Discarding a shallow, wrong-premise, off-topic, or unsupported answer entirely is valid — say so in Why when a notable perspective is set aside.
- Ignore any self-reported confidence a dispatched agent volunteers — prism confidence is computed by the orchestrator from cross-model agreement + reasoning quality, never from an agent's self-score. Treat a volunteered score only as a cue to read the caveat beside it; do not instruct agents to self-score.
- Same-model convergence is discounted (shared training = shared blind spots); parallax (cross-model) confirmation or dissent carries outsized weight — model diversity is prism's entire point.
- A single well-reasoned point can beat consensus driven by shared priors. If you cannot articulate why dissent is wrong, downgrade confidence rather than expanding dissent into a paragraph.

Agents advise; they do not vote. The tally shows lineage alignment, not the decision rule — convergence is evidence, not a vote.

### Step 5: Grounding check

Re-read the user's original question. Verify: your synthesis answers it directly (and produces any requested deliverable); the header leads in fixed field order with confidence shown and any caveat in its own row; on a cross-model break the tally + Dissent line sit above Why, on material disagreement a `Tradeoff:` carries the split (no tally), on full convergence all three are omitted; no per-lens summary in the main path; every retained dissent/caveat/trigger changes a decision, confidence, or next action. **Live-research runs:** before treating divergence as a reasoning split, compare the agents' listed sources — a dissent resting on a fact the others never had is an *information asymmetry* (propagate the fact and re-judge), not a shared-blind-spot signal.

Optionally delete all temp files: `PL clean <id>` (or `rm -f /tmp/prism-<unique-id>*`) — both clear the whole `/tmp/prism-<unique-id>` prefix (packet, dispatch, normalized config, manifest, launchers, out logs, result). `clean` refuses a gpt-pro lens whose `.log` shows a `run_id` but has no `.res.md` yet (a possibly-live worker) unless `--force`.

## Lens Assignment

A lens is a **weighing posture**, not a task variant. Do not put the task noun in the lens name. Choose lenses on **orthogonal tradeoff axes**; before adding one, write one sentence on how it differs from every existing lens. The symmetric default dispatches eight agents, so aim for **eight distinct postures**; if the task can't support that many, keep the full fan and field the best distinct posture on each tier — **never drop a tier to dodge lens scarcity** (a tier is excluded only on explicit user instruction). At `N ≥ 2`, give each copy a distinct lens where the task supports it; deliberate same-*posture* redundancy on a pivotal question is allowed, but each agent still needs a **distinct lens name** (e.g. `Adversarial-A`/`Adversarial-B`) — `prism-launch` rejects duplicate names. At `N=1` there is one Claude subagent slot: when a risk-bearing question wants its adversarial lens on Claude or GPT, accept it on GPT (`xhigh`), or bump `N` — do **not** drop a Parallax tier to free a Claude slot.

On a **live-research task**, also weigh tier web-reach when placing research-tilted lenses (see the Independent research rule).

### Lens Axes

Lenses are grouped into **axis families**. `templates/lens-catalog.json` mirrors this machine-readably (each lens's `axis` + one-line `desc`) and is what `prism-launch` reads to fill scaffolds — edit a lens's description or axis there. **Pick at most one lens per family per run;** field two from one family only when each earns its slot by a distinct on-task emphasis (research/exploration and writing legitimately do this). This is the unit of selection — **choose by axis, not by scanning names.**

| Axis family | What it weighs | Member lenses |
|---|---|---|
| **Search** | coverage vs depth | Breadth-Weighted · Depth-Weighted |
| **Reframe** | a different basis, prior, frame, or non-obvious option | First-Principles · Outsider · Reframe · Lateral-Generative |
| **Evidence** | empirical grounding and correctness | Empirical · Correctness |
| **Mechanism** | cause and effect | Causal |
| **Challenge** *(opt-in)* | attack, downside, disproof | Adversarial · Falsification · Disconfirming · Risk |
| **Human / Value** | affected parties and reception | Stakeholder · Audience · Clarity |
| **Delivery** | ship-ability, structural fit, and minimalism | Pragmatist · Simplicity · Structural |
| **Time** | lifecycle, sequencing, reversibility | Temporal |
| **Self** | holistic synthesis (orchestrator only) | Integrator |

The menu stays **open** — mint a task-specific lens when you can name its axis in one sentence and slot it into (or beside) a family. **`Disconfirming` vs `Reframe`:** `Disconfirming` is adversarial (Challenge family, subject to the opt-in gate); `Reframe` is exploratory (an alternate prior/framing, an orthogonal default) — do not relabel an attack posture as a frame to evade the opt-in gate. **`Structural`** (Delivery) is the build-quality pole — reach for it on the *durable fix vs. expedient hack* call; it's one Delivery pole, so don't field it with `Simplicity`/`Pragmatist` as if independent.

**Suggested lenses by task type:** `scaffold --preset review|design|diagnosis|compare|research|decision|writing` pre-fills eight lenses by task type — the authoritative ordered sets live in `templates/lens-catalog.json` (`.presets`); edit a preset there, not here (the per-task-type starting sets are listed in README). Implementation has no preset — compose it by hand.

## Guards

- **No cross-model recursion (HARD RULE):** Dispatched agents must never start a nested Prism run or invoke a cross-model dispatch skill (prism, relay, gpt-pro-relay, deep-research) or call another model — pulling in a different model destroys the lens's independence. They MAY, at their own discretion, spawn their own same-model subagents (kept terminal: read-only, no further spawning, no cross-model dispatch, no response-file write). Read-only analysis skills are permitted; side effects are not. The Constraints section and launcher prompts both enforce this — do not weaken or omit either. Keep the anti-recursion warning at the top of every heredoc; the orchestrator-composed gpt-pro launcher carries the same guard as its first line.
- **No contamination:** Write the shared context file and compose all launcher prompts before any launch. Do not modify the shared file or revise prompts after seeing early agent outputs. Keep the packet neutrally framed — no orchestrator verdict, hypothesis ranking, or leading language priming the fan (see *Shared Context* → Neutral framing).
- **No all-same-model dispatch (HARD RULE):** The dispatched parallax peers must equal the resolved parallax counts — `7N` by default, minus any tier excluded by explicit user instruction. Via `prism-launch` the manifest's `counts` derives this and the single `parallax` call emits exactly those peers. Zero relay **and** zero subagent calls together is legal only as the `N=0` gpt-pro-only shape (valid only when `M ≥ 1`). A **no-subagents** run (`Variant: no-subagents`) satisfies this trivially — it is `7N` cross-model peers with zero subagents (maximally cross-model); but if relay then goes down it must **refuse or degrade to gpt-pro-only**, never substitute subagents (see Parallax → relay unavailable). A run with **no surviving external lane** (parallax down/empty **and** `M = 0`) is refused.
- **No early synthesis (HARD RULE):** Do not synthesize until every dispatched agent has returned its completion notification. "Subagents are done, GPT relay is still running" is not a reason to proceed — it is the expected state. Proceeding without any tier's results voids the entire Prism run.
- **No side effects:** Dispatched agents must not edit files, commit, push, or invoke any skill with side effects (e.g., push, xurl, todo, goal-drive). Read-only analysis skills are allowed. The only permitted write is the relay response file (`.res.md`).
- **No working-tree reverts (HARD RULE):** Neither the orchestrator nor any dispatched agent may run a git command that discards or hides uncommitted work — `git restore`, `git checkout <path>` / branch switch, `git reset`, `git stash`, `git clean`, `git rm`. The repo routinely holds the user's *or a concurrent prism/Claude session's* uncommitted changes; reverting them is unrecoverable (a real incident). Only read-only git is allowed: `git status`, `git diff`, `git log`, `git show`. To get a clean baseline, commit your own work — never undo someone else's. See Step 3.5.

## Degrees of Freedom

The core principle (redundancy, not division of labor), the launcher-template structure, and the hard completion gate are load-bearing — do not relax them. Flexible: lens choices, synthesis body framing, agent count beyond the minimum. The verdict line is fixed and always first (Step 4); the body below it flexes — merge, reorder, or add task-specific sections when the task calls for it.

## When to Use Prism

Use Prism when a task benefits from diverse, redundant judgment and the shared context fits cleanly across all agents. Skip it for trivial lookups, deterministic transforms, single-correct-answer tasks, or tasks requiring parallel mutations of shared state.

Once you've decided to use it, resolve config via the **Config-presence gate**: with an explicit number, honor the parsed shape verbatim (omitted dimensions fall to `N=1`/`M=0`); with none, autonomously pick `N` and `M` per **Choosing N and gpt-pro** (anchored at `N=1`, scaling only when decision risk justifies the cost).
