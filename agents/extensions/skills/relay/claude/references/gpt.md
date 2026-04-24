# GPT-5.5 Prompt Craft

Help users write effective prompts for OpenAI GPT models — either from scratch or by refining existing prompts. Based on OpenAI's official GPT-5.5 prompt guidance. For Codex coding agents, see `references/codex.md` instead.

## Core philosophy: outcome-first

GPT-5.5 works best with **outcome-first prompts** that define the target and constraints while leaving room for the model to choose an efficient solution path. Shorter, outcome-first prompts usually outperform process-heavy instruction stacks.

- Describe the destination, not every step. State the target outcome, success criteria, constraints, and available context — then let the model choose the search, tool, or reasoning strategy.
- Avoid unnecessary absolute rules (ALWAYS, NEVER, must, only) for judgment calls. Reserve absolutes for safety, privacy, and compliance.
- Add explicit stopping conditions so the model knows when the job is done.
- Re-evaluate `low` and `medium` reasoning effort before escalating — they cover more ground than you might expect.

### Suggested prompt structure

```
Role: [1-2 sentences defining function, context, job]

# Personality
[tone, demeanor, collaboration style]

# Goal
[user-visible outcome]

# Success criteria
[what must be true before final answer]

# Constraints
[policy, safety, business, evidence, side-effect limits]

# Output
[sections, length, tone]

# Stop rules
[when to retry, fallback, abstain, ask, or stop]
```

Start with the minimum version of this structure, then add the specialized blocks below only when a measured failure mode justifies them.

## Writing a prompt from scratch

### Step 1: Clarify the task

Ask the user:
- What should the model do? (core task)
- What does good output look like? (format, length, structure)
- What context will be available? (documents, tool results, prior conversation)
- Will the model have tools? (search, terminal, file edit, code execution)
- What personality should it project? (task-focused vs. expressive)

### Step 2: Set the goal, success criteria, and stop rules

State the outcome, not the procedure. Include explicit stopping conditions and missing-evidence behavior.

**Example — outcome-first with stop rules:**

```
Resolve the customer's issue end to end. Success means:
- the eligibility decision is made from the available policy and account data
- any allowed action is completed before responding
- the final answer includes completed_actions, customer_message, and blockers
- if evidence is missing, ask for the smallest missing field

Resolve the user query in the fewest useful tool loops, but do not let loop
minimization outrank correctness, accessible fallback evidence, calculations,
or required citation tags for factual claims. After each result, ask: "Can I
answer the user's core request now with useful evidence and citations for the
factual claims?" If yes, answer. Use the minimum evidence sufficient to
answer correctly, cite it precisely, then stop.
```

### Step 3: Define personality and collaboration style

Personality and collaboration style are separate components. Specify both when the UX matters.

**Personality** — tone, warmth, directness, formality, humor, empathy, polish.

**Collaboration style** — when to ask questions, when to make assumptions, when to check work, how to handle uncertainty.

**Example — task-focused:**

```
# Personality

You are a capable collaborator: approachable, steady, and direct. Prefer
making progress over stopping for clarification when the request is already
clear enough. Stay concise without becoming curt. When correcting the user or
disagreeing, be candid but constructive.
```

**Example — expressive:**

```
# Personality

Adopt a vivid conversational presence: intelligent, curious, playful when
appropriate. Be warm, collaborative, and polished. Offer a real point of view
rather than merely mirroring the user.
```

### Step 4: Define the output contract

State what the output should look like. Keep this block short — lean on the suggested prompt structure above for shape, and use the contract to lock format where precision matters.

```xml
<output_contract>
- Return exactly the sections requested, in the requested order.
- If the prompt defines a preamble, analysis block, or working section, do not
  treat it as extra output.
- Apply length limits only to the section they are intended for.
- If a format is required (JSON, Markdown, SQL, XML), output only that format.
</output_contract>

<verbosity_controls>
- Prefer concise, information-dense writing.
- Avoid repeating the user's request.
- Keep progress updates brief.
- Do not shorten the answer so aggressively that required evidence, reasoning,
  or completion checks are omitted.
</verbosity_controls>
```

**Formatting defaults** — let formatting serve comprehension, not the other way around.

