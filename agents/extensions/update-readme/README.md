# /update-readme

Update or create README.md for the current repository by analyzing the codebase structure, dependencies, and existing documentation.

## Usage

```
/update-readme
```

## What it does

1. Reads key project files (package.json, pyproject.toml, main source files)
2. If README.md exists, preserves user-written content and updates outdated info
3. Writes/updates README.md following a consistent style

## Style rules

- Numbered sections (`## 1. Installation`, `## 2. Usage`)
- Bold callout after each heading summarizing the section
- Bullet points over paragraphs
- Real examples from the codebase, not generic placeholders
- ASCII diagrams for architecture when clearer than prose
- No badges, shields, or emoji unless already present
