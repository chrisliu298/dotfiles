# GPT-5.4 Prompt Craft

Help users write effective prompts for OpenAI GPT models — either from scratch or by refining existing prompts. Based on OpenAI's official prompt guidance. For Codex coding agents, see `references/codex.md` instead.

## Writing a prompt from scratch

### Step 1: Clarify the task

Ask the user:
- What should the model do? (core task)
- What does good output look like? (format, length, structure)
- What context will be available? (documents, tool results, prior conversation)
- Will the model have tools? (search, terminal, file edit, code execution)

### Step 2: Draft the prompt

Apply these patterns — each one addresses a real failure mode observed in GPT workflows.

#### Define an output contract

GPT performs best when you explicitly state what the output should look like. This prevents drift and keeps outputs compact.

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

#### Set a follow-through policy

Define when to proceed autonomously vs. when to ask permission. This prevents the model from stalling on obvious tasks or acting on risky ones without confirmation.

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

#### Set instruction priorities

When instructions might conflict, state the hierarchy explicitly:

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

#### Handle mid-conversation updates

Use scoped, explicit steering messages that state scope, override, and carry-forward:

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

### Step 3: Add tool use guidance (if applicable)

#### Tool persistence

A common failure mode is skipping tool calls because the right end state seems obvious. Prevent this:

```xml
<tool_persistence_rules>
- Use tools whenever they materially improve correctness, completeness, or
  grounding.
- Do not stop early when another tool call is likely to materially improve
  correctness or completeness.
- Keep calling tools until:
  (1) the task is complete, and
  (2) verification passes (see <verification_loop>).
- If a tool returns empty or partial results, retry with a different strategy.
</tool_persistence_rules>
```

#### Dependency checking

Ensure prerequisites happen before downstream actions:

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

### Step 4: Add completeness and verification

These blocks address the most common failure modes in multi-step workflows — incomplete execution, false negatives from empty results, and unverified output.

#### Completeness contract

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

#### Verification loop

```xml
<verification_loop>
Before finalizing:
- Check correctness: does the output satisfy every requirement?
- Check grounding: are factual claims backed by the provided context or tool
  outputs?
- Check formatting: does the output match the requested schema or style?
- Check safety and irreversibility: if the next step has external side effects,
  ask permission first.
</verification_loop>
```

#### Missing context gating

```xml
<missing_context_gating>
- If required context is missing, do NOT guess.
- Prefer the appropriate lookup tool when the missing context is retrievable;
  ask a minimal clarifying question only when it is not.
- If you must proceed, label assumptions explicitly and choose a reversible
  action.
</missing_context_gating>
```

#### Action safety (for agents that take actions)

```xml
<action_safety>
- Pre-flight: summarize the intended action and parameters in 1-2 lines.
- Execute via tool.
- Post-flight: confirm the outcome and any validation that was performed.
</action_safety>
```

### Step 5: Add citation and grounding rules (if applicable)

For research, review, and information tasks:

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

**Research mode** — use for research, review, and synthesis tasks (not short execution tasks):

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

### Step 6: Add reasoning effort guidance (if applicable)

Reasoning effort is a last-mile tuning knob, not the primary way to improve quality. Before increasing reasoning effort, first add completeness contracts, verification loops, and tool persistence rules.

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

Recommended starting points:

- `none`: Fast, cost-sensitive, latency-sensitive tasks where the model doesn't need to think. For GPT-5.4 specifically, `none` can already perform well on action-selection and tool-discipline tasks.
- `low`: Latency-sensitive tasks where a small amount of thinking produces meaningful accuracy gain, especially with complex instructions.
- `medium` or `high`: Tasks that truly require stronger reasoning and can absorb the latency/cost tradeoff. Start here for research-heavy workloads: long-context synthesis, multi-document review, conflict resolution, strategy writing.
- `xhigh`: Avoid as a default unless evals show clear benefits. Best for long, agentic, reasoning-heavy tasks where maximum intelligence matters more than speed or cost.

Most teams should default to the `none`, `low`, or `medium` range.

#### Migration starting points