```
Use plain paragraphs as the default format for normal conversation,
explanations, reports, documentation, and technical writeups. Keep the
presentation clean and readable without making the structure feel heavier
than the content.

Use headers, bold text, bullets, and numbered lists sparingly. Reach for them
when the user requests them, when the answer needs clear comparison or
ranking, or when the information would be harder to scan as prose. Otherwise,
favor short paragraphs and natural transitions.
```

**Editing tasks** — preserve the requested artifact rather than inflating it:

```
Preserve the requested artifact, length, structure, and genre first. Quietly
improve clarity, flow, and correctness. Do not add new claims, extra
sections, or a more promotional tone unless explicitly requested.
```

### Step 5: Set a follow-through policy

Define when to proceed autonomously vs. when to ask permission. This prevents stalling on obvious tasks and unchecked action on risky ones.

```xml
<default_follow_through_policy>
- If the user's intent is clear and the next step is reversible and low-risk,
  proceed without asking.
- Ask permission only if the next step is:
  (a) irreversible,
  (b) has external side effects (sending, purchasing, deleting, writing to
  production), or
  (c) requires missing sensitive information or a choice that would materially
  change the outcome.
- If proceeding, briefly state what you did and what remains optional.
</default_follow_through_policy>
```

### Step 6: Set instruction priorities (when instructions may conflict)

```xml
<instruction_priority>
- User instructions override default style, tone, formatting, and initiative
  preferences.
- Safety, honesty, privacy, and permission constraints do not yield.
- If a newer user instruction conflicts with an earlier one, follow the newer
  instruction.
- Preserve earlier instructions that do not conflict.
</instruction_priority>
```

**Mid-conversation updates** — use scoped steering messages that state scope, override, and carry-forward:

```xml
<task_update>
For the next response only:
- Do not complete the task.
- Only produce a plan.
- Keep it to 5 bullets.

All earlier instructions still apply unless they conflict with this update.
</task_update>
```

When the task itself changes:

```xml
<task_update>
The task has changed.
Previous task: complete the workflow.
Current task: review the workflow and identify risks only.

Rules for this turn:
- Do not execute actions.
- Do not call destructive tools.
- Return exactly:
  1. Main risks
  2. Missing information
  3. Recommended next step
</task_update>
```

### Step 7: Tool use guidance (if applicable)

#### Preamble pattern (streaming / tool-heavy agents)

For streaming applications, a short preamble improves perceived responsiveness. This is especially important for Responses API workflows that separate commentary from final answers.

```
Before any tool calls for a multi-step task, send a short user-visible update
that acknowledges the request and states the first step. Keep it to one or
two sentences.
```

For coding agents with separate message phases:

```
You must always start with an intermediary update before any content in the
analysis channel if the task will require calling tools.
```

#### Tool persistence

Prevent early stopping when another tool call would materially improve correctness — but pair it with outcome-first stopping conditions so the model doesn't loop indefinitely.

```xml
<tool_use_guidance>
- Use tools whenever they materially improve correctness, completeness, or
  grounding.
- Do not stop early when another tool call is likely to materially improve
  correctness or completeness.
- If a tool returns empty or partial results, retry with a different strategy.
- Stop once the task is complete and verification passes — not sooner, not later.
</tool_use_guidance>
```

#### Dependency checking

```xml
<dependency_checks>
- Before taking an action, check whether prerequisite discovery, lookup, or
  memory retrieval steps are required.
- Do not skip prerequisite steps just because the intended final action seems
  obvious.
- If the task depends on the output of a prior step, resolve that dependency
  first.
</dependency_checks>
```

#### Parallel tool calling

```xml
<parallel_tool_calling>
- When multiple retrieval or lookup steps are independent, prefer parallel tool
  calls to reduce wall-clock time.
- Do not parallelize steps that have prerequisite dependencies or where one
  result determines the next action.
- After parallel retrieval, pause to synthesize the results before making more
  calls.
- Prefer selective parallelism: parallelize independent evidence gathering, not
  speculative or redundant tool use.
</parallel_tool_calling>
```

#### Terminal tool hygiene (for coding agents)

```xml
<terminal_tool_hygiene>
- Only run shell commands via the terminal tool.
- Never "run" tool names as shell commands.
- If a patch or edit tool exists, use it directly; do not attempt it in bash.
- After changes, run a lightweight verification step such as ls, tests, or a
  build before declaring the task done.
</terminal_tool_hygiene>
```

### Step 8: Retrieval budgets and grounding

