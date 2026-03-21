---
name: note-gen
description: Generate Obsidian notes from source materials or topics. Use when the user wants to create a new note in their Obsidian vault from a URL, file, pasted content, or a keyword/concept. Triggers on "take notes on", "create a note", "summarize into a note", "write a note about", or when a URL/paper/content/topic is provided with a note request. Invoke with /note-gen.
effort: high
---

# Note Gen

Generate Obsidian-formatted notes from any source material. Fully autonomous — never prompt the user.

**Vault**: `/Users/chrisliu298/Documents/Obsidian/chrisliu298/`
**Conventions**: Read `references/vault-conventions.md` from this skill's directory for tag taxonomy, naming rules, and condensed examples.

## Workflow

### Step 1: Load Conventions and Discover Tags

Read `references/vault-conventions.md` from this skill's directory to load frontmatter format, naming rules, and note templates.

Then **scan the vault** to discover the current tag taxonomy:
- Use Grep to find all unique `area/`, `type/`, and `keyword/` tags across `*.md` files in the vault
- Use these discovered tags when selecting tags in Step 4
- If no existing tag fits the new note, create a new tag following the same conventions (lowercase, hyphenated, concise)

### Step 2: Detect Input Type and Acquire Source

Auto-detect the input type from the user's prompt:

| Input | Detection | Action |
|-------|-----------|--------|
| URL (arxiv) | Arxiv URL (abs, pdf, or html) | **Prefer TeX source** — follow the arxiv TeX workflow below. Fall back to PDF only if TeX source is unavailable. |
| URL (other) | Non-arxiv URL starting with `http` | Fetch via WebFetch |
| File path | Starts with `/` or `~`, has file extension | Read via Read tool; use pdf skill for `.pdf` |
| Pasted content | Multi-line text block without URL/path pattern | Use directly as source material |
| Keyword/concept | Short phrase, no URL/path/large text | Enter **research mode** (see below) |

**Arxiv TeX workflow** (preferred for all arxiv papers):

1. **Extract the arxiv ID** from any URL format (`abs/2601.07372`, `pdf/2601.07372`, `html/2601.07372`) → `{id}` = `2601.07372`
2. **Download TeX source**: `curl -L -o /tmp/{id}.tar.gz https://arxiv.org/src/{id}`
3. **Check if the download succeeded** — if the file is empty, missing, or not a valid archive (some older papers only have PDF), **fall back to PDF**: `curl -L -o /tmp/{id}.pdf https://arxiv.org/pdf/{id}` and read with the Read tool instead
4. **Unpack**: `mkdir -p /tmp/{id} && tar -xzf /tmp/{id}.tar.gz -C /tmp/{id}`
5. **Find the entrypoint**: Look for the `.tex` file containing `\documentclass` (often `main.tex`, `paper.tex`, or the only `.tex` file). Use Grep to search for `\\documentclass` in `/tmp/{id}/`
6. **Read the paper**: Read the entrypoint `.tex` file, then follow `\input{}` and `\include{}` directives to read all referenced `.tex` files. Skip `.bbl`/`.bst`/style files — focus on content files
7. **Proceed to Step 3** with the acquired LaTeX content

> [!tip] TeX source is preferred because LaTeX is plain text — math is already in LaTeX notation (maps directly to Obsidian `$$` blocks), tables and figures are structured, and there are no PDF parsing artifacts.

**Complexity assessment** — decide silently (never ask the user):
- **Direct synthesis**: Source is a complete paper/blog post with sufficient detail — proceed directly
- **Light research**: Source references unexplained concepts — use WebSearch or a single Task subagent to fill gaps
- **Full research**: Only a keyword/concept provided, or source is too thin — use TeamCreate to spin up a research team (see below)

**Research mode** (full research): Use TeamCreate to create a team with parallel agents:
- One agent searches for authoritative papers (arxiv, Semantic Scholar)
- One agent searches for blog posts, tutorials, documentation
- Collect results via the task list, then synthesize the top 2-3 sources into a cohesive note
- Shut down the team when research is complete

If the source is inaccessible (404, paywall), report the error and attempt alternative sources.

### Step 3: Determine Note Type and Filename

| Source | Note Type | `type/` Tag | Filename Pattern |
|--------|-----------|-------------|------------------|
| Arxiv / academic paper | Paper | `type/paper` | `Author YYYY Title.md` |
| Blog post / article | Blog post | `type/blog-post` | `Title.md` |
| Concept / technical content | Concept note | `type/note` | `Concept Name.md` |
| Research-synthesized topic | Concept note | `type/note` | `Concept Name.md` |
| Twitter/X thread | X post | `type/x-post` | `Title.md` |

