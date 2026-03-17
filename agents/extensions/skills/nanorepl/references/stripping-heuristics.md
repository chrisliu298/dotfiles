# Stripping Heuristics

Decision framework for identifying what to keep, strip, or defer when building a minimal reimplementation.

## The Core Test

> "If I remove this and the project still does the same THING (just slower or less conveniently), it is NOT core."

Ask: does removing this change WHAT the system does, or only HOW FAST / HOW CONVENIENTLY it does it?

## Always Keep

| Category | Rationale | How to Minimize |
|----------|-----------|-----------------|
| Core algorithm | The irreducible logic that defines what this project IS | Implement explicitly, no black-box calls |
| Essential data structures | Types the algorithm operates on | Use the simplest representation (list > tree > custom class, unless the structure IS the point) |
| Minimum I/O | Enough to prove the algorithm works | stdin/stdout or hardcoded test data at scale 1; file I/O at scale 2+ |
| Invariants | Properties that must always hold for correctness | Assert inline, don't build validation frameworks |

## Always Strip

| Category | Why | What to Do Instead |
|----------|-----|-------------------|
| Abstraction layers with single implementation | Indirection without value | Inline the concrete code |
| Configuration systems | Cognitive overhead; premature flexibility | Hardcode the one good default |
| Plugin / extension / middleware architecture | Framework complexity unrelated to the algorithm | Remove entirely; hardcode the one path |
| Logging, metrics, monitoring | Observability infrastructure, not algorithm | Remove entirely; use print for debugging |
| Build systems, package manifests | Engineering infrastructure | Single file, run directly |
| Module structure (at micro/nano level) | File boundaries obscure the full picture | Merge everything into one file |
| Comments describing "what" | Code should be self-explanatory | Only keep "why" comments for non-obvious choices |
| Error handling for impossible states | Defensive noise | Remove; trust internal invariants |
| Backward-compatibility code | Historical debt | Remove; implement only the current design |
| Performance optimizations that obscure the algorithm | Speed at the cost of clarity | Remove; clarity > performance |
| Type annotations in dynamically-typed languages | Visual noise in educational code | Remove at micro/nano; optional at mini. Keep in statically-typed languages (Rust, Go, TS). |
| Docstrings | The code structure is the documentation | Remove |

## Make Implicit Things Explicit

When production code hides something that is conceptually always present, expose it:

- A KV cache in transformers: "conceptually always there" -- build it explicitly
- A virtual function table: show the dispatch mechanism
- A garbage collector: show the reference counting
- An event loop: show the poll/select/callback chain

This is the opposite of stripping. Some things need to be UN-hidden for understanding. The rule: if a concept is central to understanding but invisible in production code, make it visible.

## Scale-Dependent (Strip at Low Scale, Add at Higher)

| Category | Strip at Scale | Add at Scale | Notes |
|----------|---------------|-------------|-------|
| Concurrency / parallelism | 1-2 | 3+ | Unless concurrency IS the project (e.g., a scheduler) |
| Caching | 1-2 | 3+ | Unless caching IS the project (e.g., a cache system) |
| Serialization / persistence | 1 | 2+ | Add when proving data survives restarts |
| Networking / protocols | 1-2 | 3+ | Unless networking IS the project (e.g., a web server) |
| Authentication / authorization | 1-3 | 4+ | Almost never core to the algorithm |
| Database access | 1-2 | 3+ | Unless the project IS a database |
| CLI argument parsing | 1-3 | 4+ | Hardcode defaults; add argparse at scale 4+ |
| Multiple file formats | 1-3 | 4+ | Support one format well |
| Batching / vectorization | 1-2 | 3+ | Add when demonstrating real-world performance |

## Level-Dependent (micro / nano / mini)

| Decision | micro | nano | mini |
|----------|-------|------|------|
| External dependencies | None. Implement from scratch. | One key dep (e.g., numpy, torch). | Essential deps only. |
| File count | 1 | 1 | 1-3 |
| Abstractions | None. Inline everything. | Minimal (a class for the main entity). | Reasonable structure. |
| Standard library usage | Full stdlib OK | Full stdlib OK | Full stdlib OK |
| Reimplementation depth | Reimplement core deps (e.g., autograd, HTTP parsing) | Use the dep for what it's good at | Use deps normally |

## Decision Flowchart

For each component in the original project:

```
Is it the core algorithm?
  YES -> KEEP (implement explicitly)
  NO  -> Does removing it change WHAT the project does?
           YES -> KEEP (it's actually core, you miscategorized)
           NO  -> Is it conceptually important but hidden?
                    YES -> MAKE EXPLICIT (un-hide it)
                    NO  -> Is it needed at the current scale?
                            YES -> ADD (minimal implementation)
                            NO  -> STRIP
```

## The "One Concept Per Layer" Rule

Each layer should add exactly ONE of these:
1. A new data structure
2. A new algorithm or mechanism
3. A new I/O mode (file, network, user interaction)
4. A new optimization technique
5. A new abstraction level

If a layer adds two concepts, split it. If you can't articulate the single concept a layer adds, rethink the decomposition.

## Examples

**Database (nano-3):**
- L0: In-memory hash map with get/put (~80 LOC) -- core: key-value storage
- L1: + disk persistence with append-only file (~200 LOC) -- concept: durability
- L2: + write-ahead log and crash recovery (~400 LOC) -- concept: atomicity

**Web framework (nano-3):**
- L0: TCP socket listen + route match + response send (~90 LOC) -- core: request routing
- L1: + HTTP parsing, path params, query strings (~250 LOC) -- concept: protocol handling
- L2: + middleware chain, static files, JSON responses (~500 LOC) -- concept: composability

**Transformer (micro-3):**
- L0: Single attention head on hardcoded data (~100 LOC) -- core: attention mechanism
- L1: + multi-head attention, feedforward, layer norm (~300 LOC) -- concept: transformer block
- L2: + token embeddings, training loop, text generation (~600 LOC) -- concept: end-to-end training
