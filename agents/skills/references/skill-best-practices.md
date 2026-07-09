# Skill Best Practices

> Source: https://x.com/trq212/status/2033949937936085378 (Anthropic internal learnings)

## Key Principles

- **Skills are folders, not files.** Use the folder for progressive disclosure — reference snippets, helper scripts, templates, examples. The entire file system is context engineering.
- **Focus on what Claude doesn't know.** Push Claude out of its normal way of thinking. Don't restate what it already knows about coding.
- **Gotchas are the highest-signal content.** Build them from real failure points. Update over time as Claude hits new edge cases.
- **Give flexibility, not rigidity.** Provide information Claude needs but let it adapt to the situation. Avoid being too specific in instructions.
- **The description is a trigger, not a summary.** It's scanned to decide "is there a skill for this request?" Write it as when-to-trigger conditions.

## Skill Categories

| Category | Purpose | Examples |
|----------|---------|---------|
| **Knowledge** | Explain how to use a library, CLI, or SDK correctly | billing-lib, internal-platform-cli, frontend-design |
| **Verification** | Test or verify code is working (often paired with playwright, tmux) | signup-flow-driver, checkout-verifier, tmux-cli-driver |
| **Data & Monitoring** | Connect to data/monitoring stacks | funnel-query, cohort-compare, grafana |
| **Workflow Automation** | Automate repetitive workflows into one command | standup-post, create-ticket, weekly-recap |
| **Scaffolding** | Generate framework boilerplate | new-workflow, new-migration, create-app |
| **Code Quality** | Enforce code quality, review code | adversarial-review, code-style, testing-practices |
| **DevOps** | Fetch, push, deploy code | babysit-pr, deploy-service, cherry-pick-prod |
| **Investigation** | Symptom-to-diagnosis structured reports | service-debugging, oncall-runner, log-correlator |
| **Maintenance** | Routine maintenance with guardrails | resource-orphans, dependency-management, cost-investigation |

## Progressive Disclosure

- Point to other markdown files (`references/api.md`) for detailed signatures and usage examples
- Include template files in `assets/` for Claude to copy and use
- Have folders of references, scripts, examples that Claude reads at appropriate times
- Tell Claude what files are in your skill so it discovers them when needed

## Persistent State

- Store data in `${CLAUDE_PLUGIN_DATA}` (stable across upgrades), not in the skill directory
- Formats: append-only text logs, JSON files, or SQLite databases
- Example: standup-post keeps a `standups.log` so Claude sees what changed since yesterday

## Helper Scripts

- Give Claude composable scripts and libraries so it spends turns on composition, not reconstructing boilerplate
- Example: data science skill with helper functions to fetch from event sources — Claude generates scripts on the fly to compose them

## Session-Scoped Hooks

- Skills can register hooks that activate only when invoked and last for the session
- Use for opinionated hooks that shouldn't run all the time
- Examples: `/careful` (blocks destructive commands via PreToolUse), `/freeze` (blocks edits outside a specific directory)

## Distribution

- **Small teams**: Check skills into repo under `.claude/skills/`
- **At scale**: Internal plugin marketplace — let teams decide which to install
- **Organic curation**: Sandbox folder in GitHub, share via Slack, move to marketplace once it has traction
- **Dependencies**: Reference other skills by name — the model invokes them if installed

## Measuring Skill Quality

- Use a PreToolUse hook to log skill usage
- Find skills that are popular or undertriggering compared to expectations