Add explicit retrieval budgets — stopping rules for search. Unbounded "search more" instructions cause wasted calls and over-reasoning.

```
For ordinary Q&A, start with one broad search using short, discriminative
keywords. If the top results contain enough citable support for the core
request, answer from those results instead of searching again.

Make another retrieval call only when:
- top results do not answer the core question
- a required fact, parameter, owner, date, ID, or source is missing
- the user asked for exhaustive coverage, comparison, or a comprehensive list
- a specific document, URL, email, meeting, record, or code artifact must be read
- the answer would otherwise contain an important unsupported factual claim

Do not search again to improve phrasing, add examples, cite nonessential
details, or support wording that can safely be made more generic.
```

#### Citations and grounding

```xml
<citation_rules>
- Only cite sources retrieved in the current workflow.
- Never fabricate citations, URLs, IDs, or quote spans.
- Use exactly the citation format required by the host application.
- Attach citations to the specific claims they support, not only at the end.
</citation_rules>

<grounding_rules>
- Base claims only on provided context or tool outputs.
- If sources conflict, state the conflict explicitly and attribute each side.
- If the context is insufficient or irrelevant, narrow the answer or say you
  cannot support the claim.
- If a statement is an inference rather than a directly supported fact, label
  it as an inference.
</grounding_rules>
```

#### Empty result recovery

```xml
<empty_result_recovery>
If a lookup returns empty, partial, or suspiciously narrow results:
- do not immediately conclude that no results exist,
- try at least one or two fallback strategies,
  such as:
  - alternate query wording,
  - broader filters,
  - a prerequisite lookup,
  - or an alternate source or tool,
- Only then report that no results were found, along with what you tried.
</empty_result_recovery>
```

#### Research mode (for synthesis tasks)

Use for research, review, and synthesis tasks (not short execution tasks):

```xml
<research_mode>
- Do research in 3 passes:
  1) Plan: list 3-6 sub-questions to answer.
  2) Retrieve: search each sub-question and follow 1-2 second-order leads.
  3) Synthesize: resolve contradictions and write the final answer with
  citations.
- Stop only when more searching is unlikely to change the conclusion.
</research_mode>
```

### Step 9: Completeness and verification

Address common failure modes in multi-step workflows — incomplete execution, false negatives from empty results, unverified output.

```xml
<completeness_contract>
- Treat the task as incomplete until all requested items are covered or
  explicitly marked [blocked].
- Keep an internal checklist of required deliverables.
- For lists, batches, or paginated results:
  - determine expected scope when possible,
  - track processed items or pages,
  - confirm coverage before finalizing.
- If any item is blocked by missing data, mark it [blocked] and state exactly
  what is missing.
</completeness_contract>

<verification_loop>
Before finalizing:
- Check correctness: does the output satisfy every requirement?
- Check grounding: are factual claims backed by the provided context or tool
  outputs?
- Check formatting: does the output match the requested schema or style?
- Check safety and irreversibility: if the next step has external side effects,
  ask permission first.
</verification_loop>

<missing_context_gating>
- If required context is missing, do NOT guess.
- Prefer the appropriate lookup tool when the missing context is retrievable;
  ask a minimal clarifying question only when it is not.
- If you must proceed, label assumptions explicitly and choose a reversible
  action.
</missing_context_gating>

<action_safety>
- Pre-flight: summarize the intended action and parameters in 1-2 lines.
- Execute via tool.
- Post-flight: confirm the outcome and any validation that was performed.
</action_safety>
```

### Step 10: Validation after output

After producing a change or artifact, validate it before declaring the task done.

**For coding agents:**

```
After making changes, run the most relevant validation available: targeted
unit tests for changed behavior; type checks or lint checks when applicable;
build checks for affected packages; a minimal smoke test when full validation
is too expensive.
```

**For visual artifacts:**

```
Render the artifact before finalizing. Inspect the rendered output for
layout, clipping, spacing, missing content, and visual consistency. Revise
until the rendered output matches the requirements.
```

### Step 11: Creative drafting guardrails

For drafts, marketing copy, or anything where the model might be tempted to fabricate specifics to sound stronger, distinguish source-backed facts from creative wording.

