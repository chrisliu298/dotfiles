---
name: publish-skill
description: |
  Publish a local skill from `~/dotfiles/agents/extensions/skills/<name>/` to `chrisliu298/<name>`,
  then update this dotfiles repo to reference the published source. Use when the user says
  "publish skill", "publish <name>", "make <name> a public skill repo", "release skill",
  or invokes /publish-skill. Do NOT trigger for publishing npm packages or deploying apps.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Publish Skill

Publish a local skill from `~/dotfiles/agents/extensions/skills/<name>/` to a standalone public GitHub repo at `chrisliu298/<name>`, then update the dotfiles repo to reference the upstream source.

## Context

- Skills directory: !`ls ~/dotfiles/agents/extensions/skills/`
- GitHub auth: !`gh auth status 2>&1 | head -3`
- Current SKILLS table entries: !`sed -n '/^SKILLS=(/,/^)/p' ~/dotfiles/dotfiles.sh`

## Arguments

The skill name is passed as an argument: `/publish-skill <skill-name>`. If no argument is given, ask the user which skill to publish.

## Workflow

### Phase 1: Validate

1. **Check the skill exists** at `~/dotfiles/agents/extensions/skills/<name>/SKILL.md`. If not, list available local skills and ask the user to pick one.
2. **Read the SKILL.md** and any files in `references/`, `agents/`, `scripts/`, `assets/` to understand what the skill does.
3. **Check the target doesn't exist** — verify `~/Developer/GitHub/<name>/` does not already exist and `gh repo view chrisliu298/<name>` returns a 404. If the repo already exists, stop and tell the user.
4. **Verify GitHub CLI** — `gh auth status` must succeed.

### Phase 2: Create standalone repo

5. **Copy skill files** to `~/Developer/GitHub/<name>/` using `cp -r`. Copy everything: SKILL.md, references/, agents/, scripts/, assets/, and any other files in the skill directory. Do NOT regenerate files — copy them directly.

6. **Write README.md** — let the skill dictate the README structure. If available, glance at one or two existing published skill READMEs (e.g., `~/Developer/GitHub/prism/README.md`) for tone inspiration, but do not replicate their structure. If these files don't exist locally, skip — the SKILL.md content is sufficient.

   **Include:**
   - The opening subtitle: `**A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://github.com/openai/codex) that <does X>.**`
   - A brief invocation hint
   - Installation commands for Claude Code (`~/.claude/skills/<name>`) and Codex (`~/.codex/skills/<name>`)
   - Contributors: `[@chrisliu298](https://github.com/chrisliu298)` and `**Claude Code**`, plus `**Codex**` if it contributed

7. **Write LICENSE** — standard MIT license text with `Copyright (c) <current-year> chrisliu298`.

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

9. **Update `dotfiles.sh`** — add an upstream entry to the SKILLS table. Place it alphabetically among the "Upstream shared" entries:

- If the skill works with both agents (most common): `"*|chrisliu298/<name>|claude,codex"`
- If agent-specific with separate SKILL.md files per agent, use two entries like relay does

10. **Update `CLAUDE.md`** — if any paths or descriptions under `## Structure` or `## Adding Extensions` reference the skill being published, update them to reflect the removal.

11. **Update `agents/extensions/README.md`** — remove the skill from the "Workflow skills" table, then add it to the "Published skills" table in alphabetical order with Source set to `[chrisliu298/<name>](https://github.com/chrisliu298/<name>)`. Preserve the description and Enhanced marker.

12. **Verify** — run `./dotfiles.sh` from `~/dotfiles/` and confirm the skill symlinks are created correctly.

13. **Remove the local skill directory** — only after verification succeeds and `gh repo view chrisliu298/<name>` confirms the repo is accessible:

```bash
gh repo view chrisliu298/<name> --json url -q .url  # confirm repo exists
rm -rf ~/dotfiles/agents/extensions/skills/<name>/
```

14. **Report** — show the user:
    - The repo URL: `https://github.com/chrisliu298/<name>`
    - A summary of files in the repo
    - The dotfiles changes made
    - Remind them to review and commit the dotfiles changes when ready

## Constraints

- Do NOT commit or push dotfiles changes — just make the edits. The user will commit when ready.
- Do NOT modify the SKILL.md content when copying — the published version should be identical to the local version.
- Do NOT publish skills that have `Local` as their source and are not in `~/dotfiles/agents/extensions/skills/` — they must be local skills managed by this dotfiles repo.
- If the skill has sub-dependencies (e.g., references another skill), note this in the README but do not publish the dependency.
- Always use `cp` to copy files, never regenerate from memory.
- If `gh repo create` fails, do NOT proceed to Phase 3. Diagnose the error and report to the user.
