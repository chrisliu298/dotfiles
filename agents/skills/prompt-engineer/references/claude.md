# Claude Prompt Craft

Help users write effective prompts for Claude — either from scratch or by refining existing prompts. Based on Anthropic's official prompting best practices.

Guidance splits in two: **general principles** that hold across current models, and **[model-specific behavior](#model-specific-behavior)** that differs enough to change the prompt. Ask which model the prompt targets before drafting, and read the matching model section alongside the general sections. Behaviors below are attributed to specific models wherever the source docs scope them that way — don't apply a model-scoped fix to a different model without checking.

Debugging an existing prompt? Start at the [diagnostic table](#1-diagnose-the-problem) at the bottom — it maps symptoms to the specific block that fixes them.

**Subtract before you add.** The dominant migration failure on current models is leftover scaffolding: verification steps, forced status updates, anti-laziness language, and prescriptive step lists that were needed for older models and now cause over-triggering, wasted tokens, or worse output. When refining a prompt written for an earlier generation, delete first, then add.

Drafting order: [clarify the task](#clarify-the-task) → [core drafting principles](#core-drafting-principles) → [output format](#output-format) → [tool use](#tool-use) → [effort and thinking](#effort-and-thinking) → [safety and autonomy](#safety-and-autonomy) → [long-context and agentic patterns](#long-context-and-agentic-patterns) → [capability-specific blocks](#capability-specific-blocks).

## Writing a prompt from scratch

### Clarify the task

Ask the user:
- What should the model do? (core task)
- Which Claude model, and at what `effort`? (guidance diverges — see [Model-specific behavior](#model-specific-behavior))
- What does good output look like? (format, length, tone)
- What context will be available at runtime? (documents, user input, tool results)
- Will the model have tools? (file editing, search, code execution)

### Core drafting principles

Apply these principles — each one drawn from patterns that meaningfully improve Claude's output quality.

#### Be clear and direct

Think of Claude as a brilliant but new employee who lacks context on your norms. The more precisely you explain what you want, the better the result.

**Golden rule:** Show your prompt to a colleague with minimal context. If they'd be confused, Claude will be too.

Be specific about format and constraints. Use numbered steps when order or completeness matters. If you want "above and beyond" behavior, ask for it — don't expect it to be inferred from a vague prompt.

**Example — vague vs. specific:**

Less effective:
```
Create an analytics dashboard
```

More effective:
```
Create an analytics dashboard. Include as many relevant features and interactions as possible. Go beyond the basics to create a fully-featured implementation.
```

#### Specify the whole task up front

For coding and agentic work this is a structural decision, not a wording one. Opus 5 performs best given the complete task specification up front and then left to run. On Sonnet 5, ambiguous or underspecified prompts delivered progressively across several user turns tend to *reduce* token efficiency and sometimes performance, compared with stating task, intent, and constraints in the first turn.

For interactive coding products, Sonnet 5 guidance is to use `high` or `xhigh` effort, add autonomous features like an auto mode, and design to reduce the number of user turns required.

#### Explain the why

Context or motivation behind instructions helps Claude generalize beyond the literal rule.

**Example — rule vs. motivated rule:**

Less effective:
```
NEVER use ellipses
```

More effective:
```
Your response will be read aloud by a text-to-speech engine, so never use ellipses since the text-to-speech engine will not know how to pronounce them.
```

Claude is smart enough to infer related constraints from the explanation — it will also avoid other TTS-unfriendly punctuation.

The same applies to the task itself. Fable 5 in particular performs better when it understands intent, since context lets it connect the task to relevant information instead of inferring the goal:

```
I'm working on [the larger task] for [who it's for]. They need [what the output
enables]. With that in mind: [request].
```

#### State both sides of a tradeoff

When a rule encodes a cost/benefit decision, give Claude both sides — not just the side you want it to avoid. A one-sided instruction makes Claude overfit to the stated cost.

Less effective:
```
Avoid escalating to a human unless absolutely necessary — it costs $8 per case.
```

More effective:
```
Escalating to a human costs $8 per case, but resolving a billing error wrong
costs a refund and customer trust. Escalate when you can't resolve an issue
confidently; otherwise handle it yourself.
```

Capable models weigh tradeoffs well when given the full picture; giving only the anti-escalation cost produces brittle behavior.

#### Name the source of truth, not just the failure to avoid

Blunt defensive rules — often patches carried over from an older model — can make Claude *withhold information it actually has*. Name the authoritative source and a fallback condition instead of prohibiting an outcome.

Less effective:
```
Never give wrong plan details. Point customers to the account URL.
```

More effective:
```
The provided account context is authoritative for the customer's current or
grandfathered plan. Answer from it when the needed value is present; redirect
to the account URL only when it is genuinely absent.
```

#### Give Claude a role

A role in the system prompt focuses behavior and tone. Even one sentence helps:

```
You are a helpful coding assistant specializing in Python.
```

If the application needs Claude to identify itself or emit model strings correctly, say so explicitly — the model won't reliably know which version it is:

```
The assistant is Claude, created by Anthropic. The current model is Claude Opus 5.
When an LLM is needed, default to Claude Opus 5 unless the user requests otherwise.
The exact model string for Claude Opus 5 is claude-opus-5.
```

#### Structure with XML tags

XML tags help Claude parse complex prompts unambiguously. Wrap each type of content in its own tag to reduce misinterpretation:

```xml
<instructions>
Analyze the annual report and competitor analysis. Identify strategic
advantages and recommend Q3 focus areas.
</instructions>

<documents>
  <document index="1">
    <source>annual_report_2023.pdf</source>
    <document_content>
      {{ANNUAL_REPORT}}
    </document_content>
  </document>
  <document index="2">
    <source>competitor_analysis_q2.xlsx</source>
    <document_content>
      {{COMPETITOR_ANALYSIS}}
    </document_content>
  </document>
</documents>
```

Best practices:
- Use consistent, descriptive tag names
- Nest tags when content has natural hierarchy
- Place long documents (20k+ tokens) at the top of the prompt, with the query/instructions below — this can improve quality by up to 30%
- Separate role, guidelines, policy, tone, and data into their own tags. Rule of thumb: if you can't tell guidelines from policy from data when reading the prompt, neither can Claude.

#### Use examples (few-shot prompting)

Examples are one of the most reliable ways to steer output format, tone, and structure. 3-5 well-crafted examples improve accuracy and consistency.

Make examples:
- **Relevant** — mirror actual use cases closely
- **Diverse** — cover edge cases; vary enough that Claude doesn't lock onto unintended patterns
- **Clearly delimited** — wrap in `<example>` tags (multiple in `<examples>`) so Claude distinguishes them from instructions

Prefer *positive* examples of the behavior you want over instructions about what not to do — this is consistently more effective for tone, verbosity, and communication style, and it's the recommended lever on both Opus 5 and Sonnet 5.

You can also ask Claude to evaluate your examples for relevance and diversity, or to generate additional ones.

#### Ground responses in quotes (for long documents)

Ask Claude to extract relevant quotes before answering. This helps it cut through noise in large documents:

```xml
You are an AI physician's assistant. Your task is to help doctors diagnose
possible patient illnesses.

<documents>
  <document index="1">
    <source>patient_symptoms.txt</source>
    <document_content>{{PATIENT_SYMPTOMS}}</document_content>
  </document>
  <document index="2">
    <source>patient_records.txt</source>
    <document_content>{{PATIENT_RECORDS}}</document_content>
  </document>
  <document index="3">
    <source>patient01_appt_history.txt</source>
    <document_content>{{PATIENT01_APPOINTMENT_HISTORY}}</document_content>
  </document>
</documents>

Find quotes from the patient records and appointment history that are
relevant to diagnosing the patient's reported symptoms. Place these in
<quotes> tags. Then, based on these quotes, list all information that would
help the doctor diagnose the patient's symptoms. Place your diagnostic
information in <info> tags.
```

### Output format

Tell Claude what to do, not what not to do ("Your response should be composed of smoothly flowing prose paragraphs" beats "Do not use markdown"). Match prompt style to desired output — removing markdown from your prompt reduces markdown in the output. XML format indicators work too: "Write the prose sections in `<smoothly_flowing_prose_paragraphs>` tags."

#### Request summaries if you want them

Recent models have a more concise, direct communication style and may skip verbal summaries after tool calls, jumping straight to the next action. (Opus 5 is the exception in the other direction — see [its section](#claude-opus-5).) If you want visibility into what happened, ask for it explicitly:
```
After completing a task that involves tool use, provide a quick summary of the
work you've done.
```

#### Conciseness

Verbosity defaults differ sharply by model — Opus 5 runs long and does not shorten with lower `effort`, Sonnet 5 calibrates to task complexity, Fable 5 elaborates at higher effort. Each has a different lever; see [Model-specific behavior](#model-specific-behavior).

#### Written deliverable length

Files Claude writes to disk, separate from conversational verbosity:
```
Match the length of written documents to what the task needs: cover the
substance, but do not pad with filler sections, redundant summaries, or
boilerplate.
```

#### Minimize markdown

```xml
<avoid_excessive_markdown_and_bullet_points>
When writing reports, documents, technical explanations, analyses, or any
long-form content, write in clear, flowing prose using complete paragraphs
and sentences. Use standard paragraph breaks for organization and reserve
markdown primarily for `inline code`, code blocks (```...```), and simple
headings (## and ###). Avoid using **bold** and *italics*.

DO NOT use ordered lists (1. ...) or unordered lists (*) unless: a) you're
presenting truly discrete items where a list format is the best option, or
b) the user explicitly requests a list or ranking.

Instead of listing items with bullets or numbers, incorporate them naturally
into sentences. This guidance applies especially to technical writing. Using
prose instead of excessive formatting will improve user satisfaction. NEVER
output a series of overly short bullet points.

Your goal is readable, flowing text that guides the reader naturally through
ideas rather than fragmenting information into isolated points.
</avoid_excessive_markdown_and_bullet_points>
```

#### Plain-text math

Claude defaults to LaTeX for mathematical expressions:
```
Format your response in plain text only. Do not use LaTeX, MathJax, or any
markup notation such as \( \), $, or \frac{}{}. Write all math expressions
using standard text characters (e.g., "/" for division, "*" for
multiplication, and "^" for exponents).
```

### Tool use

Current models are trained for precise instruction following and benefit from explicit direction to use specific tools. Suggestive language ("can you suggest some changes") may produce suggestions instead of action; imperative language ("change this function") triggers the tool.

**Instructions don't add capability.** If a task needs something Claude can't do reliably on its own — exact arithmetic, data lookups, current facts, deterministic transforms — telling it the result is "critical" or to "always be accurate" won't help. Give it a tool: declare the tool, describe in its schema what it does and when to use it, and instruct Claude to call it. Reserve prose for *reasoning*; use tools for *execution*.

**Don't over-prompt tool triggering.** Opus 4.5 and Opus 4.6 are more responsive to the system prompt than earlier models, so anti-undertriggering language written for a previous generation now causes *over*triggering. Replace "CRITICAL: You MUST use this tool when..." with "Use this tool when...", and replace blanket defaults ("Default to using [tool]") with targeted ones ("Use [tool] when it would enhance your understanding of the problem"). On Opus 4.6, "If in doubt, use [tool]" will cause overtriggering.

#### Proactive action (default to implementing)

```xml
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's
intent is unclear, infer the most useful likely action and proceed, using
tools to discover any missing details instead of guessing. Try to infer the
user's intent about whether a tool call (e.g., file edit or read) is intended
or not, and act accordingly.
</default_to_action>
```

#### Conservative action (default to researching)

```xml
<do_not_act_before_instructions>
Do not jump into implementation or change files unless clearly instructed to
make changes. When the user's intent is ambiguous, default to providing
information, doing research, and providing recommendations rather than taking
action. Only proceed with edits, modifications, or implementations when the
user explicitly requests them.
</do_not_act_before_instructions>
```

#### Parallel tool calling

```xml
<use_parallel_tool_calls>
If you intend to call multiple tools and there are no dependencies between
the tool calls, make all of the independent tool calls in parallel. Prioritize
calling tools simultaneously whenever the actions can be done in parallel
rather than sequentially. For example, when reading 3 files, run 3 tool calls
in parallel to read all 3 files into context at the same time. Maximize use of
parallel tool calls where possible to increase speed and efficiency. However,
if some tool calls depend on previous calls to inform dependent values like
the parameters, do NOT call these tools in parallel and instead call them
sequentially. Never use placeholders or guess missing parameters in tool calls.
</use_parallel_tool_calls>
```

To go the other way: "Execute operations sequentially with brief pauses between each step to ensure stability."

#### Verbatim delivery mid-task

For long asynchronous agents, define a `send_to_user` tool whose input is rendered directly in your UI. Tool inputs are never summarized, so deliverables and exact numbers arrive intact without ending the turn. Defining it isn't enough; pair it with elicitation language ("when you have content the user must read verbatim, call `send_to_user` with that content — not for narration or reasoning"). See [Fable 5](#claude-fable-5--mythos-5) for the full schema.

### Effort and thinking

**`effort` is the primary control** for the intelligence/latency/cost tradeoff on current models — reach for it before prompt tricks. The ladder, as documented for Sonnet 5:

| Level | Use for |
|---|---|
| `max` | Absolute maximum capability, no constraint on token spend |
| `xhigh` | Hardest coding and agentic work |
| `high` | Default; balances tokens and intelligence |
| `medium` | Cost-sensitive work, trading some intelligence |
| `low` | Short, scoped, latency-sensitive tasks that aren't intelligence-sensitive |

**Check per-model availability before setting a level** — the rungs are not uniform. Sonnet 5 documents all five; Opus 5 and Fable 5 guidance tops out at `xhigh`. Levels are also not comparable *across generations*: re-run an effort sweep on your own evals rather than carrying a setting over. (Rough guide: Sonnet 5 at `medium` ≈ Sonnet 4.6 at `high`, and Sonnet 5 at `high` ≈ Sonnet 4.6 at `max`. When benchmarking, match by observed thinking length, not effort name.)

**Adaptive thinking** (`thinking: {type: "adaptive"}`) is how current models reason: Claude decides when and how much to think, calibrated from `effort` plus query complexity. Defaults differ by model — thinking is on by default on Opus 5 and Sonnet 5; off by default on Opus 4.6 through Opus 4.8 and Sonnet 4.6 when `thinking` is omitted; always on for Fable 5 / Mythos 5. `budget_tokens` (manual extended thinking) is deprecated on 4.6-era models and returns a 400 error on Claude 4.7 and later, including Sonnet 5, Opus 5, and Fable 5. Use `effort` for depth and `max_tokens` as a hard ceiling — and leave `max_tokens` headroom at `high`+ effort, or you'll get a response that's mostly thinking followed by a truncated answer.

Effort is set through `output_config`, alongside the thinking configuration:

```python
client.messages.create(
    model="claude-opus-4-8",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},
    messages=[{"role": "user", "content": "..."}],
)
```

Prompt-level guidance:

- **Prefer general instructions over prescriptive steps.** "Think thoroughly" often beats a hand-written step-by-step plan; Claude's reasoning frequently exceeds what a human would prescribe. (This does not conflict with using numbered steps for *task* structure — it's about not scripting the reasoning itself.)
- **Multishot examples work with thinking.** Use `<thinking>` tags inside few-shot examples to show the reasoning pattern.
- **Guide reflection after tool use:** "After receiving tool results, carefully reflect on their quality and determine optimal next steps before proceeding. Use your thinking to plan and iterate based on this new information, and then take the best next action."
- **Ask Claude to self-check** — "Before you finish, verify your answer against [test criteria]" — which catches errors reliably, especially in coding and math. **Opus 5 is the exception:** it verifies its own work unprompted, and these instructions cause over-verification. This exception is Opus-5-specific; Fable 5 wants verification made *explicit* on long runs, but delegated to fresh-context verifier subagents rather than self-critique (see [its section](#claude-fable-5--mythos-5)).
- **Manual chain-of-thought as a fallback.** With thinking off, ask Claude to reason step by step and use `<thinking>` and `<answer>` tags to separate reasoning from output. On Opus 5, prefer keeping thinking on at low effort instead — with thinking disabled it can leak internal tags into visible output.
- **Steer adaptive-thinking triggering** when the model thinks more often than you want (common with large system prompts):
```
Thinking adds latency and should only be used when it will meaningfully
improve answer quality - typically for problems that require multistep
reasoning. When in doubt, respond directly.
```
- **Mind the word "think" when thinking is off.** Opus 4.5 with extended thinking disabled is particularly sensitive to "think" and its variants. Prefer "consider," "evaluate," or "reason through."

#### Reduce overthinking

```
When you're deciding how to approach a problem, choose an approach and commit
to it. Avoid revisiting decisions unless you encounter new information that
directly contradicts your reasoning. If you're weighing two approaches, pick
one and see it through. You can always course-correct later if the chosen
approach fails.
```

### Safety and autonomy

#### Confirm before irreversible actions

Written for Opus 4.6, which without guidance may take actions that are hard to reverse or affect shared systems; useful for any agent with real-world side effects.

```
Consider the reversibility and potential impact of your actions. You are
encouraged to take local, reversible actions like editing files or running
tests, but for actions that are hard to reverse, affect shared systems, or
could be destructive, ask the user before proceeding.

Examples of actions that warrant confirmation:
- Destructive operations: deleting files or branches, dropping database
  tables, rm -rf
- Hard to reverse operations: git push --force, git reset --hard, amending
  published commits
- Operations visible to others: pushing code, commenting on PRs/issues,
  sending messages, modifying shared infrastructure

When encountering obstacles, do not use destructive actions as a shortcut.
For example, don't bypass safety checks (e.g. --no-verify) or discard
unfamiliar files that may be in-progress work.
```

#### Bound unrequested action

Fable 5 can occasionally take actions nobody asked for — drafting an email, creating defensive git-branch backups. Define the boundary:
```
When the user is describing a problem, asking a question, or thinking out loud
rather than requesting a change, the deliverable is your assessment. Report
your findings and stop. Don't apply a fix until they ask for one. Before
running a command that changes system state (restarts, deletes, config edits),
check that the evidence actually supports that specific action. A signal that
pattern-matches to a known failure may have a different cause.
```

#### Define when to pause

Also Fable 5: rather than enumerating every checkpoint case, state the principle.
```
Pause for the user only when the work genuinely requires them: a destructive
or irreversible action, a real scope change, or input that only they can
provide. If you hit one of these, ask and end the turn, rather than ending on
a promise.
```

### Long-context and agentic patterns

#### Context management

For agents with context compaction:
```
Your context window will be automatically compacted as it approaches its
limit, allowing you to continue working indefinitely from where you left off.
Do not stop tasks early due to token budget concerns. As you approach your
token budget limit, save your current progress and state to memory before
the context window refreshes. Always be as persistent and autonomous as
possible and complete tasks fully, even if the end of your budget is
approaching. Never artificially stop any task early regardless of the context
remaining.
```

In very long sessions Fable 5 can occasionally suggest a new session, offer to summarize and hand off, or trim its own work. This is most often triggered by the harness showing the model a remaining-token countdown — avoid surfacing one where you can. If it must be shown: "You have ample context remaining. Do not stop, summarize, or suggest a new session on account of context limits. Continue the work."

#### Ground progress claims

For long autonomous runs. In Anthropic's testing on Fable 5, this nearly eliminated fabricated status reports even on tasks designed to elicit them:
```
Before reporting progress, audit each claim against a tool result from this
session. Only report work you can point to evidence for; if something is not
yet verified, say so explicitly. Report outcomes faithfully: if tests fail,
say so with the output; if a step was skipped, say that; when something is
done and verified, state it plainly without hedging.
```

#### Workflows across multiple context windows

1. **Different prompt for the first window** — use it to set up a framework (write tests, create setup scripts); later windows iterate on a todo list.
2. **Tests in a structured format** — have Claude write tests up front into e.g. `tests.json`, and state that "it is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."
3. **Quality-of-life tooling** — have Claude create an `init.sh` to start servers, run suites, and lint, so a fresh window doesn't repeat setup.
4. **Prefer a fresh window over compaction** in some cases — current models are extremely effective at recovering state from the filesystem. Be prescriptive about the start: "Call pwd; you can only read and write files in this directory. Review progress.txt, tests.json, and the git logs."
5. **Provide verification tools** — Playwright MCP, computer use for UI checks. Autonomous correctness needs a checker.
6. **Encourage full use of context:** "It's encouraged to spend your entire output context working on the task — just make sure you don't run out of context with significant uncommitted work."

#### State tracking

Structured formats for state data, freeform text for progress notes, git for checkpoints. Ask explicitly for incremental progress tracking.

```json
// tests.json
{
  "tests": [
    { "id": 1, "name": "authentication_flow", "status": "passing" },
    { "id": 2, "name": "user_management", "status": "failing" },
    { "id": 3, "name": "api_endpoints", "status": "not_started" }
  ],
  "total": 200,
  "passing": 150,
  "failing": 25,
  "not_started": 25
}
```

```
// progress.txt
Session 3 progress:
- Fixed authentication token validation
- Updated user model to handle edge cases
- Next: investigate user_management test failures (test #2)
- Note: Do not remove tests as this could lead to missing functionality
```

#### Memory across runs

Fable 5 performs particularly well when it can record lessons from previous runs and reference them; a directory of Markdown files is enough:
```
Store one lesson per file with a one-line summary at the top. Record
corrections and confirmed approaches alike, including why they mattered.
Don't save what the repo or chat history already records; update an existing
note rather than creating a duplicate; delete notes that turn out to be wrong.
```

To bootstrap from existing history: "Reflect on the previous sessions we've had together. Use subagents to identify core themes and lessons, and store them in [X]. Make sure you know to reference [X] for future use."

#### Prevent overengineering

Opus 4.5 and Opus 4.6 tend to overengineer — extra files, unnecessary abstractions, unrequested flexibility. Fable 5 shows a related behavior at higher effort (unrequested tidying and refactoring); its section has a variant block.

```
Avoid over-engineering. Only make changes that are directly requested or
clearly necessary. Keep solutions simple and focused:

- Scope: Don't add features, refactor code, or make "improvements" beyond
  what was asked. A bug fix doesn't need surrounding code cleaned up.
- Documentation: Don't add docstrings, comments, or type annotations to code
  you didn't change. Only add comments where the logic isn't self-evident.
- Defensive coding: Don't add error handling, fallbacks, or validation for
  scenarios that can't happen. Trust internal code and framework guarantees.
  Only validate at system boundaries (user input, external APIs).
- Abstractions: Don't create helpers, utilities, or abstractions for one-time
  operations. Don't design for hypothetical future requirements. The right
  amount of complexity is the minimum needed for the current task.
```

#### Clean up scratch files

Claude uses temporary files as a scratchpad, which usually improves agentic coding outcomes. If you'd rather not accumulate them:
```
If you create any temporary new files, scripts, or helper files for iteration,
clean up these files by removing them at the end of the task.
```

#### Minimize hallucinations

```xml
<investigate_before_answering>
Never speculate about code you have not opened. If the user references a
specific file, you MUST read the file before answering. Make sure to
investigate and read relevant files BEFORE answering questions about the
codebase. Never make any claims about code before investigating unless you
are certain of the correct answer - give grounded and hallucination-free
answers.
</investigate_before_answering>
```

#### Prompt chaining (self-correction)

With adaptive thinking and native subagent orchestration, Claude handles most multistep reasoning internally; explicit chaining still earns its place when you need to inspect intermediate outputs or enforce a pipeline. The most common pattern is generate a draft → review it against criteria → refine. Each step is a separate API call so you can log, evaluate, or branch at any point.

#### Prevent test-chasing

```
Please write a high-quality, general-purpose solution using the standard tools
available. Do not create helper scripts or workarounds to accomplish the task
more efficiently. Implement a solution that works correctly for all valid
inputs, not just the test cases. Do not hard-code values or create solutions
that only work for specific test inputs.

Tests are there to verify correctness, not to define the solution. If the task
is unreasonable or infeasible, or if any of the tests are incorrect, please
inform me rather than working around them.
```

#### Research tasks

Define what a successful answer looks like, ask for cross-source verification, and for complex work add:
```
Search for this information in a structured way. As you gather data, develop
several competing hypotheses. Track your confidence levels in your progress
notes to improve calibration. Regularly self-critique your approach and plan.
Update a hypothesis tree or research notes file to persist information and
provide transparency. Break down this complex research task systematically.
```

#### Subagent control

Current models orchestrate subagents natively and delegate without being told, so **on Opus 4.6 and Opus 5 the usual need is damping** — Opus 4.6 has a strong predilection for spawning subagents where a direct approach would be faster, and Opus 5 also delegates more readily than prior models. Fable 5 points the other way: it is significantly more dependable at dispatching and sustaining parallel subagents, and the guidance there is to *use them frequently* with async orchestration.

Baseline delegation policy:
```
Use subagents when tasks can run in parallel, require isolated context, or
involve independent workstreams that don't need to share state. For simple
tasks, sequential operations, single-file edits, or tasks where you need to
maintain context across steps, work directly rather than delegating.
```

[Opus 5](#claude-opus-5) has a stricter variant of this block; [Fable 5](#claude-fable-5--mythos-5) has an encouraging one. Use the model-specific version when you know the target.

#### Code review harnesses

A filtering instruction ("only report high-severity issues," "be conservative," "don't nitpick") is now followed literally on Sonnet 5 and Opus 5, which shows up as a recall drop even though bug-finding improved. Separate finding from filtering:
```
Report every issue you find, including ones you are uncertain about or
consider low-severity. Do not filter for importance or confidence at this
stage - a separate verification step will do that. Your goal here is coverage:
it is better to surface a finding that later gets filtered out than to
silently drop a real bug. For each finding, include your confidence level and
an estimated severity so a downstream filter can rank them.
```
If you must self-filter in one pass, set a concrete bar ("report any bug that could cause incorrect behavior, a test failure, or a misleading result; omit pure style or naming nits") rather than a qualitative one ("important").

### Capability-specific blocks

#### Frontend design

Avoid generic "AI slop":
```xml
<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend
design, this creates what users call the "AI slop" aesthetic. Avoid this:
make creative, distinctive frontends that surprise and delight.

Focus on:
- Typography: Choose fonts that are beautiful, unique, and interesting. Avoid
  generic fonts like Arial and Inter; opt instead for distinctive choices that
  elevate the frontend's aesthetics.
- Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for
  consistency. Dominant colors with sharp accents outperform timid,
  evenly-distributed palettes. Draw from IDE themes and cultural aesthetics
  for inspiration.
- Motion: Use animations for effects and micro-interactions. Prioritize
  CSS-only solutions for HTML. Use Motion library for React when available.
  Focus on high-impact moments: one well-orchestrated page load with staggered
  reveals (animation-delay) creates more delight than scattered
  micro-interactions.
- Backgrounds: Create atmosphere and depth rather than defaulting to solid
  colors. Layer CSS gradients, use geometric patterns, or add contextual
  effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Cliched color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed
for the context. Vary between light and dark themes, different fonts,
different aesthetics. You still tend to converge on common choices (Space
Grotesk, for example) across generations. Avoid this: it is critical that
you think outside the box!
</frontend_aesthetics>
```

Generic negative steering ("don't use that color," "make it clean and minimal") just moves the model to a different fixed default. Two things actually produce variety: specify a concrete alternative (exact palette hexes, typeface, radius, spacing, section structure), or have the model propose options first — "Before building, propose 4 distinct visual directions tailored to this brief (each as: bg hex / accent hex / typeface, plus a one-line rationale). Ask the user to pick one, then implement only that direction."

#### Vision

Opus 4.5 and 4.6 improved on image processing and data extraction, especially with multiple images in context, and these gains carry into computer use. Opus 5 is strong on charts, documents, diagrams, and UI replication; Fable 5 interprets dense technical images and screenshots with substantially higher accuracy, often using fewer output tokens.

The lever here is a **tool, not prompt language** — this is the clearest case of "instructions don't add capability." Giving Claude a crop tool (or agent skill) so it can zoom into relevant regions shows consistent uplift on image evaluations; Anthropic publishes a crop-tool recipe. On Opus 5, vision is strongest when the model has tools to iteratively analyze, crop, and visually verify its work, and tool use is a more cost-effective lever than raising thinking. Fable 5 is trained to use bash and crop tools to handle flipped, blurry, or noisy images.

When migrating, re-validate prompt-side vision workarounds tuned for older models — they may no longer be needed.

#### Documents, slides, and spreadsheets

Current models create presentations, animations, and visual documents with strong instruction following, usually producing usable output on the first try. Opus 5 additionally handles multi-sheet spreadsheets with non-trivial formulas and well-structured decks — prompt it with any specific styles or templates it must follow.

Request interactive and animated elements explicitly when you want them:
```
Create a professional presentation on [topic]. Include thoughtful design
elements, visual hierarchy, and engaging animations where appropriate.
```

---

## Model-specific behavior

Read the section for the target model *in addition to* the general guidance above. Most cross-model prompt failures are here.

### Claude Opus 5

Built for complex agentic coding and enterprise work, with particular strength on long-horizon tasks. Existing Opus 4.8 prompts run well as-is; these are the behaviors that usually need tuning.

- **Longer default responses, and `effort` won't shorten them.** Effort controls thinking volume, not visible response length. Prompt for conciseness explicitly:
```
Keep responses focused, brief, and concise. Keep disclaimers and caveats
short, and spend most of the response on the main answer. When asked to
explain something, give a high-level summary unless an in-depth explanation
is specifically requested.
```
In a long system prompt, pair this with a short reminder near the end: `<tone_preference>Keep outputs reasonably concise.</tone_preference>`

- **Narrates readily during agentic work.** Describe the cadence and shape you want rather than forbidding narration:
```
Before your first tool call, say in one sentence what you're about to do.
While working, give a brief update only when you find something important or
change direction. When you finish, lead with the outcome: your first sentence
should answer "what happened" or "what did you find," with supporting detail
after it for readers who want it.
```

- **Remove verification instructions.** Opus 5 verifies its own work unprompted. "Include a final verification step," "use a subagent to verify," "double-check your answer," and legacy harness verification stages cause over-verification — remove them rather than rewriting them; token cost drops with no quality loss. (This is Opus-5-specific — do not carry it to Fable 5.)

- **Constrain scope on narrow tasks** — the model can widen a task on its own judgment:
```
Deliver what was asked, at the scope intended. Make routine judgment calls
yourself, and check in only when different readings of the request would lead
to materially different work. If the request seems mistaken or a better
approach exists, say so in a sentence and continue with the task as asked
rather than quietly narrowing, widening, or transforming it. Finish the whole
task, and stop short of actions that are clearly beyond what was asked.
```

- **Damp subagent spawning** — a stricter form of the [general block](#subagent-control):
```
Delegate to a subagent only for large tasks that are genuinely independent and
parallelizable, such as a wide multi-file investigation. Do not delegate work
you can finish yourself in a handful of tool calls, and do not use subagents
to verify or double-check your own work. If one subagent can complete the
task, use one rather than several, and keep spawn counts low.
```

- **Limit correction narration** in user-facing products:
```
Only correct an earlier statement when the error would change the user's code,
conclusions, or decisions. State corrections plainly and briefly, then
continue the task. For slips that change nothing for the user, make the fix
and move on without noting it.
```

- **Effort and thinking:** thinking is on by default and can be disabled only at `high` effort or below. `low`/`medium` produce strong quality at a fraction of the tokens — use them liberally as the primary cost lever, stepping up to `xhigh` for demanding coding and agentic work. Context window is 1M by default and maximum, with instruction following, tool calling, and reasoning consistent throughout.

- **Code review:** high precision *and* recall, with accuracy holding at lower effort — which supports a cheap fast pass at review time plus a thorough pass later. Filtering instructions are followed literally; see [code review harnesses](#code-review-harnesses).

- **Prefer low effort over disabling thinking.** With thinking off, two artifacts appear occasionally: the model writes a tool call as visible text instead of a structured `tool_use` block (the call never runs, and in agentic loops the leaked text persists in history), and it can emit `<thinking>` or other internal XML tags into the response. For most tasks, thinking enabled at `low` effort performs better than thinking disabled at similar cost. If you must disable it, one combined instruction mitigates both — and don't name thinking tags specifically, the general form works better:
```
When you use a tool, you may say a brief sentence first. If no tool can
express what the user asked for, say so instead of guessing. Do not include
internal or system XML tags in your response.
```
Also remove any rule telling the model not to think or reason — that increases tag leakage.

### Claude Sonnet 5

- **Length calibrates to task complexity** rather than a fixed verbosity: shorter on lookups, longer on open-ended analysis. To tighten: "Provide concise, focused responses. Skip non-essential context, and keep examples minimal." Positive examples of the concision you want beat instructions about what not to do.
- **Effort defaults to `high`; raise to `xhigh` for the hardest coding and agentic tasks.** Sonnet 5 respects effort strictly, especially at the low end — at `low`/`medium` it scopes work to exactly what was asked. If reasoning looks shallow on a complex problem, raise effort rather than prompting around it; if you're pinned at `low` for latency, add "This task involves multistep reasoning. Think carefully through the problem before responding."
- **Adaptive thinking is on by default** (a change from Sonnet 4.6, where an omitted `thinking` field meant no thinking). Disable with `thinking: {type: "disabled"}`. `budget_tokens` returns a 400 error.
- **New tokenizer produces ~30% more tokens for the same text** — `max_tokens` limits tuned for Sonnet 4.6 may truncate equivalent output.
- **Sampling parameters are rejected.** Setting `temperature`, `top_p`, or `top_k` to a non-default value returns a 400 error — new for Sonnet-class models. Steer tone and variety through the system prompt instead.
- **More agentic by default**, running tools and self-verification loops readily. With thinking disabled it's *less* likely to reach for tools — add an explicit nudge if you rely on tool calls with thinking off. Higher effort substantially increases tool usage.
- **Interprets prompts literally**, especially at lower effort: it won't silently generalize an instruction from one item to another. State scope explicitly — "Apply this formatting to every section, not just the first one."
- **Remove forced status-update scaffolding** ("After every 3 tool calls, summarize progress") — its own updates are regular and higher-quality. If they're miscalibrated, describe what updates should look like and give examples.
- **Re-evaluate voice prompts.** Long-form prose style shifts with the new baseline. If your product voice is warmer: "Use a warm, collaborative tone. Acknowledge the user's framing before answering."
- **Design defaults settle into a house style** on open-ended briefs. Use the concrete-spec or propose-options approaches from [frontend design](#frontend-design); since `temperature` is unavailable, propose-options is the recommended way to get variety across runs. Sonnet's own compact aesthetics snippet also works: "NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white or dark backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character. Use unique fonts, cohesive colors and themes, and animations for effects and micro-interactions."
- **Computer use:** `computer_20251124`, up to 2576px / 3.75MP. 1080p balances performance and cost; 720p or 1366×768 for cost-sensitive workloads.

### Claude Fable 5 / Mythos 5

Aimed at work that takes a person hours to weeks. Testing it only on simple tasks undersells it — start at the top of your difficulty range.

- **Turns run long by default** — minutes per request at higher effort, hours for autonomous runs. Adjust client timeouts, streaming, and progress indicators *before* migrating, and prefer asynchronous check-ins over blocking. To stop overplanning on ambiguous tasks:
```
When you have enough information to act, act. Do not re-derive facts already
established in the conversation, re-litigate a decision the user has already
made, or narrate options you will not pursue in user-facing messages. If you
are weighing a choice, give a recommendation, not an exhaustive survey. This
does not apply to thinking blocks.
```
- **Thinking is always on; adaptive is the only mode.** Anthropic recommends `high` as the default for most tasks, `xhigh` for the most capability-sensitive workloads, and `medium`/`low` for routine work — lower settings here still often exceed `xhigh` on prior models. Reduce effort if a task completes but takes longer than necessary.
- **Instruction following is strong enough to skip enumeration.** One brief instruction steers as well as a list of named behaviors — and skills or prompts written for prior models are often too prescriptive and can degrade output quality. Audit and delete before adding. The brevity instruction below is the canonical example, replacing a list of individual anti-verbosity rules:
```
Lead with the outcome. Your first sentence after finishing should answer
"what happened" or "what did you find": the thing the user would ask for if
they said "just give me the TLDR." Supporting detail and reasoning come after.
Being readable and being concise are different things, and readability matters
more.

The way to keep output short is to be selective about what you include (drop
details that don't change what the reader would do next), not to compress the
writing into fragments, abbreviations, arrow chains like A → B → fails, or
jargon.
```
- **Prevent unrequested tidying at higher effort** — the Fable variant of the [overengineering block](#prevent-overengineering):
```
Don't add features, refactor, or introduce abstractions beyond what the task
requires. A bug fix doesn't need surrounding cleanup and a one-shot operation
usually doesn't need a helper. Don't design for hypothetical future
requirements: do the simplest thing that works well. Avoid premature
abstraction and half-finished implementations. Don't add error handling,
fallbacks, or validation for scenarios that cannot happen. Trust internal code
and framework guarantees. Only validate at system boundaries (user input,
external APIs). Don't use feature flags or backwards-compatibility shims when
you can just change the code.
```
- **Ground progress claims**, **bound unrequested action**, and **define when to pause** — see [Ground progress claims](#ground-progress-claims) and [Safety and autonomy](#safety-and-autonomy); all three blocks were written for this model's failure modes.
- **Make self-verification explicit on long runs** — the opposite of the Opus 5 advice. Separate, fresh-context verifier subagents outperform self-critique: "Establish a method for checking your own work at an interval of [X] as you build. Run this every [X interval], verifying your work with subagents against the specification." Higher effort also produces excellent verification behavior.
- **Safety classifiers** cover offensive cybersecurity, biology/life-sciences content, and extraction of the model's summarized thinking; benign work in those areas can trip them. Configure [fallback](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback) to Opus 4.8 and handle `stop_reason: "refusal"`.
- **Never instruct it to reproduce its reasoning.** Prompts, skills, or harness rules that tell the model to echo, transcribe, or explain its internal reasoning as response text can trigger the `reasoning_extraction` refusal category and elevate fallbacks. Read structured `thinking` blocks instead, and surface progress with a send-to-user tool.
- **Use subagents frequently.** Fable 5 dispatches parallel subagents readily and reliably sustains communication with long-running ones. Prefer async orchestration over blocking on each return; long-lived subagents that keep context across subtasks save time and cost through cache reads and avoid bottlenecking on the slowest one. "Delegate independent subtasks to subagents and keep working while they run. Intervene if a subagent goes off track or is missing relevant context."
- **Rare early stopping**: deep into a long session it can end a turn with a statement of intent ("I'll now run X") and no tool call, or pause for permission it doesn't need. "Continue" usually suffices. For autonomous pipelines:
```
You are operating autonomously. The user is not watching in real time and
cannot answer questions mid-task, so asking "Want me to…?" will block the
work. For reversible actions that follow from the original request, proceed
without asking. Before ending your turn, check your last paragraph. If it is
a plan, an analysis, a question, a list of next steps, or a promise about work
you have not done ("I'll…"), do that work now with tool calls. End your turn
only when the task is complete or you are blocked on input only the user can
provide.
```
- **Readability after long runs** — dense arrow-chain shorthand and references to unseen thinking are the common failure:
```
Terse shorthand is fine between tool calls. Your final summary is different:
it's for a reader who didn't see any of that. If you've been working for a
while without the user watching, your final message is their first look at any
of it. Write it as a re-grounding, not a continuation of your working thread.
Drop the working shorthand: write complete sentences, spell out terms, avoid
arrow chains and labels you made up earlier, and give each file, commit, or
flag its own plain-language clause. Open with the outcome, then the supporting
detail. If you have to choose between short and clear, choose clear.
```
- **`send_to_user` tool** — for long async agents that must deliver content verbatim mid-turn:
```json
{
  "name": "send_to_user",
  "description": "Display a message directly to the user. Use this for progress updates, partial results, or content the user must see exactly as written before the task finishes.",
  "input_schema": {
    "type": "object",
    "properties": {
      "message": { "type": "string", "description": "The content to display to the user." }
    },
    "required": ["message"]
  }
}
```

### Earlier models (Opus 4.5–4.8, Sonnet 4.6, Haiku 4.5)

- **Thinking defaults:** on Opus 4.6 through Opus 4.8 and Sonnet 4.6, thinking is off when `thinking` is omitted; adaptive thinking is available on 4.6+. `budget_tokens` still works on Opus 4.6 / Sonnet 4.6 but is deprecated.
- **Opus 4.6 does more upfront exploration** at higher effort. Replace blanket tool defaults with targeted ones, remove anti-laziness prompting, and if it's still too aggressive, *lower* `effort` as the fallback lever.
- **Opus 4.5/4.6 over-engineer** (extra files, unnecessary abstractions) — use the [overengineering block](#prevent-overengineering).
- **Opus 4.5 with thinking disabled** is unusually sensitive to the word "think."
- **Prefills** are unsupported from Claude 4.6 onward (and Mythos Preview); earlier models still accept them.

**Context awareness** — Sonnet 5, Sonnet 4.6, Sonnet 4.5, and Haiku 4.5 can track their remaining token budget through a conversation, which pairs well with the memory tool for context transitions. (Note this list spans current and earlier models.)

---

## Refining an existing prompt

### 1. Diagnose the problem

Read the prompt and ask what's going wrong. Common issues and fixes:

| Symptom | Likely cause | Fix |
|---|---|---|
| Output too verbose | No format constraints; Opus 5 default | Add explicit format block ([Output format](#output-format)); on Opus 5 prompt conciseness directly — effort won't do it |
| Written docs bloated | No deliverable-length calibration | [Written deliverable length](#written-deliverable-length) |
| Ignores instructions | Ambiguous or contradictory rules | Simplify; resolve conflicts; use XML tags |
| Instruction applied to only one item | Literal reading (Sonnet 5) | State scope explicitly ("every section, not just the first") |
| Wrong tone/style | No role or examples | Add system prompt role + 3-5 positive examples |
| Hallucinations | No grounding | [Minimize hallucinations](#minimize-hallucinations) + quote-first pattern |
| Fabricated progress claims | Long autonomous run, no evidence rule | [Ground progress claims](#ground-progress-claims) |
| Over-engineers | No scope constraint | [Prevent overengineering](#prevent-overengineering) (Fable 5 has its own variant) |
| Widens the task | Scope not bounded | Opus 5 deliver-what-was-asked block |
| Acts when only asked a question | No action boundary (Fable 5) | [Bound unrequested action](#bound-unrequested-action) |
| Doesn't use tools | Suggestive language ("could you...") | Use imperative ("do X") + `<default_to_action>` |
| Over-uses tools | Anti-laziness prompting (Opus 4.5/4.6) | Dial back "MUST use" / "CRITICAL"; replace blanket defaults with targeted ones |
| Verifies endlessly | Legacy verification instructions | Delete them — **Opus 5 only**; Fable 5 wants verifier subagents |
| Spawns too many subagents | No delegation policy (Opus 4.6 / Opus 5) | [Subagent control](#subagent-control) + the Opus 5 damping block |
| Low code-review recall | "Only report high-severity" taken literally | [Code review harnesses](#code-review-harnesses) — split finding from filtering |
| Thinks too long | Overthinking | Lower effort; add "commit to an approach" guidance |
| Thinks when it shouldn't | Adaptive triggering on a large system prompt | Add the thinking-adds-latency block |
| `<thinking>` tags in output | Thinking disabled (Opus 5) | Re-enable thinking at low effort; remove "don't reason" rules |
| Tool call appears as plain text | Thinking disabled (Opus 5) | Re-enable thinking; add the combined mitigation instruction |
| Elevated refusals/fallbacks | "Explain your reasoning" instructions (Fable 5) | Remove them; read `thinking` blocks instead |
| Stops early / offers a handoff | Context-budget countdown shown (Fable 5) | Hide the countdown; add the ample-context reassurance |
| Ends turn on a promise, no tool call | Rare Fable 5 early stopping | Add the autonomous-operation reminder |
| Weak on images | Prompt-only fix attempted | Give it a crop tool — see [Vision](#vision) |
| Generic frontend | No aesthetic guidance | [Frontend design](#frontend-design); specify a concrete spec or propose-options |
| 400 error on request | `budget_tokens`, prefill, or `temperature` | See the API-change notes per model |

### 2. Apply targeted fixes

- **Remove what the model no longer needs** — verification steps (Opus 5), forced status summaries (Sonnet 5), anti-laziness prompting, prescriptive step lists (Fable 5), "if in doubt use [tool]". This is usually the largest single win when migrating.
- **Check the model scope of every fix** — much of this guidance is model-specific, and several fixes invert between models (verification, subagent encouragement vs damping). Applying an Opus 5 fix to Fable 5 can make the prompt worse.
- **Add what's missing** — role, examples, XML structure, format spec
- **Explain the why** — replace bare rules with motivated instructions so Claude can generalize
- **Drop unsupported prefills** — prefilled assistant responses on the last turn are no longer supported (Claude 4.6+ and Mythos Preview return a 400 error). Replace format-forcing prefills with structured outputs or an explicit format instruction; replace preamble-skipping prefills (`Here is...`) with "Respond directly without preamble."
- **Re-tune effort rather than prompting around depth** — effort levels aren't comparable across generations; sweep on your own evals.

### 3. Present the revision

Show a before/after diff explaining each change and the reasoning behind it.
