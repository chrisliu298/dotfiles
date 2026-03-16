---
name: publish-skill
description: |
  Publish a local skill from ~/dotfiles/skills/<name>/ to a standalone public GitHub
  repo under chrisliu298/<name>. Handles creating the repo with README and LICENSE,
  updating dotfiles.sh, CLAUDE.md, and skills/README.md, then verifying symlinks.
  Use when the user says "publish skill", "publish <name>", "make <name> a public repo",
  "release skill", or invokes /publish-skill.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Publish Skill

Publish a local skill from `~/dotfiles/skills/<name>/` to a standalone public GitHub repo at `chrisliu298/<name>`, then update the dotfiles repo to reference the upstream source.

## Context

- Skills directory: !`ls ~/dotfiles/skills/`
- GitHub auth: !`gh auth status 2>&1 | head -3`
- Current SKILLS table entries: !`grep -A 30 '^SKILLS=(' ~/dotfiles/dotfiles.sh | head -35`

## Arguments

The skill name is passed as an argument: `/publish-skill <skill-name>`. If no argument is given, ask the user which skill to publish.

## Workflow

### Phase 1: Validate

1. **Check the skill exists** at `~/dotfiles/skills/<name>/SKILL.md`. If not, list available local skills and ask the user to pick one.
2. **Read the SKILL.md** and any files in `references/`, `agents/`, `scripts/`, `assets/` to understand what the skill does.
3. **Check the target doesn't exist** — verify `~/Developer/GitHub/<name>/` does not already exist and `gh repo view chrisliu298/<name>` returns a 404. If the repo already exists, stop and tell the user.
4. **Verify GitHub CLI** — `gh auth status` must succeed.

### Phase 2: Create standalone repo

5. **Copy skill files** to `~/Developer/GitHub/<name>/` using `cp -r`. Copy everything: SKILL.md, references/, agents/, scripts/, assets/, and any other files in the skill directory. Do NOT regenerate files — copy them directly.

6. **Write README.md** — study the skill's SKILL.md thoroughly, then let the skill itself dictate the README's shape. A simple utility might need only a brief explanation and a usage snippet. A multi-agent orchestration skill might warrant an architecture diagram and detailed phase breakdown. A workflow skill might be best explained through a concrete example walkthrough. Do NOT follow a fixed template or rigid set of sections — adapt the structure, tone, depth, and presentation to whatever communicates this particular skill most effectively. Look at a few existing published skill READMEs (e.g., `~/Developer/GitHub/prism/README.md`, `~/Developer/GitHub/relay/README.md`, `~/Developer/GitHub/autoresearch/README.md`) for inspiration but do not replicate their structure.

   **Required elements** (include these somewhere, in whatever form fits):
   - **Opening subtitle** — `**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that <does X>.**` as the first line after the `# Title`
   - **Invocation hint** — tell users how to trigger it (e.g., "Invoke with `/<name>` or ask your agent to '...'")
   - **Installation** — git clone commands for Claude Code (`~/.claude/skills/<name>`) and Codex (`~/.codex/skills/<name>`)
   - **Contributors** — `[@chrisliu298](https://github.com/chrisliu298)` and `**Claude Code**` with a brief note on what Claude contributed (e.g., "protocol design", "implementation and testing"). If Codex was also involved, include it too.

7. **Write LICENSE** — MIT license:

```
MIT License

Copyright (c) 2025 chrisliu298

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.
```

8. **Initialize and push**:

```bash
cd ~/Developer/GitHub/<name>
git init
git add -A
git commit -m "Initial commit"
gh repo create chrisliu298/<name> --public --source . --push
```

### Phase 3: Update dotfiles

All edits happen in `~/dotfiles/`. Read each file before editing.

9. **Remove the local skill directory**:

```bash
rm -rf ~/dotfiles/skills/<name>/
```

10. **Update `dotfiles.sh`** — add an upstream entry to the SKILLS table. Place it alphabetically among the "Upstream shared" entries:

- If the skill works with both agents (most common): `"*|chrisliu298/<name>|claude,codex"`
- If agent-specific with separate SKILL.md files per agent, use two entries like relay does

11. **Update `CLAUDE.md`** — find the skills directory tree under `## Structure` and remove the `<name>/` line from the local skills listing.

12. **Update `skills/README.md`** — find the skill's row in the skill list table and change the Source column from `Local` to `[chrisliu298/<name>](https://github.com/chrisliu298/<name>)`.

13. **Update `~/Developer/GitHub/agent-skills/README.md`** — read the file, then add a row to the "My Skills" table in alphabetical order. Use the format: `| [<name>](https://github.com/chrisliu298/<name>) | <one-line description from SKILL.md> |`. Do NOT commit or push — the user will handle that separately.

14. **Verify** — run `./dotfiles.sh` from `~/dotfiles/` and confirm the skill symlinks are created correctly.

15. **Report** — show the user:
    - The repo URL: `https://github.com/chrisliu298/<name>`
    - A summary of files in the repo
    - The dotfiles changes made
    - Remind them to review and commit the dotfiles changes when ready

## Constraints

- Do NOT commit or push dotfiles changes — just make the edits. The user will commit when ready.
- Do NOT modify the SKILL.md content when copying — the published version should be identical to the local version.
- Do NOT publish skills that have `Local` as their source and are not in `~/dotfiles/skills/` — they must be local skills managed by this dotfiles repo.
- If the skill has sub-dependencies (e.g., references another skill), note this in the README but do not publish the dependency.
- Always use `cp` to copy files, never regenerate from memory.
