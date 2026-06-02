# Phased design-doc template (goal-plan/v1)

For a **sequential, heterogeneous build** with per-phase acceptance (post pattern 2). Written
to `.claude/goals/<id>.plan.md`. Authoritative format: the goal-drive skill's
`references/artifact-formats.md`; this is the scaffold.

```markdown
---
schema_version: goal-plan/v1
id: 20260601-1430-oauth
status: ready                # draft | ready | running | complete | blocked (goal-elicit writes draft→ready)
commit_policy: none          # none | per_unit
repair_budget: 3
authority: { allow_paths: ["src/**","tests/**"], allow_commands: ["pytest","curl","jq"], stop_for: [deploy, db_migration, secrets, network_send] }
done_when: all phases state=done   # optional; default = all phases done
---

# <title> — design

## Objective / Scope / Constraints
<design prose, co-written with the user — the executor treats this as binding invariants>

## Phases

### Phase 1 — Token endpoint  [state: pending]
**Does:** <what changes>
**Acceptance:** `curl -s localhost/oauth/token -d @client.json | jq -e .jwt`   # command or Given/When/Then
**Evidence:** <null until done; command + result summary or observed artifact>
**Blocked:** <null unless blocked; reason + failed verification>
**Commit:** oauth: token endpoint + JWT issuance      # used only if commit_policy=per_unit

### Phase 2 — Middleware  [state: pending]
**Does:** ...
**Acceptance:** Given a request without a token / When it hits a protected route / Then 401
**Evidence:**
**Blocked:**
**Commit:** oauth: auth middleware
```

goal-elicit rules:

- Each phase's **Acceptance** must name concrete evidence — the same gate as the contract's
  `done_when`. No "looks good".
- The per-phase **`[state: ...]` markers are the authoritative ledger** — there is no
  `current_phase` pointer. goal-drive runs the first phase whose marker is not `done`.
- **Phases are execution units, not delivery checkpoints.** This reconciles with one-shot
  delivery: the user approves the *plan* once; goal-drive executes the phases without
  per-phase re-approval.
- Co-write the design prose with the user (the contract interview produces it), then split
  into phases together. Write the file and **STOP**. [[goal-drive]] executes it.
