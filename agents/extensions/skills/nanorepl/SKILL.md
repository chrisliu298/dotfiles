---
name: nanorepl
description: |
  Build minimal reimplementations of complex projects following Karpathy's nano/micro/min
  philosophy. Analyzes a target project to identify its irreducible algorithmic core,
  decomposes it into progressive layers, and guides incremental building with verification
  at each step. Works for any domain. Triggers on "build a minimal version of", "nanorepl",
  "reimplement from scratch", "strip down to the core", "build a micro/nano/mini version",
  or when a project URL is provided with a request to understand or rebuild its core.
  Invoke with "nanorepl".
user-invocable: true
---

# nanorepl

> "What I Cannot Create, I Do Not Understand." -- Richard Feynman

Build a minimal reimplementation of any complex project. Strip away everything that isn't the core algorithm, then layer complexity back in one concept at a time.

## Two-Dimensional Complexity Control

Two independent dials control the output:

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
| micro | Pure algorithm, zero external deps, implement everything from scratch | stdlib only | single file |
| nano | Pragmatic minimal, stdlib + one key dependency | stdlib + 1 | single file |
| mini | Structured minimal, essential deps, some organization | essential deps | 1-3 files |

**Default:** `nano-3` -- single file, one dependency, produces real results.

**Reference points:** `micro-1` = microGPT gist (~200 LOC, pure Python autograd + GPT). `nano-3` = nanoGPT (~600 LOC, PyTorch model + training). `mini-5` = nanochat (~8000 LOC, full pipeline).

## Invocation

```
nanorepl                           # Start new project
nanorepl <url>                     # Analyze a specific project
nanorepl <concept> <level>-<scale> # Quick start with parameters
```

## Workflow

### Step 1: Target Acquisition

Use AskUserQuestion to gather parameters:

**Q1 -- Target:** "What do you want to build a minimal version of?"
- URL -- GitHub repo, documentation page, or paper
- Local path -- existing project on disk
- Concept -- describe what it does (e.g., "a B-tree key-value store with WAL")

**Q2 -- Scale and Level:** "What complexity?"
- Show the scale/level matrix above
- Default: nano-3
- User can specify as `{level}-{scale}` (e.g., `micro-2`, `mini-4`)
- Or separately: "scale 3, level nano"

**Q3 -- Language:** "What language?" (default: Python)

**Q4 -- Output location:** "Where to create the project?" (default: `./nanorepl-{name}/`)

If the user provided arguments with `nanorepl`, skip already-answered questions.

### Step 2: Source Analysis

Analyze the target to identify the irreducible core. Approach depends on input type:

If the target is very large (e.g., an entire framework like PyTorch or Linux), ask the user to identify a specific subsystem or capability to reimplement. Do not attempt to analyze an entire large codebase.

| Input | Action |
|-------|--------|
| GitHub URL | Fetch README via WebFetch. Clone if needed. Read entry points and core modules. Trace imports only for core algorithm -- do NOT read the entire repo. |
| Local path | Read directory structure. Read entry points and core modules. Map dependencies between modules. |
| Concept | WebSearch for reference implementations. Read 2-3 authoritative sources. Synthesize understanding of the core algorithm. |
| Paper URL | Fetch and extract the key algorithm, data structures, and evaluation approach. |

**Produce an anatomy** -- classify every component of the original:

| Category | Action |
|----------|--------|
| Core algorithm | KEEP -- implement explicitly, no black boxes |
| Essential data structures | KEEP -- simplest representation that works |
| I/O interface | KEEP -- simplify to minimum viable |
| Everything else | Classify per `references/stripping-heuristics.md` -- STRIP, DEFER to higher scale, or MAKE EXPLICIT |

Read `references/stripping-heuristics.md` from this skill's directory for the full decision framework.

### Step 3: Decomposition

Generate a layer plan. Number of layers = scale value (scale 3 = layers L0, L1, L2).

**Rules:**
- **Layer 0** is always the irreducible core -- the thing that makes this project what it IS, not what makes it fast or convenient
- **One concept per layer** -- each layer adds exactly ONE conceptual component (one data structure, one mechanism, one I/O mode, one optimization). At low scale (1-2), the final layer may bundle 2-3 closely related concepts if they cannot be meaningfully separated (e.g., "HTTP handling" may include method filtering + path params). At scale 3+, strictly one concept per layer.
- **Keep the I/O paradigm stable across layers** -- if L0 uses a REPL, L1 should extend that REPL (not replace it with TCP). If an I/O paradigm shift is needed, it should BE the concept that layer introduces, and the core algorithm code should carry over unchanged so the diff stays clean.
- If a layer's diff from the previous would exceed ~200 LOC, split into sub-layers (2a, 2b)
- Every layer must be runnable and verifiable independently

