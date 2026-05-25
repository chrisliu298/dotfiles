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

**Claude-only.** If `ANTHROPIC_BASE_URL` contains `deepseek`, this skill is unavailable — stop and tell the user: "prism is Claude-only; DeepSeek cannot orchestrate other models from inside a DeepSeek session." Prism dispatches parallax via [[relay]], which itself refuses from DeepSeek sessions.

Prism sends the **same complete question** to multiple independent agents. Each agent answers the **entire question end-to-end**. The only thing that changes between agents is the **lens**: what they prioritize and what tradeoffs they weigh more heavily.

## Core Principle

**Prism is redundancy, not division of labor.** Every agent gets the full question, full scope, and full deliverable. The lens changes **emphasis**, not **coverage**. If agents own different files, sections, or outputs, that is division of labor, not Prism.

Convergence across diverse lenses is high-confidence signal; divergence surfaces tradeoffs that need explicit resolution.

## Structure

| Tier | Tool | Role |
|------|------|------|
| Self | (none) | Your own analysis while agents run |
| Subagents | **Agent** | Same-model agents (Claude), one Agent call each |
| **Parallax — Codex** | **Bash** (`relay --to codex`) | Cross-model agents via relay to GPT-5.5 |
| **Parallax — DeepSeek** | **Bash** (`relay --to deepseek`) | Cross-model agents via relay to DeepSeek V4 Pro |

**Default: 5 perspectives** — self + 2 subagents + 1 Codex parallax + 1 DeepSeek parallax. Required dispatch: **2 Agent calls + 2 Bash relay calls**. Self does not count. Both Parallax tiers are included by default; opt out of either tier individually by setting its count to `0`.

### Invocation Shorthand

Override dispatch config with positional args before the question, or use natural language — both work.

**Positional:** `<sub> <codex-count> <codex-effort> <ds-count> [r] <question>`
- **sub** — number of same-model (Claude) subagents (default: 2)
- **codex-count** — number of Codex parallax agents (default: 1, `0` to opt out)
- **codex-effort** — Codex reasoning effort: `m` medium, `x` xhigh (default: `m`)
- **ds-count** — number of DeepSeek parallax agents (default: 1, `0` to opt out). DeepSeek always runs at `max` (DeepThink) — no effort knob.
- **r** — enable anonymous peer review round (default: off)

**Omission rule:** Positions fill left-to-right and you may stop at any point; remaining positions take their defaults. You cannot skip a position — to reach `ds-count`, you must specify the three preceding tokens. When `codex-count` is `0`, the following effort token is still consumed positionally (so the next digit lands in the right slot) and then ignored.

Examples:
- `prism 2 2 x 2 Which architecture should we pick?` — 2 sub, 2 Codex (xhigh), 2 DeepSeek (max)
- `prism 3 2 x 1 Why does X happen?` — 3 sub, 2 Codex (xhigh), 1 DeepSeek (max)
- `prism 1 0 m 1 Same-model + DeepSeek` — 1 sub, no Codex, 1 DeepSeek (max)
- `prism 2 1 m 0 r Should we launch X?` — 2 sub, 1 Codex (medium), no DeepSeek, peer review
- `prism 2 0 m 0 Solo-claude only` — 2 sub, no parallax at all (degraded — flag to user)
- `prism Why does X?` — all defaults: 2 sub, 1 Codex (medium), 1 DeepSeek (max)
- `prism r Should we launch X?` — all defaults plus peer review (`r` may appear before the question)
- `prism 3 Why does X?` — 3 sub, defaults for both parallax tiers (omission rule: trailing positions take defaults)
- `prism 3 sub, 2 codex xhigh, 1 deepseek, with review: Why does X?` — natural language works too

**Parsing:** Read tokens left-to-right. A token is config if it is a single digit, an effort letter (`m`/`x`), or the literal `r` (peer review). Map positionally in this order: digit → sub-count, digit → codex-count, letter → codex-effort, digit → ds-count. The `r` token may appear anywhere among config tokens. The first non-matching token begins the question. Reject effort letters outside `{m, x}` with: "Codex effort must be m or x." Natural language config is also accepted.

