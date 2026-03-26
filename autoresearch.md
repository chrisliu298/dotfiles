# Autoresearch: Optimize dotfiles.sh + dfs() execution speed

## Objective
Make `dotfiles.sh` and the `dfs()` shell function as fast as possible.

## Metric
Wall-clock time of `bash dotfiles.sh` (lower is better), median of 3-5 runs.

## Sanity Metric
None — functional correctness verified by checking symlinks and configs exist after run.

## Command
```bash
bash dotfiles.sh
```

## Metric Extraction
Python timing wrapper: `time.time()` before/after subprocess.

## Comparison Protocol
- Same machine (macOS ARM)
- Warm cache (repos already cloned)
- Median of 3+ runs
- All symlinks must resolve correctly after run

## Files in Scope
- `dotfiles.sh`
- `shell/.functions`
- `scripts/install-plugins.sh`

## Off Limits
- Evaluation harness
- Agent configs, skill content, CLAUDE.md

## Constraints
- No new dependencies
- Must preserve all existing functionality (symlinks, skills, MCP, plugins)
- Must not break `dfs()` function

## Guard
After each run, verify: all LINKS symlinks resolve, skills dirs exist.

## What's Been Tried
### Baseline (8.338s)
Profiled bottlenecks:
- Skills git fetch (6 repos parallel): 0.6s
- Plugin git fetch + `claude plugin list` x2: 3.9s (biggest cost)
- `claude mcp list`: 1.65s
- Submodules: 0.13s
- Links + config: <0.1s

### Wave 1 — MCP stamp file (keep)
- MCP stamp (md5 fingerprint) skips 1.65s `claude mcp list`: 8.338s → 5.191s
- Parallel network I/O: 8.338s → 6.054s (not kept, superseded by wave 2)
- Plugin JSON check + fetch TTL: 8.338s → 5.034s (not kept, applied in wave 2)

### Wave 2 — Parallel fetch + plugin JSON + dfs overlap (all keep)
- Parallel fetch overlap + fetch TTL in dotfiles.sh: 5.191s → 4.504s
- Plugin JSON check + fetch TTL in install-plugins.sh: 5.191s → 4.582s
- dfs() overlap local install with remote SSH: code-only (verified syntax)
- Combined: 0.452s warm

### Wave 3 — Background MCP + plugin stamp (keep)
- Background MCP + single `claude mcp list` call: cold 4.7s → 1.8s
- Plugin stamp file: additional warm-path skip
- Combined: 0.429s warm, 2.041s cold
