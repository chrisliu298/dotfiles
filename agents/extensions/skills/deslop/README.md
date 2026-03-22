# Deslop

**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that removes AI-generated slop from code changes.** Based on the original [deslop prompt](https://github.com/lucasb-eyer/dotfiles/blob/master/_codex/prompts/deslop.md) by [@lucasb-eyer](https://github.com/lucasb-eyer).

AI agents leave fingerprints: comments that restate the code, defensive checks at internal boundaries, single-use variables, redundant type annotations, docstrings added to files that never had them. Deslop reads the diff against main, studies the existing file style, and surgically removes what doesn't belong -- while preserving every line of actual feature code.

Invoke with `/deslop` after any AI-assisted coding session.

## What It Catches

- **Code-restating comments** -- `// Check if value is null` before `if (val === null)`
- **Docstrings added to files that don't use them** -- matches existing file conventions
- **Single-use variables** -- declared and used once on the next line
- **Defensive checks at internal boundaries** -- null checks, type guards, try/catch on internal functions called by trusted codepaths
- **Redundant type annotations and casts** -- `as Foo` when already inferred
- **Style inconsistencies** -- naming conventions, `let` vs `const`, annotation density
- **Dead code** -- attributes set but never read, variables assigned but unused

## What It Preserves

- New features, functions, and imports
- Comments explaining *why* (business logic, edge cases, workarounds)
- Security-rationale comments (timing attacks, CSRF, sanitization)
- Defensive code at real system boundaries (API endpoints, user input, external I/O)
- Helper functions used from multiple call sites

**When in doubt, deslop leaves it in.** Under-removal is safer than over-removal.

## How It Works

Deslop checks diffs in priority order:

1. Staged changes (`git diff --cached`)
2. Unstaged changes (`git diff`)
3. Branch diff (`git diff main..HEAD`)

Before editing, it reads the full file to understand the existing style -- comment density, docstring usage, error handling patterns, naming conventions. The existing code is the style guide.

## Installation

Clone into your agent's skills directory:

**Claude Code:**

```bash
git clone https://github.com/chrisliu298/deslop.git ~/.claude/skills/deslop
```

**Codex:**

```bash
git clone https://github.com/chrisliu298/deslop.git ~/.codex/skills/deslop
```

## Credits

Based on the original [deslop prompt](https://github.com/lucasb-eyer/dotfiles/blob/master/_codex/prompts/deslop.md) by [@lucasb-eyer](https://github.com/lucasb-eyer).
