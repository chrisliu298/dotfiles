# /update-readme

Update or create README.md for the current repository by analyzing codebase structure, dependencies, and existing documentation.

## Usage

```
/update-readme
```

## How It Works

1. Reads key project files (package.json, pyproject.toml, main source files)
2. If README.md exists, preserves user-written content and updates outdated info
3. Writes/updates README.md following a consistent style

## Style Rules

- Flat section headings (`## Section Name`) — no numbering
- Bullet points over paragraphs
- Real examples from the codebase, not generic placeholders
- ASCII diagrams for architecture when clearer than prose
- No badges, shields, or emoji unless already present

## Constraints

- Does not delete user-written sections it cannot regenerate
- Does not add content it cannot verify from the codebase