Use one-change-at-a-time discipline: switch model first, pin `reasoning_effort`, run evals, then iterate.

| Current setup | Suggested GPT-5.4 start | Notes |
|---|---|---|
| `gpt-5.2` | Match the current reasoning effort | Preserve latency and quality profile first, then tune. |
| `gpt-5.3-codex` | Match the current reasoning effort | For coding workflows, keep the reasoning effort the same. |
| `gpt-4.1` or `gpt-4o` | `none` | Keep snappy behavior, increase only if evals regress. |
| Research-heavy assistants | `medium` or `high` | Use explicit research multi-pass and citation gating. |
| Long-horizon agents | `medium` or `high` | Add tool persistence and completeness accounting. |

#### Small-model guidance (gpt-5.4-mini and gpt-5.4-nano)

These models are highly steerable but less likely to infer missing steps, resolve ambiguity implicitly, or package outputs as intended unless specified directly. Prompts for smaller models are often longer and more explicit.

**Prompting gpt-5.4-mini:**
- Put critical rules first
- Specify the full execution order when tool use or side effects matter
- Don't rely on "you MUST" alone — use structural scaffolding: numbered steps, decision rules, explicit action definitions
- Separate "do the action" from "report the action"
- Show the correct flow, not just the final format
- Define ambiguity behavior explicitly: when to ask, abstain, or proceed
- Specify packaging directly: answer length, follow-up questions, citation style, section order
- Prefer scoped instructions (`after the final JSON, output nothing further`) over `output nothing else`

**Prompting gpt-5.4-nano:**
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

### Step 7: Add specialized workflow patterns (as needed)

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

These patterns are from the GPT-5.4 guide for general GPT-based coding agents. For Codex-specific agent patterns (starter prompt, preambles, tools), use `references/codex.md` instead.

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

For long-running or tool-heavy agents that may emit commentary before tool calls or before a final answer, use the `phase` field on assistant messages:

- `phase` is optional at the API level but highly recommended — explicit round-tripping is strictly better than relying on server-side inference
- Use `phase` for agents that may emit commentary before tool calls or before a final answer
- Preserve `phase` when replaying prior assistant items so the model can distinguish working commentary from the completed answer
- Do not add `phase` to user messages
- If using `previous_response_id`, OpenAI can often recover prior state without manual replay
- Missing or dropped `phase` can cause preambles to be interpreted as final answers

#### Long-session compaction

When using Compaction in the Responses API:

- Compact after major milestones
- Treat compacted items as opaque state
- Keep prompts functionally identical after compaction
- GPT-5.4 tends to remain more coherent and reliable over longer, multi-turn conversations with fewer breakdowns as sessions grow

---

## Refining an existing prompt

### 1. Diagnose the problem

Read the prompt and ask what's going wrong. Common issues and fixes:

| Symptom | Likely cause | Fix |
|---|---|---|
| Stops early / incomplete output | No completeness contract | Add `<completeness_contract>` |
| Gives up on empty search results | No fallback strategy | Add `<empty_result_recovery>` |
| Skips tool calls | No tool persistence rule | Add `<tool_persistence_rules>` |
| Skips prerequisites | No dependency checking | Add `<dependency_checks>` |
| Fabricates citations | No grounding constraint | Add `<citation_rules>` + `<grounding_rules>` |
| Generic formatting / drift | No output contract | Add `<output_contract>` with sections and lengths |
| Acts on risky steps without asking | No safety gate | Add `<verification_loop>` + `<action_safety>` |
| Over-reasons / slow | Reasoning effort too high | Lower effort; improve prompt before raising it |
| Drifts in long conversations | No compaction strategy | Compact after milestones; keep prompts identical |
| Guesses when context is missing | No gating | Add `<missing_context_gating>` |

### 2. Apply targeted fixes

- **Add what's missing** — paste the relevant XML blocks from this skill directly into the prompt
- **Remove what's counterproductive** — vague instructions, redundant rules, overly high reasoning effort
- **Start with the smallest prompt that passes evals** — add blocks only when they fix a measured failure mode

### 3. Present the revision

Show a before/after diff explaining each change and the reasoning behind it.