```
Use retrieved or provided facts for any concrete product name, customer,
metric, roadmap item, date, capability, or competitive claim — and cite those
facts. Do not invent specific names, first-party data claims, metrics,
roadmap status, customer outcomes, or product capabilities to make the draft
sound stronger. If little or no citable support exists, write a useful
generic draft with placeholders or clearly labeled assumptions.
```

### Step 12: Reasoning effort

Reasoning effort is a last-mile tuning knob, not the primary way to improve quality. Before raising effort, add outcome-first stop rules, completeness contracts, and tool persistence — these typically move quality more than a higher effort setting.

If the model still stops at the first plausible answer, add an initiative nudge:

```xml
<dig_deeper_nudge>
- Don't stop at the first plausible answer.
- Look for second-order issues, edge cases, and missing constraints.
- If the task is safety or accuracy critical, perform at least one verification
  step.
</dig_deeper_nudge>
```

#### Reasoning effort defaults

Start lower than you might expect — GPT-5.5 is efficient enough that `none`, `low`, and `medium` cover most workloads. Only escalate on measured regressions.

- `none`: Fast, cost-sensitive, latency-sensitive tasks where the model doesn't need to think. Already strong on action-selection and tool-discipline.
- `low`: Latency-sensitive tasks where a small amount of thinking produces meaningful accuracy gain, especially with complex instructions.
- `medium`: Default for most interactive assistants and moderately complex workflows.
- `high`: Research-heavy workloads — long-context synthesis, multi-document review, conflict resolution, strategy writing.
- `xhigh`: Long, agentic, reasoning-heavy tasks where maximum intelligence matters more than speed or cost. Avoid as a default unless evals show clear benefits.

#### Small-model guidance (gpt-5.5-mini and gpt-5.5-nano)

Smaller models are highly steerable but less likely to infer missing steps, resolve ambiguity implicitly, or package outputs as intended unless specified directly. Prompts for smaller models are often longer and more explicit — the outcome-first minimalism that works on GPT-5.5 may underperform here.

**Prompting gpt-5.5-mini:**
- Put critical rules first
- Specify the full execution order when tool use or side effects matter
- Don't rely on "you MUST" alone — use structural scaffolding: numbered steps, decision rules, explicit action definitions
- Separate "do the action" from "report the action"
- Show the correct flow, not just the final format
- Define ambiguity behavior explicitly: when to ask, abstain, or proceed
- Specify packaging directly: answer length, follow-up questions, citation style, section order
- Prefer scoped instructions (`after the final JSON, output nothing further`) over `output nothing else`

**Prompting gpt-5.5-nano:**
- Use only for narrow, well-bounded tasks
- Prefer closed outputs: labels, enums, short JSON, fixed templates
- Avoid multi-step orchestration unless extremely constrained
- Route ambiguous or planning-heavy tasks to a stronger model

**Good default pattern for small models:**
1. Task
2. Critical rule
3. Exact step order
4. Edge cases or clarification behavior
5. Output format
6. One correct example

### Step 13: Specialized workflow patterns (as needed)

#### User updates (general)

```xml
<user_updates_spec>
- Only update the user when starting a new major phase or when something
  changes the plan.
- Each update: 1 sentence on outcome + 1 sentence on next step.
- Do not narrate routine tool calls.
- Keep the user-facing status short; keep the work exhaustive.
</user_updates_spec>
```

For coding agents, use the more detailed version below instead.

#### Coding agent autonomy (non-Codex GPT agents)

For Codex-specific agent patterns (starter prompt, preambles, tools), use `references/codex.md` instead.

```xml
<autonomy_and_persistence>
Persist until the task is fully handled end-to-end within the current turn
whenever feasible: do not stop at analysis or partial fixes; carry changes
through implementation, verification, and a clear explanation of outcomes
unless the user explicitly pauses or redirects you.

Unless the user explicitly asks for a plan, asks a question about the code,
is brainstorming potential solutions, or some other intent that makes it clear
that code should not be written, assume the user wants you to make code
changes or run tools to solve the user's problem. In these cases, it's bad to
output your proposed solution in a message, you should go ahead and actually
implement the change. If you encounter challenges or blockers, you should
attempt to resolve them yourself.
</autonomy_and_persistence>
```

#### User updates (for coding agents)

