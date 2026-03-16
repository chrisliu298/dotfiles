---
name: update-readme
description: |
  Update or create README.md for the current repository. Inspects the repo,
  extracts verified facts, preserves strong user-written content, and produces
  a README that helps a new reader succeed quickly without inventing details.
  Use when the user wants to update, improve, or create a README.md file.
  Invoke with /update-readme.
user-invocable: true
allowed-tools: Bash(find:*), Bash(ls:*), Bash(tree:*), Bash(wc:*), Bash(pwd:*), Bash(head:*), Bash(awk:*), Bash(git remote:*), Glob(*), Grep(*), Read(*), Edit(*), Write(*)
---

# Update README

Generate or update `README.md` from repository evidence, not conventions.

## Context

- Working directory: !`pwd`
- Directory tree (top 3 levels): !`find . -maxdepth 3 -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -not -path '*/venv/*' -not -path '*/.venv/*' -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/target/*' -not -path '*/.next/*' -not -path '*/coverage/*' 2>/dev/null | sort | head -80`
- Key manifests: !`find . -maxdepth 2 -type f \( -name "package.json" -o -name "pyproject.toml" -o -name "Cargo.toml" -o -name "go.mod" -o -name "Makefile" -o -name "justfile" -o -name "Taskfile.yml" -o -name "setup.py" -o -name "setup.cfg" -o -name "requirements*.txt" -o -name "Dockerfile*" -o -name "docker-compose*.yml" -o -name "CMakeLists.txt" \) 2>/dev/null | grep -v node_modules | head -20`
- Existing README headings: !`awk '/^#/{print}' README.md 2>/dev/null | head -40 || echo "No README.md found"`
- CLAUDE.md opening: !`head -50 CLAUDE.md 2>/dev/null || echo "No CLAUDE.md found"`
- AGENTS.md opening: !`head -50 AGENTS.md 2>/dev/null || echo "No AGENTS.md found"`
- Git remote: !`git remote -v 2>/dev/null | head -2`

## Core Rule

**Never invent facts.** Every command, path, and claim in the README must be verified against the repository. If something is important but cannot be verified, omit it or ask the user.

**Scope:** This skill targets the root `README.md` unless the user specifies a different path.

## Phase 1: Analyze the Project

Before writing, build a fact table by reading files in this order:

1. **Existing descriptions** — CLAUDE.md, AGENTS.md, `description` fields in manifests. These often contain the best human-written summary.
2. **Entrypoints** — find the main entry (bin scripts, main.py, src/index.ts, cmd/, lib.rs). Read enough to understand what the project *does*.
3. **CLI and API surface** — argument parsers, route definitions, exported functions, `bin` entries. These define what users interact with.
4. **Configuration** — env vars, config files, CLI flags. Note what knobs exist.
5. **Build and test** — CI configs, Makefile/justfile targets, test directories. These reveal how to build, test, and deploy.
6. **Existing README** — read the full README.md if it exists. Note what is accurate, outdated, or missing.

**Evidence ranking:** Package scripts, Make/just targets, CI workflows, executable entrypoints, and tests are stronger evidence than naming conventions or folder structure.

**Determine the project type** — use the strongest repository signals to decide which sections belong:

- CLI tool: Installation, Usage, Configuration
- Library: Installation, API/Usage, Examples
- Service/app: Setup, Running, Configuration
- Research code: Overview, Reproduction, Citation
- Dotfiles, skill, or plugin: Overview, Installation, Usage, Customization
- Monorepo: Overview, Package map, Development

Use this as a heuristic, not a template.

**Stop when you can answer:** What does this project do? Who is it for? How do you install, configure, and use it? What should the reader *not* assume?

## Phase 2: Plan

Before writing, decide:

- **Create vs. update** — if a README exists, identify sections that are accurate (keep), outdated (rewrite), and missing (add). Do not discard custom sections.
- **Section selection** — only include sections with real content. Choose from the project-type table above, or keep existing sections if they work.
- **Depth calibration** — match README length to project complexity. A 50-line script needs 10 lines of README. A framework needs detailed docs. Never pad a simple project.
- **Large READMEs** — if the existing README exceeds 200 lines, prefer targeted edits over full rewrites. Only rewrite sections that are outdated or missing.
- **No-op is valid** — if the README is already accurate and complete, tell the user "The README is up to date — no changes needed" and stop without editing the file.

## Phase 3: Write

**When creating a new README:**

Let the project dictate the shape. Every README must answer:
1. What is this and why would someone use it? (the first line after the title)
2. How do I install/set it up?
3. How do I use it? (with real examples from the codebase)
4. How do I configure it? (if configurable)

Include only if relevant: architecture diagrams (ASCII in ```text blocks), API reference, development setup, license.

**When updating an existing README:**

- **Preserve human voice.** If the description uses first-person, domain-specific language, or tells a story — keep it.
- **Preserve custom sections.** Badges, acknowledgments, FAQ, warnings, migration notes were added intentionally. Keep them.
- **Update stale facts.** Fix file paths that no longer exist, commands that don't match, features that were removed.
- **Match existing style.** If the README uses a different structure (no numbered sections, paragraphs instead of bullets, different heading levels), match its style rather than imposing a new one.

**Style rules:**

- Concise and scannable — bullets over paragraphs, real commands over prose
- Real examples only — every code block must use actual commands and paths from this codebase, not `your-project` or `<placeholder>`
- Show, don't list — one concrete usage example teaches more than five feature bullets
- No decorative elements — no badges, shields, or emoji unless they already exist
- No marketing language — "robust", "seamless", "powerful", "easy-to-use" without proof is noise
- Skip empty sections — if a section would be generic or speculative, omit it entirely
- ASCII diagrams only when they clarify real structure better than prose

## Verify

After writing, spot-check:

1. **Paths** — do all referenced files and directories actually exist? Glob to verify.
2. **Commands** — do install/build/run commands match the manifest and Makefile?
3. **Claims** — does the description match what the entrypoint code actually does?
4. **Preservation** — if updating, confirm no important user-authored sections were deleted.

Fix any issues before finishing.

## Constraints

- Never invent facts — this is the core rule.
- When updating an existing README, never delete user-authored sections without explicit permission.
- Do not add badges, shields, or decorative elements unless they already exist.
- Do NOT delete an existing README.md. If the file seems unnecessary, tell the user rather than removing it.
