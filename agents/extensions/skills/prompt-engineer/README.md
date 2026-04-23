# Prompt Engineer

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that helps you write and refine LLM prompts using vendor-specific best practices.**

Prompt Engineer guides you through writing prompts from scratch or diagnosing and fixing existing ones. It carries three reference guides -- Claude (XML blocks and patterns), GPT-5.5 (cross-cutting prompt patterns), and Codex (coding agent starter prompt and customization) -- distilled from each vendor's official documentation into diagnostic tables and step-by-step workflows.

Invoke with `/prompt-engineer claude`, `/prompt-engineer gpt`, or `/prompt-engineer codex`, or just ask your agent to help you write a prompt and it will pick the right reference automatically.

## What It Does

**Writing from scratch:** The skill walks through a structured workflow -- clarify the task, draft using model-specific patterns, then present the complete prompt with design rationale. Each reference file contains concrete XML blocks (output contracts, tool persistence rules, safety controls, frontend aesthetics, etc.) that can be dropped directly into prompts.

**Refining an existing prompt:** Diagnose what's going wrong using a model-specific failure mode table, apply targeted fixes, and present a before/after diff with reasoning behind each change.

### Model families

| Argument | Reference | Covers |
|----------|-----------|--------|
| `claude` | `references/claude.md` | Clarity, roles, XML structure, examples, output format, thinking guidance, safety controls, agentic patterns, frontend aesthetics |
| `gpt` | `references/gpt.md` | Output contracts, follow-through policies, tool persistence, completeness verification, citation/grounding, reasoning effort, small-model guidance |
| `codex` | `references/codex.md` | Codex-Max starter prompt, autonomy/persistence, preambles and personality, tool configuration, plan hygiene, metaprompting |

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/prompt-engineer.git ~/.claude/skills/prompt-engineer
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/prompt-engineer.git ~/.codex/skills/prompt-engineer
```

## Usage

Tell your agent what you need:

> "Help me write a system prompt for a Claude-based code review agent"

> "/prompt-engineer gpt -- my GPT prompt keeps stopping early and skipping tool calls"

> "I have this prompt but the output is too verbose and ignores my formatting instructions"

The skill determines the target model family from context or asks if ambiguous.

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** -- reference guide curation and diagnostic tables
