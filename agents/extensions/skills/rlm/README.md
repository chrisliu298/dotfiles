# RLM

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that teaches AI agents to handle data-scale tasks through recursive decomposition.**

Adapted from the [Recursive Language Models](https://arxiv.org/abs/2512.24601) paper (Zhang, Kraska, Khattab 2025). When a task involves many files, information-dense aggregation, pairwise comparisons, or output too large for one response, RLM teaches your agent to externalize state to files, generate sub-problems programmatically from manifests, and assemble output from structured intermediate artifacts.

Invoke with `/rlm` or let it auto-trigger on qualifying tasks.

## What It Teaches

Three behaviors that differ from agent defaults:

1. **Externalize state** -- keep large data in files; work from metadata (paths, counts, snippets) after probing; don't copy bulk content into conversational context
2. **Programmatic delegation** -- generate sub-problems from manifests and code, not verbal ad-hoc descriptions; this enables batched fan-out over many items
3. **File-built output** -- assemble large deliverables in files via structured intermediate artifacts, then summarize to chat

## Escalation Ladder

The skill works through levels, exiting as early as possible:

1. **Probe** -- enumerate inputs with metadata tools before reading content
2. **Filter** -- narrow scope with grep/regex/code
3. **Process locally** -- code-only filtering handles many tasks without subagents
4. **Batch for subagents** -- group items into batches for async dispatch
5. **Aggregate from files** -- synthesis pass over collected sub-results

Most tasks should stop at level 2 or 3. The skill includes explicit guidance for when *not* to use recursive decomposition -- it actively hurts on small or sparse tasks.

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/rlm.git ~/.claude/skills/rlm
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/rlm.git ~/.codex/skills/rlm
```

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code**
- **Codex**