```xml
<user_updates_spec>
- Intermediary updates go to the `commentary` channel.
- User updates are short updates while you are working. They are not final
  answers.
- Use 1-2 sentence updates to communicate progress and new information while
  you work.
- Do not begin responses with conversational interjections or meta commentary.
  Avoid openers such as acknowledgements ("Done -", "Got it", or "Great
  question") or similar framing.
- Before exploring or doing substantial work, send a user update explaining
  your understanding of the request and your first step. Avoid commenting on
  the request or starting with phrases such as "Got it" or "Understood."
- Provide updates roughly every 30 seconds while working.
- When exploring, explain what context you are gathering and what you learned.
  Vary sentence structure so the updates do not become repetitive.
- When working for a while, keep updates informative and varied, but stay
  concise.
- When work is substantial, provide a longer plan after you have enough
  context. This is the only update that may be longer than 2 sentences and
  may contain formatting.
- Before file edits, explain what you are about to change.
- While thinking, keep the user informed of progress without narrating every
  tool call. Even if you are not taking actions, send frequent progress
  updates rather than going silent.
- Keep the tone of progress updates consistent with the assistant's overall
  personality.
</user_updates_spec>
```

#### Formatting control

```xml
Never use nested bullets. Keep lists flat (single level). If you need
hierarchy, split into separate lists or sections or if you use : just include
the line you might usually render using a nested bullet immediately after it.
For numbered lists, only use the `1. 2. 3.` style markers (with a period),
never `1)`.
```

#### Structured output (JSON, SQL, etc.)

```xml
<structured_output_contract>
- Output only the requested format.
- Do not add prose or markdown fences unless they were requested.
- Validate that parentheses and brackets are balanced.
- Do not invent tables or fields.
- If required schema information is missing, ask for it or return an explicit
  error object.
</structured_output_contract>
```

#### Frontend design

```xml
<frontend_tasks>
When doing frontend design tasks, avoid generic, overbuilt layouts.

Use these hard rules:
- One composition: The first viewport must read as one composition, not a
  dashboard, unless it is a dashboard.
- Brand first: On branded pages, the brand or product name must be a
  hero-level signal, not just nav text or an eyebrow. No headline should
  overpower the brand.
- Brand test: If the first viewport could belong to another brand after
  removing the nav, the branding is too weak.
- Full-bleed hero only: On landing pages and promotional surfaces, the hero
  image should usually be a dominant edge-to-edge visual plane or background.
  Do not default to inset hero images, side-panel hero images, rounded media
  cards, tiled collages, or floating image blocks unless the existing design
  system clearly requires them.
- Hero budget: The first viewport should usually contain only the brand, one
  headline, one short supporting sentence, one CTA group, and one dominant
  image. Do not place stats, schedules, event listings, address blocks,
  promos, "this week" callouts, metadata rows, or secondary marketing content
  there.
- No hero overlays: Do not place detached labels, floating badges, promo
  stickers, info chips, or callout boxes on top of hero media.
- Cards: Default to no cards. Never use cards in the hero unless they are the
  container for a user interaction. If removing a border, shadow, background,
  or radius does not hurt interaction or understanding, it should not be a
  card.
- One job per section: Each section should have one purpose, one headline, and
  usually one short supporting sentence.
- Real visual anchor: Imagery should show the product, place, atmosphere, or
  context.
- Reduce clutter: Avoid pill clusters, stat strips, icon rows, boxed promos,
  schedule snippets, and competing text blocks.
- Use motion to create presence and hierarchy, not noise. Ship 2-3 intentional
  motions for visually led work, and prefer Framer Motion when it is
  available.

Exception: If working within an existing design system, preserve the
established patterns.
</frontend_tasks>
```

#### Vision and image detail

Specify the image `detail` level explicitly rather than relying on auto:
- `high` — standard high-fidelity image understanding
- `original` — large, dense, or spatially sensitive images (computer use, localization, OCR, click-accuracy tasks)
- `low` — only when speed and cost matter more than fine detail

#### Bounding box extraction (OCR / document localization)

```xml
<bbox_extraction_spec>
- Use the specified coordinate format exactly (for example [x1,y1,x2,y2]
  normalized 0..1).
- For each bbox, include: page, label, text snippet, confidence.
- Add a vertical-drift sanity check:
  - ensure bboxes align with the line of text (not shifted up or down).
- If dense layout, process page by page and do a second pass for missed items.
</bbox_extraction_spec>
```

#### Personality and writing controls (for customer-facing apps)

