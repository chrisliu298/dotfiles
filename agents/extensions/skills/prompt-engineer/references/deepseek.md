# DeepSeek V4 Prompt Craft

Help users write effective prompts for DeepSeek V4 (Pro and Flash) — either from scratch or by refining existing prompts. Based on DeepSeek's published guidance and observed production behavior.

DeepSeek V4 is an open-weight Mixture-of-Experts family (V4-Pro ≈ 1.6T total / 49B active, V4-Flash ≈ 284B total / 13B active) with a 1M-token context window and up to 384k output tokens. Both models share the same prompt surface; pick Flash for cheap quick answers and Pro for multi-step reasoning or agentic work.

When DeepSeek is reached via the Anthropic-compatible endpoint and driven by Claude Code (e.g., the `ds`/`dsx` aliases or `relay call --to deepseek`), the prompt surface is the Claude Code user message — system-prompt guidance below applies to whatever wrapper composes the request.

## Core philosophy: structured prompts with thinking effort

DeepSeek V4 was trained heavily on XML-tagged instruction data, so structured prompts with explicit sections outperform free-form English for non-trivial tasks. Thinking mode is a request parameter (not a separate model), exposed as two effort tiers: `high` (default for regular requests) and `max`.

- Default to XML scaffolding when the task has more than one section or constraint.
- Use Markdown headings only when the consumer is a human reading the output, or when XML is genuinely overkill.
- Switch to JSON when wiring the prompt into a multi-message API payload.
- Re-evaluate whether `high` is sufficient before reaching for `max` — `max` doubles latency and rarely changes simple answers.

## CO-STAR for complex prompts

DeepSeek responds best to prompts that name all six dimensions explicitly. Use all six for complex tasks; drop the irrelevant ones for simple ones.

| Dimension | What to say |
|---|---|
| **Context** | Who you are, what you're working on, what the model needs to assume |
| **Objective** | One concrete deliverable. "Help me" is not an objective. |
| **Style** | Doc, bullets, code-heavy, Socratic, terse |
| **Tone** | Direct, warm, critical, neutral |
| **Audience** | Reader's expertise level and goals |
| **Response format** | Sections, length cap, required artifacts |

```xml
<context>
We're hardening the auth layer of a B2B SaaS before a SOC 2 audit. The
codebase is Python 3.12 + FastAPI. Tests live in tests/ and run under pytest.
</context>

<objective>
Identify OWASP Top 10 vulnerabilities in src/auth.py, fix each in place, and
verify with pytest. Return a one-line summary per fix.
</objective>

<style>
Code-heavy. Show patches before prose. Skip preamble.
</style>

<tone>
Direct. Flag uncertainty explicitly. No hedging on safe fixes.
</tone>

<audience>
Senior engineer who already knows the codebase.
</audience>

<response_format>
- A summary table at the top: file, line, vulnerability, fix
- Then the diffs, grouped by file
- Cap at 400 words excluding diffs
</response_format>
```

## Thinking mode (effort)

DeepSeek V4 has two thinking tiers, controlled by the `CLAUDE_CODE_EFFORT_LEVEL` env var when invoked through Claude Code or by the equivalent API parameter when called directly.

| Effort | When to use |
|---|---|
| `high` | Default. Code review, refactoring, multi-step reasoning, agentic tool use. |
| `max` | Eval-bound questions, frontier coding, deep architectural analysis. Doubles latency. |

**Quirks worth knowing:**

- **Minimal system prompt with DeepThink.** Long meta-instructions degrade thinking-mode quality. Move policy and persona into the user message body when running at `max`.
- **Sometimes skips the reasoning phase.** If you see the model jump straight to an answer when you wanted reasoning, prepend `Please start your response with the <think> tag.` to re-activate chain-of-thought.
- **`max` is for hard problems, not anxious ones.** Cranking effort on a simple lookup wastes latency without lifting quality.

## Production patterns (what actually works)

Drawn from teams running V4 in production:

- **Positive framing beats negative.** "Include X, Y, Z" lifts quality more than "don't hallucinate" or "never use Z." Reserve negative constraints for hard safety/policy guardrails.
- **Skip the personality.** Role prompts like "you are a witty developer" reduce consistency. Stay professional and task-focused.
- **Lighter safety layer.** For agentic tasks with tool access, state explicitly what success looks like AND what the agent must never do — DeepSeek won't refuse risky operations as readily as Claude.
- **Cache prefixes aggressively.** Put stable instructions and few-shot examples at the very start; per-call variables go at the end. Output tokens cost ~10× cached input on Flash and ~24× on Pro.

## Suggested prompt structure (XML)

```xml
<role>
[1-2 sentences defining function, expertise, scope]
</role>

<context>
[background, constraints from environment, assumptions to make]
</context>

<task>
[the one specific deliverable]
</task>

<success_criteria>
[what must be true before the answer is final]
</success_criteria>

<constraints>
[policy, safety, format limits — positive framing preferred]
</constraints>

<output_format>
[sections, length, artifact requirements]
</output_format>

<examples>
[3-5 input/output pairs if format matters]
</examples>
```

Start with the minimum (role + task + output_format) and add sections only when a measured failure mode justifies them.

## JSON output

`response_format=json_object` returns valid JSON only if the prompt:
- Contains the word "json" literally
- Includes a small example schema
- Has `max_tokens` high enough to avoid truncation

Otherwise the model may emit JSON-shaped text inside prose.

## Migration notes

If you see `model="deepseek-chat"` or `model="deepseek-reasoner"` in older code, those legacy IDs were retired on 2026-07-24. Switch to `deepseek-v4-flash` (was `deepseek-chat`) or `deepseek-v4-pro` (was `deepseek-reasoner`). The base URL is unchanged.

---

## Refining an existing prompt

### 1. Diagnose

| Symptom | Likely cause | Fix |
|---|---|---|
| Output too verbose | No length cap | Add `<response_format>` with explicit word limit |
| Skips reasoning at `max` | DeepThink skipped | Prepend "start with <think> tag" |
| Ignores sections | Unstructured prose | Switch to XML scaffolding |
| Wrong tone | No CO-STAR Tone | Add explicit `<tone>` |
| Refuses to act on agentic task | Over-cautious framing | Drop "never do X" stack; replace with positive success criteria |
| Hallucinates facts | Negative anti-hallucination prompts | Replace "don't hallucinate" with "cite the source file:line for each claim" |
| Latency too high | `max` for a routine task | Drop to `high` |

### 2. Apply targeted fixes

- **Add what's missing** — CO-STAR sections, XML tags, response format
- **Remove what's counterproductive** — anti-laziness MUSTs, personality fluff, long system prompts in DeepThink mode
- **Reframe negatives as positives** — "include X" instead of "don't omit X"

### 3. Present the revision

Show a before/after diff and explain each change in one line.