For paper filenames:
- Use the **first author's last name** only
- Use the publication year
- Use a short, descriptive title (drop articles like "A" or "The" at the start)
- Example: "Proximal Policy Optimization Algorithms" by Schulman et al. 2017 → `Schulman 2017 Proximal Policy Optimization Algorithms.md`

### Step 4: Generate Frontmatter

```yaml
---
aliases: []
date-created: {current timestamp YYYY-MM-DD HH:MM:SS}
date-modified: {same as date-created}
tags:
  - area/{best-fit area tag}
  - type/{detected type}
  - keyword/{topic1}
  - keyword/{topic2}
---
```

- `aliases`: `[]` by default; include well-known acronyms (e.g., `[PPO]`, `[GRPO]`, `[DPO]`)
- `area/`: pick ONE from the tags discovered in Step 1; create a new one only if none fit
- `type/`: pick ONE from the tags discovered in Step 1; create a new one only if none fit
- `keyword/`: 0-3 specific topic keywords, preferring existing keywords from Step 1; create new ones only if none fit

### Step 5: Generate Content by Note Type

**Every note MUST have an H1 heading (`# Title`) as the very first line after the frontmatter `---` closing delimiter.** No blank lines or other content before the H1. The H1 text should match the filename (without `.md`).

**Every note must end with `## Related` then `## References`** (in that order, as the last two sections). Omit a section only if it is genuinely not available or applicable.

#### Paper Notes (`type/paper`)

```
# Author YYYY Title

## Core Thesis
1-3 sentences summarizing the main claim.

## Background and Motivation
Prose explaining the problem and why existing approaches fall short.
Can include bullets for specific prior work limitations or gaps.

## [Method Name / Approach]
Prose building intuition, then equations where central to the method:

$$\mathcal{L}(\theta) = ...$$

Follow with bullets for algorithm steps, design choices, or components.
Use tables for hyperparameters or structured comparisons.

## Key Findings
Mix of prose context and bulleted results. Use tables for benchmark
comparisons. Bold the most important numbers or conclusions.

## Ablation Studies
(if applicable — omit section if paper lacks ablations)

## Limitations and Future Directions
(if applicable)

## Key Takeaways
- Practical implication 1
- Practical implication 2

## Related
- [[Existing Note 1]]
- [[Existing Note 2]]

## References
- [Author YYYY Title](URL)
```

#### Blog Post Notes (`type/blog-post`)

```
# Title

Opening paragraph with context and the post's main argument or insight.

Key points from the post — use bullets, prose paragraphs, or a mix
depending on the content. Sections with `##` headers when the post
covers multiple distinct topics.

## Related
- [[Existing Note 1]]
- [[Existing Note 2]]

## References
- [Title](URL)
```

#### Concept Notes (`type/note`)

```
# Concept Name

## What It Is
Definition and explanation of the core idea. Can be a short paragraph
or a few bullet points depending on complexity.

## How It Works / Why It Matters
Explanation of the mechanism or significance. Use prose to build
intuition, bullets for discrete properties or steps, math where
applicable, tables for comparisons.

## Practical Applications
(if applicable)

## Related
- [[Existing Note 1]]
- [[Existing Note 2]]

## References
- [Source Title](URL)
```

### Step 6: Auto-Link to Existing Vault Notes

Before writing the note:

1. Use Glob to list all `*.md` files in `/Users/chrisliu298/Documents/Obsidian/chrisliu298/`
2. Also read the `aliases` frontmatter field of relevant notes to build a mapping of alias → actual filename
3. When generated content mentions a concept that matches an existing note filename, insert `[[Note Name]]`
4. Use `[[Note Name|Display Text]]` when display text differs from the note name
5. Common mappings: PPO → `[[Proximal Policy Optimization]]`, KL → `[[Forward KL and Backward KL]]`, GAE → `[[Generalized Advantage Estimation|GAE]]`

**Critical wikilink rule**: Wikilinks MUST always use the **actual filename** (without `.md`) as the link target, never an alias. If you want to display an alias or abbreviation, use the pipe syntax:
- Correct: `[[Clipped IS-weight Policy Optimization|CISPO]]`
- Wrong: `[[CISPO]]` (CISPO is an alias, not a filename — this creates a broken link)

To verify: if a file named `Foo Bar.md` exists with `aliases: [FB]`, then link as `[[Foo Bar]]` or `[[Foo Bar|FB]]`, never `[[FB]]`.

### Step 7: Check for Conflicts and Write

1. Check if a note with the target filename already exists in the vault
2. If it exists: do NOT overwrite — inform the user and suggest an alternative filename or offer to append
3. If no conflict: write to `/Users/chrisliu298/Documents/Obsidian/chrisliu298/{filename}.md` using the Write tool

### Step 8: Log to NOTES.md

After writing the note, add an entry to `/Users/chrisliu298/Documents/Obsidian/chrisliu298/NOTES.md` under today's date header (`## YYYY-MM-DD`):

