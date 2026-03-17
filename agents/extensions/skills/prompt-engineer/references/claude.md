# Claude Prompt Craft

Help users write effective prompts for Claude — either from scratch or by refining existing prompts. Based on Anthropic's official prompting best practices.

## Writing a prompt from scratch

### Step 1: Clarify the task

Ask the user:
- What should the model do? (core task)
- What does good output look like? (format, length, tone)
- What context will be available at runtime? (documents, user input, tool results)
- Will the model have tools? (file editing, search, code execution)

### Step 2: Draft the prompt

Apply these principles — each one drawn from patterns that meaningfully improve Claude's output quality.

#### Be clear and direct

Think of Claude as a brilliant but new employee who lacks context on your norms. The more precisely you explain what you want, the better the result.

**Golden rule:** Show your prompt to a colleague with minimal context. If they'd be confused, Claude will be too.

Be specific about format and constraints. Use numbered steps when order matters.

**Example — vague vs. specific:**

Less effective:
```
Create an analytics dashboard
```

More effective:
```
Create an analytics dashboard. Include as many relevant features and interactions as possible. Go beyond the basics to create a fully-featured implementation.
```

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

#### Give Claude a role

A role in the system prompt focuses behavior and tone. Even one sentence helps:

```
You are a helpful coding assistant specializing in Python.
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
- Place long documents at the top of the prompt, with the query/instructions below — this can improve quality by up to 30%

#### Use examples (few-shot prompting)

Examples are one of the most reliable ways to steer output format, tone, and structure. 3-5 well-crafted examples dramatically improve accuracy and consistency.

Make examples:
- **Relevant** — mirror actual use cases closely
- **Diverse** — cover edge cases; vary enough that Claude doesn't lock onto unintended patterns
- **Clearly delimited** — wrap in `<example>` tags so Claude distinguishes them from instructions

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

### Step 3: Control output format

Tell Claude what to do, not what not to do. Match prompt style to desired output.

**Minimize markdown:**
```xml
<avoid_excessive_markdown_and_bullet_points>
When writing reports, documents, technical explanations, analyses, or any
long-form content, write in clear, flowing prose using complete paragraphs
and sentences. Use standard paragraph breaks for organization and reserve
markdown primarily for `inline code`, code blocks (```...```), and simple
headings (###, and ###). Avoid using **bold** and *italics*.

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

**Plain-text math** (Claude defaults to LaTeX):
```
Format your response in plain text only. Do not use LaTeX, MathJax, or any
markup notation such as \( \), $, or \frac{}{}. Write all math expressions
using standard text characters (e.g., "/" for division, "*" for
multiplication, and "^" for exponents).
```

### Step 4: Add tool use guidance (if applicable)

Claude benefits from explicit direction. Suggestive language ("could you suggest...") may not trigger tool use — imperative language ("change this function...") does.

**Proactive action (default to implementing):**
```xml
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's
intent is unclear, infer the most useful likely action and proceed, using
tools to discover any missing details instead of guessing. Try to infer the
user's intent about whether a tool call (e.g., file edit or read) is intended
or not, and act accordingly.
</default_to_action>
```

**Conservative action (default to researching):**
```xml
<do_not_act_before_instructions>
Do not jump into implementation or change files unless clearly instructed to
make changes. When the user's intent is ambiguous, default to providing
information, doing research, and providing recommendations rather than taking
action. Only proceed with edits, modifications, or implementations when the
user explicitly requests them.
</do_not_act_before_instructions>
```

**Parallel tool calling:**
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

### Step 5: Add thinking/reasoning guidance (if applicable)

- Prefer general instructions ("think thoroughly") over prescriptive step-by-step plans
- Use `<thinking>` tags in few-shot examples to show reasoning patterns
- Ask Claude to self-check: "Before you finish, verify your answer against [test criteria]"

**Reduce overthinking:**
```
When you're deciding how to approach a problem, choose an approach and commit
to it. Avoid revisiting decisions unless you encounter new information that
directly contradicts your reasoning. If you're weighing two approaches, pick
one and see it through.
```

### Step 6: Add safety and autonomy controls (for agents)

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

### Step 7: Add long-context / agentic patterns (if applicable)

**Context management** (for agents with context compaction):
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

**State tracking** — use structured formats for state data, freeform text for progress notes, and git for checkpoints:

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

**Prevent overengineering:**
```
Avoid over-engineering. Only make changes that are directly requested or
clearly necessary. Keep solutions simple and focused:

- Scope: Don't add features, refactor code, or make "improvements" beyond
  what was asked.
- Documentation: Don't add docstrings, comments, or type annotations to code
  you didn't change. Only add comments where the logic isn't self-evident.
- Defensive coding: Don't add error handling, fallbacks, or validation for
  scenarios that can't happen. Trust internal code and framework guarantees.
- Abstractions: Don't create helpers, utilities, or abstractions for one-time
  operations. Don't design for hypothetical future requirements.
```

**Minimize hallucinations:**
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

**Prompt chaining (self-correction):** The most common chaining pattern is
generate a draft, have Claude review it against criteria, then refine based on
the review. Each step is a separate API call so you can log, evaluate, or
branch at any point.

**Prevent test-chasing:**
```
Write a high-quality, general-purpose solution using the standard tools
available. Implement a solution that works correctly for all valid inputs,
not just the test cases. Do not hard-code values or create solutions that
only work for specific test inputs. Tests are there to verify correctness,
not to define the solution.
```

**Research tasks:**
```
Search for this information in a structured way. As you gather data, develop
several competing hypotheses. Track your confidence levels in your progress
notes to improve calibration. Regularly self-critique your approach and plan.
Update a hypothesis tree or research notes file to persist information and
provide transparency. Break down this complex research task systematically.
```

**Subagent control** (Claude tends to over-delegate):
```
Use subagents when tasks can run in parallel, require isolated context, or
involve independent workstreams that don't need to share state. For simple
tasks, sequential operations, single-file edits, or tasks where you need to
maintain context across steps, work directly rather than delegating.
```

**Frontend design** (avoid generic "AI slop"):
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

---

## Refining an existing prompt

### 1. Diagnose the problem

Read the prompt and ask what's going wrong. Common issues and fixes:

| Symptom | Likely cause | Fix |
|---|---|---|
| Output too verbose | No format constraints | Add explicit format block (see step 3) |
| Ignores instructions | Ambiguous or contradictory rules | Simplify; resolve conflicts; use XML tags |
| Wrong tone/style | No role or examples | Add system prompt role + 3-5 examples |
| Hallucinations | No grounding | Add `<investigate_before_answering>` + quote-first pattern |
| Over-engineers | No scope constraint | Add overengineering prevention block |
| Doesn't use tools | Suggestive language ("could you...") | Use imperative ("do X") + `<default_to_action>` |
| Over-uses tools | Aggressive anti-laziness prompting | Dial back "MUST use" / "CRITICAL" to normal phrasing |
| Thinks too long | Overthinking | Lower effort; add "commit to an approach" guidance |
| Generic frontend | No aesthetic guidance | Add `<frontend_aesthetics>` block |

### 2. Apply targeted fixes

- **Add what's missing** — role, examples, XML structure, format spec
- **Remove what's counterproductive** — aggressive MUST/NEVER language, redundant instructions, anti-laziness prompting that causes overtriggering
- **Explain the why** — replace bare rules with motivated instructions so Claude can generalize

### 3. Present the revision

Show a before/after diff explaining each change and the reasoning behind it.
