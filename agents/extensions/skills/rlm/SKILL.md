---
name: rlm
description: |
  RLM-inspired externalize-and-recurse for data-scale tasks. Use when
  the task involves many files/items, information-dense aggregation, pairwise
  comparisons, or output too large for one response. Especially when direct
  in-context handling would overflow, degrade quality, or miss coverage.
  Do NOT use for small tasks, single-file edits, or tasks solvable by one grep.
user-invocable: true
effort: medium
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
---

# RLM

Adapted from Recursive Language Models (Zhang, Kraska, Khattab 2025). This is not a faithful port: coding agents do not expose a persistent REPL. Files are symbolic state, subagents are expensive recursive calls, and you are the loop controller.

The skill teaches three behaviors that differ from your defaults:

1. **Externalize state** — keep large data in files; work from metadata (paths, counts, snippets) after probing; don't copy bulk content into conversational context.
2. **Programmatic delegation** — generate sub-problems from manifests/code, not verbal ad-hoc descriptions. This enables batched fan-out over many items.
3. **File-built output** — assemble large deliverables in files via structured intermediate artifacts, then summarize to chat.

## Agent Mapping (approximate)

These are honest adaptations, not equivalences.

| RLM Concept | Agent Approximation |
|---|---|
| Prompt as REPL variable | Source files on disk — refer by path, inspect with tools, never copy bulk content into chat |
| `Metadata(state)` at init | `ls`, `wc`, `file`, `head` to enumerate before reading content; plan from metadata alone |
| `sub_RLM()` in code loops | Asynchronous subagent dispatch over programmatically generated batches from a manifest — not ad-hoc verbal delegation |
| REPL persistent state | Files and scratch artifacts (manifests, JSONL, intermediate markdown); each Bash call is stateless, so files are the only durable state |
| `hist` (code + metadata) | Bounded control transcript: keep command outputs compact; large results go to files, not conversational context |
| `Final` variable | Canonical final artifact on disk; return file path + brief chat summary; don't regenerate from prose what's already stored |
| Persistent loop | Orchestrator iteration: collect results, assess, compose new sub-problems, dispatch again |
| Depth-1 recursion | A recommended control strategy: keep recursion shallow and prefer leaf-task workers unless nested delegation is clearly necessary |

## Decision Test

**Use when:**
- Many files/items where coverage matters and context would overflow
- Per-item semantic processing (classify, label, transform each item)
- Pairwise or cross-reference reasoning
- Output too large for one response
- Prior direct attempt became muddled or lost coverage

**Don't use when:**
- Task fits comfortably in one context pass
- One grep/search gives the answer
- Single-file edit or straightforward Q&A
- Subagent coordination overhead would dominate the actual work
- The task is small — recursive approaches can underperform direct calls on small inputs

## Escalation Ladder

Work through these levels. **Exit as early as possible** — most tasks should stop at level 2 or 3. For sparse lookups (finding one thing), level 1 alone is often sufficient.

1. **Probe** — enumerate inputs with metadata tools (`ls`, `wc`, `head`, `file`). Plan decomposition from metadata alone, before reading any content. If the task is a simple lookup, one targeted grep may be all you need — do it and stop.
2. **Filter** — use grep/regex/code to narrow scope. Leverage domain knowledge in search queries (not just literal prompt terms — use priors about what's likely relevant).
3. **Process locally** — many tasks stop here. Code-only filtering without subagents outperformed full recursion on 2 of 5 benchmarks in the paper. Use subagents only for semantically hard work that code can't handle.
4. **Batch for subagents** — group 3-10 items per subagent depending on item size. Never one-per-item unless items are individually large and semantically complex. Launch asynchronously and continue local work while batches run.
5. **Aggregate from files** — always run a synthesis pass over collected sub-results. Never just concatenate. Write the final deliverable to a file, then summarize to chat.

## Complexity Patterns

- **Sparse lookup** (O(1)): one grep, inspect survivors, answer. Do not escalate beyond level 1-2. The overhead of structured decomposition actively hurts on sparse tasks.
- **Per-item processing** (O(n)): enumerate items, batch, process each batch, reduce findings. Start simple — uniform chunking or keyword-based grouping, not elaborate decomposition.
- **Pairwise reasoning** (O(n^2)): generate candidate pairs programmatically, prune with cheap heuristics, recurse on survivors only.

## File-Based State

Create a scratch directory for multi-phase work:

```
/tmp/rlm-<task>/
├── plan.md            # decomposition plan
├── inventory.json     # enumerated units with metadata
├── results/           # per-batch findings (batch-01.md, etc.)
└── final.md           # assembled output artifact
```

Keep formats consistent so aggregation is mechanical. Update `plan.md` after each major phase — long workflows can lose verbal state through summarization, compaction, or context drift.

## Anti-Patterns

| Instead of... | Do this |
|---|---|
| Opening many files into context | Build a manifest, read selectively |
| One subagent per file/item | Batch 3-10 items per call |
| Summarizing before filtering | Filter first with code/regex, summarize survivors |
| Verbal delegation ("analyze these 5 areas") | Enumerate from manifest, dispatch programmatically |
| Keeping intermediate state in prose | Write to files, read back compact summaries |
| Copying bulk data into chat | Keep data in files; work from paths + metadata |
| Generating long output directly in chat | Build in files, return path + summary |
| Rebuilding answer from prose when it's in state | Return the stored artifact directly |

## Gotchas

- **Keep subagent tasks bounded** — for multi-level work, prefer the main agent to collect results, compose the next wave of sub-problems, and dispatch again rather than nesting delegation.
- **Long workflows lose state** — verbal context can be lost through summarization, compaction, or context drift. Checkpoint progress to files after each phase.
- **Over-recursion** is the most common failure mode — models have been observed making thousands of sub-calls for basic tasks. Batch aggressively.
- **Plan-as-answer** — models sometimes return reasoning/plan instead of the computed result. Keep intermediate work clearly separate from final deliverables.
- **Discard-and-regenerate** — models sometimes build the correct answer in state, then discard it and re-derive incorrectly from prose. Once the answer exists in a file, return that file.
- **Over-verification** — continuing to verify after having the answer wastes cost. Set explicit stop conditions.
- **Decomposition is simpler than you think** — the paper found only uniform chunking and keyword search in practice, not elaborate strategies. Start simple.

## Stop Conditions

- Remaining work fits in one direct pass — stop recursing
- Recursion isn't shrinking the search space — redesign decomposition
- Fanout is growing faster than information gain — batch more aggressively
- Sub-calls are producing repetitive low-yield results — stop and synthesize
- Task was mis-classified as data-scale — fall back to direct approach