- For papers: `read: [Author YYYY Title](URL) (notes at [[Note Name]])`
- For blog posts: `read: [Title](URL) (notes at [[Note Name]])`
- For concepts/keywords: no NOTES.md entry needed

If today's date header doesn't exist yet, create it at the top (below any existing frontmatter).

## Detail Level

- User says "detailed" / "comprehensive" → full template, ~100-150 lines
- User says "concise" / "brief" → core idea + refs, ~30 lines
- Unspecified → moderate detail matching existing vault notes, ~50-80 lines

## Format Modes

**Default (balanced)**: Mix prose and markdown naturally. Use prose paragraphs for explanations and narrative, but break up content with markdown elements — bullets for discrete points, bold for key terms, tables for comparisons, math blocks for equations, and ASCII diagrams for architectures, pipelines, or any structural/spatial concept that is easier to grasp visually than in prose. A section might open with a prose paragraph then follow with a bullet list of specific findings, or alternate between the two. Avoid walls of unbroken text *and* walls of unbroken bullets.

**Flat list**: If the user explicitly says "list", "flat list", "bullet points", or similar — generate the note as a simple flat bullet list with minimal prose. Each bullet is a self-contained point. Still include frontmatter, `## Related`, and `## References`.

## Math Notation

When the source material contains mathematical content — loss functions, objective functions, update rules, probability distributions, complexity bounds, etc. — **reproduce the key equations in LaTeX**, don't just describe them in English.

- If a paper introduces a new loss function, write the actual equation: `$$\mathcal{L}_{\text{GRPO}}(\theta) = \mathbb{E}_{q \sim \pi_\theta} [\ldots]$$`
- If a method modifies an existing formulation, show both the original and the modification so the reader can see what changed
- Define variables inline after the equation (e.g., "where $\pi_\theta$ is the policy, $r_t(\theta)$ is the probability ratio")
- For algorithms with multiple steps, present the core mathematical relationships, not just a prose summary of "the algorithm computes X then Y"
- Use `$inline$` for referencing symbols in prose (e.g., "the clipping threshold $\epsilon$") and `$$block$$` for standalone equations
- Prefer LaTeX over plain-text approximations: `$\alpha$` not "alpha", `$O(n \log n)$` not "O(n log n)", `$\nabla_\theta J(\theta)$` not "gradient of J with respect to theta"

The goal: a reader should be able to understand the mathematical formulation from the note alone, without going back to the original source.

## Style Checklist

- [ ] **Balanced by default** — prose for narrative/explanation, bullets for discrete points, mix freely within sections
- [ ] **Bullets are welcome** — use them for findings, takeaways, comparisons, steps, components, or any content that reads better as discrete items
- [ ] **Prose for flow** — use paragraphs when building intuition, explaining mechanisms, or connecting ideas
- [ ] **Break up long paragraphs** — if a paragraph has 4+ distinct points, consider converting some to bullets
- [ ] **LaTeX math** — reproduce key equations from the source; use `$inline$` for symbols in prose and `$$block$$` for standalone equations
- [ ] **ASCII illustrations** — use ASCII diagrams to illustrate architectures, pipelines, data flows, hierarchies, or any spatial/structural concept that benefits from a visual (wrap in ` ```text ` blocks)
- [ ] Tables for structured comparisons
- [ ] `##` sections, `###` subsections, no deeper
- [ ] **Bold** key terms on first mention
- [ ] External links: `[Title](URL)`, internal: `[[Note Name]]`
- [ ] Callouts sparingly: `> [!tip]`, `> [!important]`
- [ ] No code blocks unless source contains code
- [ ] No emoji
