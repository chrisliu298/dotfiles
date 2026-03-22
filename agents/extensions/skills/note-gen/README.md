# Note Gen

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that generates Obsidian notes from any source material.**

> *Hand it a paper, a URL, a concept, or a keyword. Walk away. Come back to a vault-ready note with frontmatter, wikilinks, and math — filed and logged.*

Note Gen turns your agent into an autonomous note-taking assistant for [Obsidian](https://obsidian.md/). It detects the input type, acquires the source, generates a structured note with proper frontmatter and LaTeX math, auto-links to existing vault notes, checks for filename conflicts, and logs the entry — all without prompting you.

Invoke with `/note-gen` or ask your agent to "take notes on", "create a note about", or "summarize into a note".

## What It Handles

| Input | What happens |
|-------|--------------|
| Arxiv URL | Downloads TeX source for clean math notation (falls back to PDF) |
| Other URL | Fetches content via WebFetch |
| File path | Reads directly (uses pdf skill for `.pdf`) |
| Pasted content | Uses as source material |
| Keyword / concept | Enters **research mode** — spins up parallel agents to search papers and blogs, then synthesizes |

## Note Types

| Source | Type | Filename pattern |
|--------|------|-----------------|
| Academic paper | Paper | `Author YYYY Title.md` |
| Blog post / article | Blog post | `Title.md` |
| Concept / keyword | Concept note | `Concept Name.md` |
| X thread | X post | `Title.md` |

## Key Features

- **Vault-aware tags** — scans existing `area/`, `type/`, `keyword/` tags before selecting; creates new ones only when needed
- **Auto-linking** — finds matching notes in the vault and inserts `[[wikilinks]]` with correct filenames (never aliases)
- **LaTeX math** — reproduces key equations from source papers, not prose descriptions
- **Conflict detection** — refuses to overwrite existing notes
- **Detail levels** — detailed (~100-150 lines), moderate (default, ~50-80), concise (~30)
- **NOTES.md logging** — appends a timestamped entry after writing each note

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/note-gen.git ~/.claude/skills/note-gen
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/note-gen.git ~/.codex/skills/note-gen
```

## Configuration

The skill expects a vault at a configured path. Edit the `Vault` path in `SKILL.md` and the vault location in `references/vault-conventions.md` to point to your Obsidian vault.

## Contributors

- [@chrisliu298](https://github.com/chrisliu298)
- **Claude Code** — workflow design, vault conventions, and note templates
