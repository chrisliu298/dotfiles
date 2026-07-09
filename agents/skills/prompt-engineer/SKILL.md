---
name: prompt-engineer
description: |
  Guide for writing or refining prompts for Claude, GPT, or Codex, distilled from each
  vendor's official best practices. Use for new prompts, debugging an existing prompt, or
  "prompt engineering", "system prompt", "Claude/GPT/Codex/OpenAI prompt". Accepts arg:
  "claude", "gpt", or "codex".
user-invocable: true
---

# Prompt Engineer

Help users write effective prompts — from scratch or by refining existing ones — using vendor-specific best practices.

## Usage

Covers three model families; the user specifies which:

- **`prompt-engineer claude`** — Anthropic Claude prompting best practices
- **`prompt-engineer gpt`** — OpenAI GPT-5.6 general prompting best practices
- **`prompt-engineer codex`** — OpenAI Codex coding agent best practices

If unspecified, ask which model family the prompt targets. If obvious from context (e.g., they mention "Claude", "Anthropic", "GPT", "OpenAI", "Codex"), use that. If they say "GPT" or "OpenAI" without specifying further, ask whether the prompt is for a general GPT-5.6 application or a Codex coding agent — the guidance differs significantly.

## Workflow

The process is the same regardless of model family:

### Writing a prompt from scratch

**Step 1: Clarify the task** — ask the user:
- What should the model do? (core task)
- What does good output look like? (format, length, tone/structure)
- What context will be available at runtime? (documents, user input, tool results)
- Will the model have tools? (search, file editing, code execution, etc.)

**Step 2: Draft the prompt** — read the appropriate reference file for model-specific patterns and blocks, then draft applying the relevant techniques.

**Step 3: Pre-flight quality pass** — before presenting, read the draft back and design out the failure modes that most often degrade a one-shot prompt. Without an eval loop you can't *measure* these traps, so anticipate them — they're the design flaws an eval would flag, caught without running one. Check:

- **Structure** — can a stranger tell role from policy from guidelines from data from examples at a glance? If you can't tell them apart when reading the prompt, the model can't either. If not, split them into clearly labeled sections (XML tags for Claude; headings or explicit blocks for GPT/Codex).
- **Capability vs. instruction** — does any instruction ask the model to *do* something it can't reliably do (exact arithmetic, external/current lookups, deterministic transforms where exactness matters)? Give it a tool, ask for the missing input, or narrow the task — don't escalate the adjectives. Instructions don't add capability.
- **Tradeoffs** — is any rule stated one-sided (a cost with no counterweight, e.g. "avoid X, it's expensive")? State both sides so the model weighs them, instead of hard-coding the conclusion and causing it to overfit.
- **Over-constraint** — would any blunt `NEVER`/`ALWAYS` rule make the model *withhold information it actually has* or refuse a valid action? Replace the prohibition with a source of truth ("the provided context is authoritative — answer from it; redirect only when the value is genuinely absent").
- **Instruction strength** — are `CRITICAL`/`MUST`/`NEVER` earning their place, or papering over missing structure or a missing tool? Dial back to plain phrasing where they aren't.

For a higher-quality result, have the model critique its own draft against these checks in the same turn, then revise — an inline version of the generate → review → refine pattern.

**Step 4: Present the draft** — show the complete prompt and explain design choices.

### Refining an existing prompt

**Step 1: Diagnose** — read the prompt and ask what's going wrong, then read the reference file and consult its model-specific diagnostic table.

**Step 2: Apply targeted fixes** — add what's missing, remove what's counterproductive, explain the why.

**Step 3: Present the revision** — show a before/after diff explaining each change.

## Model-specific references

Read the corresponding reference file for the full set of patterns, XML blocks, and diagnostic tables:

- **Claude** → `references/claude.md` — clarity, roles, XML structure, examples, output format, thinking guidance, safety controls, agentic patterns, and Claude-specific failure modes.
- **GPT** → `references/gpt.md` — outcome-first prompting, output contracts, follow-through policies, tool persistence, completeness verification, citation/grounding, reasoning effort, verbosity, and GPT-specific failure modes.
- **Codex** → `references/codex.md` — the Codex-Max starter prompt, autonomy/persistence, preambles and personality, tool configuration, plan hygiene, and Codex-specific failure modes.

The Claude and GPT references contain ready-to-paste XML blocks; the Codex reference contains a full starter prompt to customize.