**Layer template from microGPT blog (example for a language model at micro-5):**
- L0: bigram counting (simplest possible model)
- L1: MLP with manual gradients (add neural network)
- L2: autograd engine (add automatic differentiation)
- L3: self-attention mechanism (add the transformer's key idea)
- L4: full transformer block (add feedforward, norm, residuals)
- L5: Adam optimizer + LR decay (add real training)

For each layer, specify:
- What it adds (3-5 bullets)
- New capability unlocked (what it can do that the previous could not)
- Verification command and expected output
- Approximate LOC

### Step 4: Plan Presentation

Present the decomposition as a clean overview:

```
nanorepl-{name} [{level}-{scale}]: {one-line description}

L0 (~{N} LOC): {core algorithm name}
  adds: {what}
  verify: {command}

L1 (~{N} LOC): + {concept added}
  adds: {what}
  verify: {command}
  diff: {key additions from L0}

...

Stripped from original:
- {thing}: {why it was removed}
- {thing}: {why it was removed}
```

Wait for the user to confirm or adjust before building.

### Step 5: Progressive Building

Build one layer at a time, interactively.

For each layer:

1. **Generate the layer file** (`layer{N}.py` or appropriate extension)
   - Fully self-contained -- copy-paste runnable, no imports from other layers
   - Structured so `diff layer{N-1}.py layer{N}.py` shows clean, meaningful changes
   - **Zero comments except rare "why" notes.** Do not add section labels (`# forward pass`), step markers (`# step 1`), variable descriptions (`# learning rate`), or formula annotations (`# dL/dw`). If the code needs a comment to be understood, rename the variable or restructure the code instead. The only acceptable comment explains a non-obvious design choice (e.g., `# ReLU instead of sigmoid to avoid vanishing gradients`).
   - Short but clear variable names
   - No docstrings, no type annotations (unless language requires them)
   - At `micro` level: zero external deps, implement everything from scratch
   - At `nano` level: allow one key dependency
   - At `mini` level: allow essential deps, may use multiple files per layer

2. **Present with context**
   - Brief explanation of what's new relative to the previous layer
   - For L1+, highlight the key diff (what changed and why)

3. **Show verification**
   - Specific command to run
   - Expected output
   - What to check for correctness

4. **Wait for user input.** Supported commands:

   | Command | Action |
   |---------|--------|
   | `next` | Proceed to next layer |
   | `explain {thing}` | Walk through specific code, function, or concept |
   | `diff` | Show diff from previous layer |
   | `modify {request}` | Adjust current layer |
   | `done` | Stop here, skip remaining layers |
   | `restart {N}` | Regenerate from layer N |

### Step 6: Summary

After all layers are built (or user says "done"), generate `README.md` in the project directory:

```markdown
# nanorepl-{name}

A minimal reimplementation of {project} in {total LOC} lines of {language}.

> "{one-line description of what the irreducible core does}"

## Layers

| File | LOC | Concept Added |
|------|-----|---------------|
| layer0.py | {N} | {core algorithm} |
| layer1.py | {N} | + {concept} |
| ... | ... | ... |

## What Was Stripped

| Original Feature | Why Removed |
|-----------------|-------------|
| {feature} | {rationale from stripping heuristics} |

## Run

{command to run the final layer}

## Compare

- Original: {link to original project}
- This reimplementation: {total LOC} lines vs {original LOC estimate}
```

## Guiding Principles

These are non-negotiable -- they apply to every nanorepl project:

1. **The algorithm is NOT simplified.** Strip infrastructure, not the core logic. "Teeth over education" -- the hard parts stay hard.
2. **Every layer runs.** No layer is purely structural. Each produces verifiable output.
3. **Code is the documentation.** Zero comments by default. No section labels (`# forward pass`), no variable descriptions (`# weights`), no formula annotations. If the code isn't clear, rename variables or restructure -- don't add a comment.
4. **Make implicit things explicit.** If something is conceptually present but hidden by production code, expose it. Clarity > performance.
5. **One concept per layer.** If a layer adds two concepts, split it. At scale 1-2, the final layer may bundle closely related concepts that can't be meaningfully separated.
6. **Standalone and diffable.** Each layer file is self-contained. `diff` between adjacent layers reveals exactly what one concept looks like in code.
7. **No magic.** "It's a big math function." Every mechanism is visible and traceable.
8. **Everything else is just efficiency.** The gap between the nanorepl and production is engineering, not algorithmic understanding.

## Fixed Behaviors

| Behavior | Rule |
|----------|------|
| Layer files | Always standalone, never import from other layers |
| File naming | `layer{N}.py` at micro/nano level. At mini level with multiple files per layer: `layer{N}/` directory (e.g., `layer2/model.py`, `layer2/train.py`) |
| Default language | Python unless user specifies otherwise |
| Default complexity | nano-3 |
| Layer 0 | Always the irreducible core, always present |
| Verification | Required for every layer -- no unverifiable code |
| Dependencies at micro | Zero. Implement from scratch, including things like autograd, HTTP parsing, etc. |
| Dependencies at nano | One key dependency maximum |
| Comments | Zero comments by default. Only a rare "why" comment for a non-obvious design choice. No section labels, no variable descriptions, no formula annotations, no step markers. |
| README | Always generated at the end |