**Both Parallax tiers are on by default.** Every run with `codex-count > 0` MUST include that many Bash relay calls to Codex; every run with `ds-count > 0` MUST include that many to DeepSeek. Do not skip, replace with a subagent, or defer. Exceptions: (1) user explicitly set the tier's count to `0`, or (2) `relay` is unavailable (substitute a same-model agent carrying that tier's assigned lens and warn the user about degradation). If your planned dispatch set contains fewer relay calls than `codex-count + ds-count`, Parallax is incomplete — fix before launching.

### Parallax (cross-model agents)

Parallax is dispatched via `relay` to **different models** (Codex and/or DeepSeek). Invoke `relay` directly — not via a subagent that calls relay. The value of each tier is model diversity:

- **Codex** brings GPT-5.5's training, its strengths in agentic code review, and two effort tiers (`medium`/`xhigh`).
- **DeepSeek** brings an entirely independent training lineage (open-weight V4-Pro), distinct prompting conventions, and always runs at `max` (DeepThink).

**Tier strength and lens fit (heuristic, not a routing rule):** Claude Opus 4.7 (subagents) and GPT-5.5 (Codex) are roughly peers in raw reasoning capability. DeepSeek V4-Pro is meaningfully weaker on hard reasoning at peak effort, partially offset by always running at `max` (DeepThink). This does *not* reduce DeepSeek's value — its independent training lineage catches blind spots the other two share, which is the entire point of model diversity. The asymmetry should inform lens assignment only:

- **Subtle hard-reasoning lenses on risk-bearing questions** (Adversarial / Falsification / Disconfirming on a technical proposal where finding the non-obvious attack is the deliverable): prefer Claude subagent or Codex at `--effort xhigh`. If exactly one lens carries the heaviest reasoning load and it lands on DeepSeek, you've under-resourced the most decision-relevant role.
- **Lenses where the value is a different prior** (Outsider, First-Principles, Disconfirming-via-different-frame, Breadth-Weighted, Risk, Alternative-Framing): give these to DeepSeek. Its independent lineage is the asset; raw reasoning depth is not the bottleneck.
- **Both parallax lenses comparably hard:** no swap needed.
- **Never drop DeepSeek to "upgrade" a run.** Lineage diversity is non-substitutable; default tier inclusion is unchanged.

This affects assignment only. In synthesis, DeepSeek dissent retains full cross-model weight — discount weak reasoning, never the model label. Treat the ranking as approximate; revisit when model versions change (the named model versions above are the canary — when they look stale, this section is stale).

Assign each tier a lens that maximizes diversity. **Default to orthogonal exploratory lenses** (Breadth-Weighted, Depth-Weighted, Outsider, First-Principles, Disconfirming-via-different-frame) — these almost always extract more from cross-model diversity than a second attack angle. **Reach for an adversarial lens (Adversarial, Falsification, Disconfirming) only when it is much more valuable than another orthogonal lens would be** — i.e., the deliverable hinges on finding a non-obvious flaw, attack, or failure mode, and no other dispatched lens is already covering that ground. When that bar is met, put it on the parallax tier best suited to the reasoning load (see "Tier strength and lens fit"); otherwise skip it. When using two parallax tiers, give them distinct lenses — never the same lens to both Codex and DeepSeek (that wastes a perspective), and don't stack two adversarial lenses unless the task genuinely demands two independent attack frames.

Before writing any Parallax relay prompt:
- **For Codex:** read `~/.claude/skills/prompt-engineer/references/gpt.md` and `~/.claude/skills/prompt-engineer/references/codex.md`.
- **For DeepSeek:** read `~/.claude/skills/prompt-engineer/references/deepseek.md`.

If those symlinks are unavailable, use the repo copies at `agents/extensions/skills/prompt-engineer/references/`. Do this every time, not just once.

**Relay call syntax (exact):**

```bash
# Codex parallax
relay call --to codex --name <slug> --effort <medium|xhigh> <<'BODY'
<prompt content here>
BODY

# DeepSeek parallax (no --effort — always max)
relay call --to deepseek --name <slug> <<'BODY'
<prompt content here>
BODY
```