Separate persistent personality from per-response writing controls:

```xml
<personality_and_writing_controls>
- Persona: <one sentence>
- Channel: <Slack | email | memo | PRD | blog>
- Emotional register: <direct/calm/energized/etc.> + "not <overdo this>"
- Formatting: <ban bullets/headers/markdown if you want prose>
- Length: <hard limit, e.g. <=150 words or 3-5 sentences>
- Default follow-through: if the request is clear and low-risk, proceed
  without asking permission.
</personality_and_writing_controls>
```

#### Professional memo mode

```xml
<memo_mode>
- Write in a polished, professional memo style.
- Use exact names, dates, entities, and authorities when supported by the
  record.
- Follow domain-specific structure if one is requested.
- Prefer precise conclusions over generic hedging.
- When uncertainty is real, tie it to the exact missing fact or conflicting
  source.
- Synthesize across documents rather than summarizing each one independently.
</memo_mode>
```

#### Phase parameter (API integration)

For long-running, tool-heavy Responses API workflows, preambles, `phase` handling, and assistant-item replay are important.

- `phase` is optional at the API level but highly recommended — explicit round-tripping is strictly better than relying on server-side inference
- Use `phase: "commentary"` for intermediate user-visible updates, `phase: "final_answer"` for the completed answer
- Preserve `phase` exactly when replaying prior assistant items so the model can distinguish working commentary from the completed answer
- Do not add `phase` to user messages
- If using `previous_response_id`, OpenAI can often recover prior state without manual replay
- Missing or dropped `phase` can cause preambles to be interpreted as final answers

#### Long-session compaction

When using Compaction in the Responses API:

- Compact after major milestones
- Treat compacted items as opaque state
- Keep prompts functionally identical after compaction

---

## Refining an existing prompt

### 1. Diagnose the problem

Read the prompt and ask what's going wrong. Common issues and fixes:

| Symptom | Likely cause | Fix |
|---|---|---|
| Over-specified / mechanical output | Process-heavy scaffolding | Strip decision trees; rewrite as outcome-first with explicit stop rules |
| Stops early / incomplete output | No completeness contract | Add `<completeness_contract>` |
| Gives up on empty search results | No fallback strategy | Add `<empty_result_recovery>` |
| Skips tool calls | No tool use guidance | Add `<tool_use_guidance>` |
| Over-searches / wasted retrieval | No retrieval budget | Add the retrieval budget block from Step 8 |
| Skips prerequisites | No dependency checking | Add `<dependency_checks>` |
| Fabricates citations | No grounding constraint | Add `<citation_rules>` + `<grounding_rules>` |
| Fabricates specifics in drafts | No creative guardrail | Add the creative drafting block from Step 11 |
| Generic formatting / drift | No output contract | Add `<output_contract>` with sections and lengths |
| Over-formats conversational answers | Default to heavy structure | Add the "formatting serve comprehension" block from Step 4 |
| Inflates edits beyond the ask | No preservation rule | Add the editing-task block from Step 4 |
| Acts on risky steps without asking | No safety gate | Add `<verification_loop>` + `<action_safety>` |
| Ships code without validation | No validation-after-output | Add the Step 10 validation block |
| Over-reasons / slow | Reasoning effort too high, or prompt over-specifies process | Lower effort; strip legacy scaffolding before raising it |
| Drifts in long conversations | No compaction strategy | Compact after milestones; keep prompts identical |
| Guesses when context is missing | No gating | Add `<missing_context_gating>` |
| Tone feels off / inconsistent | No personality block | Add Step 3 personality + collaboration style |
| Dead-air before first tool call | No preamble | Add the Step 7 preamble pattern |

### 2. Apply targeted fixes

- **Start minimal** — the outcome-first structure (Role / Personality / Goal / Success criteria / Constraints / Output / Stop rules) is often enough on its own.
- **Add what's missing** — paste the relevant XML blocks from this skill only when they address a measured failure mode.
- **Remove what's counterproductive** — legacy process scaffolding, absolute ALWAYS/NEVER rules on judgment calls, redundant rules, overly high reasoning effort.
- **Prefer stop rules over "keep going" rules** — GPT-5.5 is more likely to over-search than to under-search; explicit stop conditions usually beat persistence nudges.

### 3. Present the revision

Show a before/after diff explaining each change and the reasoning behind it.
