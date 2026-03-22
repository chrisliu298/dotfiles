# Citation Assistant

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that adds verified citations to academic LaTeX documents.**

The hardest part of writing a paper isn't finding papers to cite — it's making sure every citation is real. Citation Assistant scans your LaTeX sections for unsupported claims, searches multiple academic databases in parallel, cross-verifies each paper in 2+ sources, and fetches BibTeX via DOI. If it can't verify a paper, it marks `[CITATION NEEDED]` instead of guessing.

Invoke with `/citation-assistant` or ask your agent to "add citations to the introduction."

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  1. Scan section for unsupported claims             │
│  2. List gaps to user before searching              │
├─────────────────────────────────────────────────────┤
│  3. Search in parallel:                             │
│     Semantic Scholar + Web Search + Exa MCP         │
│  4. Cross-verify each paper in 2+ sources           │
│  5. Fetch BibTeX via DOI (never from memory)        │
├─────────────────────────────────────────────────────┤
│  6. Append to .bib, insert \cite{} commands         │
│  7. Report what was added and why                   │
└─────────────────────────────────────────────────────┘
```

The skill checks your existing `.bib` file first to avoid duplicates, detects your citation style (`\cite{}`, `\citep{}`, `\citet{}`), and matches it throughout.

## Usage

```
/citation-assistant                     # Ask which section needs citations
/citation-assistant [section]           # Add citations to a specific section
/citation-assistant verify              # Verify all existing citations
```

### Example

> "Add citations to the related work section"

The agent will:
1. Read the section and list each claim that lacks a citation
2. Search Semantic Scholar, web, and Exa for relevant papers
3. Verify each paper exists in multiple sources
4. Fetch BibTeX via DOI and append to your `.bib` file
5. Insert citation commands matching your document's style

For each citation added, it reports the claim being supported, the paper title and authors, why the paper is relevant, and the BibTeX key.

## The No-Hallucination Rule

Hallucinated citations are academic misconduct. This skill enforces a strict verification pipeline:

- **Never generates BibTeX from memory** — always fetches via DOI or constructs from verified metadata
- **Cross-verifies in 2+ sources** — Semantic Scholar, CrossRef, arXiv
- **Marks unverifiable claims** as `[CITATION NEEDED]` instead of guessing
- **Shows gaps before searching** — you approve the plan before any citations are added

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/citation-assistant.git ~/.claude/skills/citation-assistant
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/citation-assistant.git ~/.codex/skills/citation-assistant
```

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