`--name` is required (lowercase slug, e.g., `prism-adversarial`). `--to codex` is the script default and may be omitted; `--to deepseek` is required for DeepSeek calls. Do not pass `--effort` to DeepSeek — it always runs at `max` and the flag is silently ignored. The heredoc body must not be empty. Do not pass model flags — the script handles model selection. For concurrency details (backgrounding, timeouts), follow the relay skill's Async / Parallel section for your platform.

**Inspecting Parallax results:** Only read the `.res.md` response file. Never read the `.log` sidecar — it contains the peer's full stderr, which is extremely long and token-heavy. The relay script's Bash output already surfaces diagnostic information for failure cases.

If `relay` is unavailable, replace both Parallax tiers with same-model subagents and warn the user. Each substitute carries the lens that tier was already assigned under the opt-in rule above — do not re-decide by task category. Relay being unavailable does not change whether adversarial coverage is valuable for this question.

**Constraint leakage risk (CRITICAL):** Relay peers may recurse unless the anti-recursion rule is explicit, early, and repeated. You MUST:
1. Put the anti-recursion warning at the top of every launcher prompt, before the file-read instruction.
2. Preserve the Constraints section verbatim in the shared context file — do not summarize or abbreviate.
3. Ensure the prohibition appears in both each launcher (short form) and the shared file (full form).
4. Tell each peer to ignore loaded skill descriptions for prism and relay.

Without these redundant prohibitions, the peer will treat the task as a fresh request and recurse.

**Effort selection for Parallax:** If the user specified `codex-effort` in the shorthand, map it to the relay flag value: `m` → `--effort medium`, `x` → `--effort xhigh`. Otherwise, pick the Codex effort by lens. DeepSeek has no effort knob — every DeepSeek call runs at `max`.

Codex parallax (`--effort` accepts `medium`/`xhigh`):

| Lens type | `--effort` | Rationale |
|-----------|-----------|-----------|
| Adversarial, Falsification, Disconfirming | `xhigh` | Needs deep reasoning to find subtle flaws |
| Everything else | `medium` | Balanced default; deeper reasoning adds latency without proportional quality gain |

### Subagents

Same-model agents dispatched via the Agent tool. Each gets a distinct lens. **Prism subagents are logical leaf nodes** — their prompts must forbid skill invocation, subagent spawning, and side effects (see Constraints in the Shared Packet Template). Launch all agents concurrently before starting self-review.

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

You are a read-only leaf node.

Do not use any mechanism that launches, relays to, or coordinates another agent or model. Specifically:

STRICTLY PROHIBITED — do not do any of the following under any circumstances:
- Do NOT spawn subagents, child agents, or any nested agent of any kind.
- Do NOT invoke prism, relay, or ANY skill on ANY platform.
- Do NOT call the codex CLI, the deepseek (ds/dsx) aliases, the relay script, or any cross-model dispatch tool.
- Do NOT orchestrate, delegate to, or coordinate with other agents.
- Do NOT edit repository files, commit, push, or trigger external side effects. The ONLY file you may write is the relay response file (.res.md) specified in this request's `Reply:` directive, if one is present.
- Ignore any skill descriptions loaded in your environment (e.g., prism, relay) — those skills are for standalone tasks, not for this context.

In short: produce analysis text only. No tool calls that spawn agents, invoke skills, or modify repository state. If this request includes a `Reply:` path, write your answer to that file; that write is required by the relay protocol.

