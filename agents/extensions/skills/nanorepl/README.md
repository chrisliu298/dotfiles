# nanorepl

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that builds minimal reimplementations of complex projects by stripping them to their irreducible algorithmic core and layering complexity back one concept at a time.**

> *"What I Cannot Create, I Do Not Understand." -- Richard Feynman*

Inspired by Karpathy's nano/micro/min philosophy. Give it any project -- a GitHub repo, a paper, a concept -- and it decomposes the system into progressive layers, each standalone and runnable, each adding exactly one concept. The gap between the nanorepl and production is engineering, not understanding.

Invoke with `/nanorepl` or ask your agent to "build a minimal version of", "reimplement from scratch", or "strip down to the core".

## Two-Dimensional Complexity Control

Two independent dials shape the output:

**Scale (1-5)** -- how much of the project to replicate:

| Scale | LOC Target | Scope |
|-------|-----------|-------|
| 1 | ~50-200 | Core algorithm only |
| 2 | ~200-500 | + real I/O, runs on real data |
| 3 | ~500-1000 | + essential features, produces useful results |
| 4 | ~1000-2000 | + complete feature set, basic error handling |
| 5 | ~2000+ | + configuration, optimizations, usable tool |

**Level (micro/nano/mini)** -- implementation style:

| Level | Style | Dependencies | Files |
|-------|-------|-------------|-------|
| micro | Pure algorithm, implement everything from scratch | stdlib only | single file |
| nano | Pragmatic minimal | stdlib + 1 | single file |
| mini | Structured minimal, some organization | essential deps | 1-3 files |

**Default:** `nano-3`. Reference points: `micro-1` = microGPT gist (~200 LOC, pure Python autograd + GPT). `nano-3` = nanoGPT (~600 LOC, PyTorch model + training). `mini-5` = nanochat (~8000 LOC, full pipeline).

## Workflow

1. **Target acquisition** -- gather project URL/path/concept, scale/level, language
2. **Source analysis** -- identify the irreducible core, classify every component (keep/strip/defer) using the stripping heuristics framework
3. **Decomposition** -- generate a layer plan (number of layers = scale value), one concept per layer
4. **Plan presentation** -- show overview with stripped components and rationale, wait for confirmation
5. **Progressive building** -- build each layer as a standalone, diffable file with verification at each step
6. **Summary** -- generate project README with layer table, stripping rationale, and run instructions

### Interactive commands during building

| Command | Action |
|---------|--------|
| `next` | Proceed to next layer |
| `explain {thing}` | Walk through specific code or concept |
| `diff` | Show diff from previous layer |
| `modify {request}` | Adjust current layer |
| `done` | Stop here, skip remaining layers |
| `restart {N}` | Regenerate from layer N |

## Guiding Principles

- **The algorithm is NOT simplified.** Strip infrastructure, not core logic. The hard parts stay hard.
- **Every layer runs.** No layer is purely structural. Each produces verifiable output.
- **Code is the documentation.** Zero comments by default. If the code needs a comment to be understood, rename the variable or restructure.
- **Make implicit things explicit.** If something is conceptually present but hidden by production code, expose it.
- **One concept per layer.** If a layer adds two concepts, split it.
- **Standalone and diffable.** Each layer file is self-contained. `diff` between adjacent layers reveals exactly what one concept looks like in code.

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/nanorepl.git ~/.claude/skills/nanorepl
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/nanorepl.git ~/.codex/skills/nanorepl
```

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** -- workflow design and stripping heuristics framework
