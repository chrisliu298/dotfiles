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
- **`prompt-engineer gpt`** — OpenAI GPT-5.5 general prompting best practices
- **`prompt-engineer codex`** — OpenAI Codex coding agent best practices

If unspecified, ask which model family the prompt targets. If obvious from context (e.g., they mention "Claude", "Anthropic", "GPT", "OpenAI", "Codex"), use that. If they say "GPT" or "OpenAI" without specifying further, ask whether the prompt is for a general GPT-5.5 application or a Codex coding agent — the guidance differs significantly.

## Workflow

The process is the same regardless of model family:

### Writing a prompt from scratch

**Step 1: Clarify the task** — ask the user:
- What should the model do? (core task)
- What does good output look like? (format, length, tone/structure)
- What context will be available at runtime? (documents, user input, tool results)
- Will the model have tools? (search, file editing, code execution, etc.)

**Step 2: Draft the prompt** — read the appropriate reference file for model-specific patterns and blocks, then draft applying the relevant techniques.

**Step 3: Present the draft** — show the complete prompt and explain design choices.

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