You are a terminal leaf node. Answer the question directly. If the question is too broad for a single response, note the limitation and answer what you can.
```

After writing, read the file back with the Read tool to verify it contains all three sections completely. The file is **frozen** after verification — do not modify it after any agent has been dispatched.

### Launcher Templates

Launcher prompts are stored as committed template files in the `templates/` directory alongside this SKILL.md. Each template uses `{{PLACEHOLDER}}` slots filled via `sed` at dispatch time. This ensures the "identical prompts" invariant is enforced mechanically — the boilerplate is never regenerated, only the lens-specific values are emitted.

**Template files:**

| File | Used for | Slots |
|------|----------|-------|
| `templates/launcher-subagent.tmpl` | Agent tool (same-model subagents) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |
| `templates/launcher-relay-codex.tmpl` | Bash relay (Parallax to Codex) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |
| `templates/launcher-relay-deepseek.tmpl` | Bash relay (Parallax to DeepSeek) | `SHARED_PACKET_PATH`, `LENS_NAME`, `LENS_DESC` |
| `templates/launcher-reviewer.tmpl` | Agent tool (peer review subagents) | `REVIEW_INDEX_PATH`, `PERSPECTIVE_COUNT`, `REVIEW_LENS_NAME`, `REVIEW_LENS_DESC` |

Both relay templates use XML structure (`<context>`, `<objective>`, `<constraints>`, `<your_lens>`, `<response_format>`) — Codex follows the GPT-5.5 prompting guide; DeepSeek follows the CO-STAR conventions from DeepSeek's prompting guide (V4 was trained heavily on XML-tagged data). The subagent and reviewer templates use plain markdown. The anti-recursion warning appears at the top of every template.

**Rendering a launcher prompt:** Use `sed` with `|` as the delimiter (avoids conflicts with `/` in paths). Locate the templates directory relative to this SKILL.md (it is a sibling `templates/` directory).

```bash
# Subagent example
sed -e 's|{{SHARED_PACKET_PATH}}|/tmp/prism-abc123.md|g' \
    -e 's|{{LENS_NAME}}|Simplicity|g' \
    -e 's|{{LENS_DESC}}|weigh the approach that requires the fewest moving parts|g' \
    /path/to/templates/launcher-subagent.tmpl

# Codex Parallax example (render to variable, pass as heredoc)
LAUNCHER_CODEX=$(sed -e 's|{{SHARED_PACKET_PATH}}|/tmp/prism-abc123.md|g' \
                     -e 's|{{LENS_NAME}}|Adversarial|g' \
                     -e 's|{{LENS_DESC}}|weigh the strongest attacks on the proposal|g' \
                     /path/to/templates/launcher-relay-codex.tmpl)
relay call --to codex --name prism-adversarial --effort xhigh <<BODY
$LAUNCHER_CODEX
BODY

# DeepSeek Parallax example (render to variable, pass as heredoc — no --effort)
LAUNCHER_DS=$(sed -e 's|{{SHARED_PACKET_PATH}}|/tmp/prism-abc123.md|g' \
                  -e 's|{{LENS_NAME}}|Falsification|g' \
                  -e 's|{{LENS_DESC}}|weigh what evidence would prove this wrong|g' \
                  /path/to/templates/launcher-relay-deepseek.tmpl)
