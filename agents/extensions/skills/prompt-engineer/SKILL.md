---
name: prompt-engineer
description: |
  Guide for writing and refining prompts for Claude or GPT/Codex models, distilled from each vendor's official best practices. Use this skill whenever the user wants to write a new prompt, improve or debug an existing prompt, or learn model-specific prompting techniques. Also trigger when the user mentions "prompt engineering", "system prompt", "Claude prompt", "GPT prompt", "Codex prompt", "OpenAI prompt", or asks how to get better results from any LLM. Accepts an argument: "claude" for Claude/Anthropic guidance, "gpt" for GPT-5.5 guidance, "codex" for Codex agent guidance.
user-invocable: true
---

# Prompt Engineer

Help users write effective prompts — either from scratch or by refining existing prompts — using vendor-specific best practices.

## Usage

This skill covers three model families. The user specifies which one:

- **`prompt-engineer claude`** — Anthropic Claude prompting best practices
- **`prompt-engineer gpt`** — OpenAI GPT-5.5 general prompting best practices
- **`prompt-engineer codex`** — OpenAI Codex coding agent best practices

If the user doesn't specify, ask which model family the prompt targets. If it's obvious from context (e.g., they mention "Claude", "Anthropic", "GPT", "OpenAI", "Codex"), use that. If the user says "GPT" or "OpenAI" without specifying further, ask whether the prompt is for a general GPT-5.5 application or a Codex coding agent — the guidance differs significantly.

## Workflow

Regardless of model family, the overall process is the same:

### Writing a prompt from scratch

**Step 1: Clarify the task** — ask the user:
- What should the model do? (core task)
- What does good output look like? (format, length, tone/structure)
- What context will be available at runtime? (documents, user input, tool results)
- Will the model have tools? (search, file editing, code execution, etc.)

**Step 2: Draft the prompt** — read the appropriate reference file for model-specific patterns and blocks, then draft the prompt applying the relevant techniques.

**Step 3: Present the draft** — show the complete prompt and explain design choices.

### Refining an existing prompt

**Step 1: Diagnose** — read the prompt and ask what's going wrong. Consult the model-specific diagnostic table in the reference file.

**Step 2: Apply targeted fixes** — add what's missing, remove what's counterproductive, explain the why.

**Step 3: Present the revision** — show a before/after diff explaining each change.

## Model-specific references

After determining the target model family, read the corresponding reference file for the full set of patterns, XML blocks, and diagnostic tables:

- **Claude** → `references/claude.md` — covers clarity, roles, XML structure, examples, output format, thinking guidance, safety controls, agentic patterns, and Claude-specific failure modes.
- **GPT** → `references/gpt.md` — covers output contracts, follow-through policies, tool persistence, completeness verification, citation/grounding, reasoning effort, small-model guidance, and GPT-specific failure modes.
- **Codex** → `references/codex.md` — covers the Codex-Max starter prompt, autonomy/persistence, preambles and personality, tool configuration, plan hygiene, and Codex-specific failure modes.

The Claude and GPT references contain ready-to-paste XML blocks. The Codex reference contains a full starter prompt to customize.