relay call --to deepseek --name prism-falsification <<BODY
$LAUNCHER_DS
BODY
```

Only the shared packet path and lens vary between launcher prompts. Agent names are metadata outside the prompt body. When adding a new relay target model, create a new template file (e.g., `launcher-relay-gemini.tmpl`) optimized for that model's prompting conventions.

## Pre-Launch Checks

Run these checks before launching. If any fails, rewrite and re-check.

0. **Relay availability test (if either parallax tier > 0):** Run `command -v relay` to check if the relay command is in PATH. This is the sole test — do not glob for relay files or references to determine availability. If the command exists, relay is available.

1. **Shared-file test:** Verify the shared context file was written and read back successfully. Confirm every rendered launcher references the same absolute file path. The shared file must be frozen before any dispatch.

2. **Slot-completion test:** After rendering all launcher prompts via `sed`, verify no `{{` placeholder tokens survive: `grep -c '{{' rendered_launcher`. Also confirm the shared packet path is absolute and identical across all rendered prompts, and that the anti-recursion warning is the first line of every launcher. For relay prompts (both Codex and DeepSeek), verify the XML skeleton is well-formed (`<context>`, `<objective>` or `<goal>`, `<constraints>`, `<your_lens>` tags present).

3. **Redundancy test:** Swap any two agents' lenses. If the prompts become incoherent, you have divided labor. This applies across tiers too — a Codex agent's lens and a DeepSeek agent's lens should be swappable in principle (only the prompt format differs).

4. **Lens quality test:** Each lens name must be a weighing posture (1-3 words), never a task or role. For each lens, write one sentence explaining what unique axis it covers that no other lens does. If two lenses would produce the same emphasis, replace one. **Adversarial coverage is opt-in, not default:** include a structurally adversarial lens (Adversarial, Falsification, Disconfirming, Risk, or similar) only when having one is *much more valuable* than spending that slot on another orthogonal lens — i.e., the answer turns on surfacing a non-obvious flaw, attack, or failure mode that no other lens is already covering. Before adding one, write one sentence naming the specific risk it exists to catch; if you can't, drop it and use an exploratory lens instead. This applies regardless of task category — a "risk-bearing" task (decision, design, code review, implementation, root-cause claim) does *not* automatically require an adversarial lens; judge whether stress-testing is the binding constraint for *this* question. **Conversely, the omission must also be deliberate:** if the task proposes, evaluates, or changes something and you include *no* adversarial-family lens, write one sentence naming which dispatched lens covers "what could go wrong." If none does, add one — it need not be a full Adversarial lens; a failure-mode-tilted variant of an exploratory lens (e.g., Depth-Weighted on failure modes) can suffice. Silent omission on such a task is a check failure, because an all-constructive dispatch can converge with false confidence when nothing was assigned to attack the proposal. Never assign the same lens to both Codex and DeepSeek — that wastes a perspective. If you do include an adversarial lens and it carries the heaviest reasoning load on a subtle technical question, confirm it is assigned to Claude or Codex (`xhigh`) rather than DeepSeek — see "Tier strength and lens fit" in Parallax.

5. **Dispatch-shape test (CRITICAL):** Total dispatched agents (subagents + Codex parallax + DeepSeek parallax) must match the configured counts. Self does not count. Enumerate planned calls by type:
   - Bash relay calls with `--to codex` must equal `codex-count`.
   - Bash relay calls with `--to deepseek` (or whose env routes to DeepSeek) must equal `ds-count`.
   - The rest are Agent calls and must equal `sub`.

   If any count mismatches, the dispatch is wrong — fix before launching. The most common failure is forgetting the DeepSeek call because the previous parallax model was Codex-only.

6. **Effort test:** If the user specified `codex-effort` in the shorthand, confirm every Codex relay call uses the mapped level (`m` → `--effort medium`, `x` → `--effort xhigh`) — never pass the raw shorthand letter, the relay script rejects it. If omitted, confirm each Codex call uses the effort from the lens-based table (Effort selection for Parallax). State the Codex effort being applied. DeepSeek calls must NOT pass `--effort` — it always runs at `max`. Reject Codex effort letters outside `{m, x}` at parse time.

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

## Peer Review (Optional)

Peer review adds a second dispatch wave after all initial agents return. Reviewers read **anonymized** outputs and critique them — surfacing blind spots that even the integrator might share with the initial agents (same-model bias).

**When to use:** Enable with the `r` flag. Recommended for high-stakes decisions, ambiguous tradeoffs, or any question where "what did everyone miss?" is as valuable as "what did everyone say?"

### How it works

1. **Anonymize and persist from disk:** Assign each agent a random letter (A, B, C, …) — shuffle so the mapping is not predictable from dispatch order. **Do not use Write to re-emit agent outputs.** Instead, create perspective files from existing on-disk artifacts using a single Bash call:

   - **Relay agents:** `cp` the `.res.md` file (path is in the Bash completion result). Pipe through `sed` to strip YAML frontmatter and redact lens self-references.
   - **Subagents:** Extract the final assistant response from the Agent tool's JSONL output file using `jq`, pipe through `sed` for redaction. The output file path is visible in the Agent tool result metadata (e.g., `/private/tmp/claude-501/.../tasks/<agent-id>.output`). The extraction command:
     ```bash
     jq -sr '[.[] | select(.type=="assistant")] | last | .message.content |
       if type=="array" then [.[] | select(.type=="text") | .text] | join("\n") else . end' \
       "$AGENT_OUTPUT_FILE" | sed 's/Simplicity/[redacted]/gi' \
       > /tmp/prism-<id>-perspective-<letter>.md
     ```
   - **Fallback:** If `jq` extraction fails for a subagent (schema change, missing file), fall back to Write for that single perspective. Log the fallback.

   Batch all `cp`/`jq`/`sed` commands into as few Bash calls as possible. Build `sed` patterns dynamically from the lens names assigned during dispatch.

   **Platform dependency:** The subagent JSONL format and output file path are internal to the Claude Code runtime and may change. The relay `.res.md` path is a stable protocol contract. If the JSONL extraction breaks, the Write fallback activates automatically — no data loss, just degraded token cost.

2. **Anonymization check (fail-closed):** Before building the review index, verify perspective files are clean. Build the grep pattern dynamically from the **actual lens names assigned in this run** — do not use a hardcoded list of all possible terms. Prism architecture terms like "Parallax" or "cross-model" are NOT identity markers — they may appear legitimately when agents discuss Prism itself.
   ```bash
   # Only check for the lenses actually used in this run
   LENSES="LensA|LensB|LensC|LensD"  # substitute actual names
   grep -ilP "(?i)(${LENSES})" /tmp/prism-<id>-perspective-*.md
   ```
   If any assigned lens name survives redaction, fix the `sed` pattern and re-run before proceeding. Do not dispatch reviewers with leaky perspective files.

3. **Build the review index:** Write a lightweight index to `/tmp/prism-<same-id>-review.md`. This file contains **no agent output** — only pointers. Reviewers read the perspective files themselves.

   ```
   ## Original Question

   Read the shared context file for full question and background:
   - {SHARED_PACKET_PATH}

   ## Perspectives

   Read each perspective file in full before answering the review questions.

   - Perspective A: /tmp/prism-<same-id>-perspective-A.md
   - Perspective B: /tmp/prism-<same-id>-perspective-B.md
   - Perspective C: /tmp/prism-<same-id>-perspective-C.md
   - ...

   ## Review Questions

   Answer each question concisely. Cite perspectives by letter and quote key phrases.

   1. **Strongest response** — Which perspective is strongest overall, and why?
   2. **Biggest blind spot** — Which perspective has the most significant gap or weakness?
   3. **Collective gap** — What did ALL perspectives miss or underweight? This is the most important question.
   ```

4. **Dispatch reviewers:** Launch **2 same-model subagents** concurrently (`run_in_background: true`). Each reviewer gets a launcher prompt referencing the review index. Reviewers are read-only leaf nodes — same constraints as initial agents. Give each reviewer a distinct review lens:
   - **Reviewer 1 — Strength-finder:** Weighs which arguments are most well-supported and actionable.
   - **Reviewer 2 — Gap-hunter:** Weighs what's missing, underexplored, or assumed without evidence.

5. **Wait for both reviewers** before proceeding to synthesis. Same hard gate as the initial round.

### Reviewer Launcher Template

The reviewer launcher is stored in `templates/launcher-reviewer.tmpl`. Render it with `sed`, filling the slots `{{REVIEW_INDEX_PATH}}`, `{{PERSPECTIVE_COUNT}}`, `{{REVIEW_LENS_NAME}}`, and `{{REVIEW_LENS_DESC}}`:

```bash
sed -e 's|{{REVIEW_INDEX_PATH}}|/tmp/prism-abc123-review.md|g' \
    -e 's|{{PERSPECTIVE_COUNT}}|4|g' \
    -e 's|{{REVIEW_LENS_NAME}}|Strength-finder|g' \
    -e 's|{{REVIEW_LENS_DESC}}|weigh which arguments are most well-supported and actionable|g' \
    /path/to/templates/launcher-reviewer.tmpl
```

## Execution

### Step 1: Freeze context, compose, verify, launch

1. Build one canonical shared packet (Full Question + Context + Constraints).
2. Write the shared packet to `/tmp/prism-<unique-id>.md` using the Write tool. Read it back to verify completeness.
3. Render launcher prompts from the template files in `templates/` using `sed` substitution (see Launcher Templates). For each agent, fill only the lens-specific slots — the boilerplate is already in the template. Render Codex parallax launchers from `launcher-relay-codex.tmpl`, DeepSeek parallax launchers from `launcher-relay-deepseek.tmpl`, and subagent launchers from `launcher-subagent.tmpl`.
4. Run the pre-launch checks (including the slot-completion test on rendered launchers). Fix failures before launch.
5. Launch all dispatched agents concurrently (`run_in_background: true`). **Dispatch checklist:**
   - Subagents: **Agent** tool with the rendered launcher prompt.
   - **Codex parallax (required if codex-count > 0):** **Bash** tool to `relay call --to codex` (the `--to codex` flag is optional since codex is the default) with the rendered Codex launcher as the heredoc body.
   - **DeepSeek parallax (required if ds-count > 0):** **Bash** tool to `relay call --to deepseek` with the rendered DeepSeek launcher as the heredoc body.
   - Compose all Parallax calls FIRST to prevent omission — they are the most-forgotten step. Verify each relay command shape, heredoc body, and Bash timeout (`timeout: 600000`) before launching.
   - Confirm the count of dispatched Codex relay calls matches `codex-count` and DeepSeek relay calls matches `ds-count`.

Do not poll or sleep-loop — the system notifies you when agents finish.

### Step 2: Self-review

While agents run, form your own position independently. Your lens is **Integrator Lens** — you weigh holistic coherence, feasibility, and alignment with the user's goals. Write your tentative recommendation before opening any agent output.

Since you composed the prompts and chose the lenses, your self-review is not fully independent. When dispatched agents diverge from your position, give their perspectives slightly more weight on points you may have anchored on during prompt design.

### Step 3: Wait for ALL agents (HARD GATE)

**Do not synthesize, summarize, or present results until EVERY dispatched agent — including both Parallax tiers — has returned.** This is a hard gate, not a suggestion. Having "enough" subagents is never a reason to skip the remaining agents. The whole point of Parallax is model diversity — proceeding without it defeats the purpose of Prism. Codex finishing first is not permission to ignore DeepSeek, and vice versa.

**Parallax is slow — that is normal and expected.** Relay calls routinely take 2-5x longer than same-model subagents. DeepSeek calls (always at DeepThink `max`) and Codex calls at `--effort xhigh` are the slowest. Do not diagnose, retry, report failure, or proceed while a background task is running. The system sends a completion notification per call; until all expected notifications arrive, the run is healthy. Do not tell the user you are "still waiting" or suggest proceeding without any tier.

**What to do while waiting:** Work on your self-review (Step 2). If self-review is done, wait silently. Do not synthesize partial results.

**Handling failures (after completion notification only):**

- **Relay transport failure:** Check the Bash tool's output for diagnostic information, fix the invocation, and retry once before escalating. Do not read the `.log` sidecar — it is extremely long and token-heavy.
- **Answer-quality failure** (empty, truncated, off-topic): Offer the user: (a) retry, (b) proceed with reduced perspectives, or (c) abort.
- **Only these post-notification failures justify proceeding without Parallax.** "It's taking a long time" is never a failure.

### Step 3.5: Safety check

Before synthesizing, verify no dispatched agent modified the working tree:

```bash
git diff --stat HEAD
```

If the diff shows unexpected changes, flag them to the user before proceeding. Discard the offending agent's output — an agent that violated read-only constraints may have reasoned from a corrupted state.

Scan each agent's output for recursion indicators: mentions of "dispatching," "subagent," "relay call," "Prism run," or synthesis-style structure (Consensus/Contested/Unique sections). Flag matches for review — the agent may have spawned nested agents, producing contaminated reasoning.

### Step 3.75: Peer review (if `r` enabled)

Skip this step if peer review was not requested.

1. Anonymize from disk: assign random letter mappings, create perspective files from existing on-disk artifacts using Bash `cp`/`jq`/`sed` (see "How it works" for per-agent-type details). Do not use Write to re-emit agent outputs.
2. Run the fail-closed anonymization check. Fix any surviving identity markers before proceeding.
3. Write the review index to `/tmp/prism-<same-id>-review.md` — pointers only, no inlined content. Read it back to verify all perspective paths are correct.
4. Dispatch 2 reviewer subagents concurrently (`run_in_background: true`) using the Reviewer Launcher Template.
5. Wait for both reviewers (hard gate — same rules as Step 3).
6. Carry reviewer findings forward into synthesis — especially answers to "What did ALL perspectives miss?"

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
- **Cross-model break** (subagents converge, one or both Parallax tiers dissent): cap confidence at moderate. Lead Watch/Dissent with the Parallax argument — cross-model disagreement is the highest-signal finding and must not be buried. When Codex and DeepSeek dissent in the *same direction*, treat this as an especially strong signal (two independent model lineages agree the subagents missed something).
- **Deliverable**: artifact in Answer; Why becomes design rationale; Do now covers integration/review steps.

**Banned in the main path:**

- Per-lens attribution ("Agent A said…", "The Simplicity lens noted…"). Move to an optional `<details>Per-lens notes</details>` appendix at the very bottom only if the user asked, or if disagreement is deep enough to require lens-level audit.
- Synthesis narration ("Weighing the perspectives…", "After considering the arguments…"). The recommendation carries the reasoning.
- Generic contingencies ("if requirements change"). Only concrete, observable triggers.
- Standalone `Confidence and basis` / `Key dissent` / `Contingencies` sections. Their content folds into Why and Watch/Dissent, and only when decision-relevant.

**Cross-model weighting (internal — surfaces through Why):**

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

Optionally delete all Prism temp files: shared context (`/tmp/prism-<unique-id>.md`), perspective files (`/tmp/prism-<unique-id>-perspective-*.md`), and review index (`/tmp/prism-<unique-id>-review.md`).

## Guards

- **No recursion (HARD RULE):** Dispatched agents must never invoke prism, relay, any skill, or spawn child agents. The Constraints section and launcher prompts both enforce this — do not weaken or omit either. For Parallax, keep the anti-recursion warning at the top of every heredoc (both Codex and DeepSeek launchers).
- **No contamination:** Write the shared context file and compose all launcher prompts before any launch. Do not modify the shared file or revise prompts after seeing early agent outputs.
- **No all-same-model dispatch (HARD RULE):** The total count of Bash relay calls must equal `codex-count + ds-count`. If the planned dispatch has zero relay calls but either configured count is non-zero, fix before launching. This is the most common Prism failure mode — even with two parallax tiers configured, forgetting to launch them is easy.
- **No early synthesis (HARD RULE):** Do not synthesize until every dispatched agent has returned its completion notification. "Subagents are done, Codex relay is still running" or "Codex came back, DeepSeek is still running" are not reasons to proceed — they are the expected state. Proceeding without any tier's results voids the entire Prism run.
- **No side effects:** Dispatched agents must not edit files, commit, push, or invoke skills. The only permitted write is the relay response file (.res.md).

## Degrees of Freedom

The core principle (redundancy, not division of labor), the prompt template structure, and the hard completion gate are load-bearing constraints — do not relax them. Everything else — lens choices, synthesis categories, agent count beyond the minimum, pre-launch check order — is flexible guidance that you should adapt to the task.

**Synthesis adaptation:** The default categories (Recommendation, Confidence and basis, Key dissent, Contingencies) suit most analysis and decision questions. But the integrator should actively adapt the synthesis frame when the task calls for it — merge sections, reorder, or add task-specific sections. A deliverable question needs the artifact front and center with design rationale behind it; a pure risk assessment might elevate Contingencies above Confidence. Rigid adherence to the default categories when they don't fit the question is a failure of integration.

## When to Use Prism

Use Prism when a task benefits from diverse, redundant judgment and the shared context fits cleanly across all agents.

Skip Prism for trivial lookups, deterministic transforms, single-correct-answer tasks, or tasks requiring parallel mutations of shared state.
