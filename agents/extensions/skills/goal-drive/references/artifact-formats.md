# Artifact formats — the goal-drive execution contract

`goal-drive` executes **one artifact per goal**. The artifact *is* the plan *is* the
state — never a separate plan file and a separate state file for the same goal, and never a
companion contract beside a checklist or phased doc. Three shapes are accepted. This file is
the **authoritative contract**: `goal-elicit` writes files that conform to it, and a
**bring-your-own (BYO)** artifact (hand-written or script-generated) is valid as long as it
conforms here.

This is a Design-by-Contract boundary: **preconditions** = `authority`, **postconditions** =
acceptance / `done_when`, **invariants** = scope. goal-drive reasons against the artifact, not
against chat history.

## State model

Every executable **unit** (a checklist item, a phase, or — for a contract — each `done_when`
item) is in exactly one of three states:

| state | meaning |
|---|---|
| `pending` | not yet completed |
| `done` | completed **and** its acceptance verified, with evidence recorded |
| `blocked` | attempted, could not complete within the repair budget; carries a reason |

There is no persisted `in_progress`. State is a **ledger of completed fact, not intent** —
flip to `done` only *after* acceptance verifies. (See `execution-loop.md`.)

**Unit state vs artifact status are different things.** The three states above are *per-unit*.
A markdown artifact also carries a frontmatter `status` describing the *whole artifact's
lifecycle* — `draft | ready | running | complete | blocked`. `goal-elicit` authors a `draft`
that becomes `ready`; `goal-drive` sets `running` on load, `complete` when done, `blocked`
when a unit blocks. (goal-elicit's contract `status` is `draft | ready | blocked` — it has no
runtime states. Do not conflate artifact status with unit state.)

## Where artifacts live

Aligned with `goal-elicit`'s convention (`contract-template.md`):

- **Contract:** `GOAL.md` at the repo root (or `$PWD`), or `.claude/goals/<id>.goal.md` for multiple goals.
- **Checklist:** `.claude/goals/<id>.checklist.json`
- **Phased doc:** `.claude/goals/<id>.plan.md`

`<id>` is `<YYYYMMDD>-<HHMM>-<slug>` (slug ≤ 30 chars), the same id format goal-elicit uses.

## Default authority (when an artifact has no `authority` block)

`authority` is the executor's least-privilege precondition set. When the artifact omits it
(common for a quick BYO checklist), the default is:

- **allow_paths:** the repo working tree (edits there are reversible — two-way-door).
- **allow_commands:** any command **named in the artifact's `acceptance_per_item`, phase
  `Acceptance`, or `done_when`** (so verification can run), plus read-only inspection
  (`git status`/`git diff`, test runners). Nothing else.
- **commit_policy:** `none` (no commits unless the artifact opts in).
- **stop_for (the canonical one-way-door list):**
  `deploy, db_migration, destructive, protected_branch_push, secrets, network_send`.

goal-drive must **announce these assumed defaults in its first status line** when it falls
back to them, so the authority in force is visible. An explicit `authority` block overrides
`allow_paths` / `allow_commands`; its `stop_for` only **adds** to the canonical one-way-door
list above. Those classes always require assent — an artifact cannot remove them.

## Emergent items (scope drift)

When work surfaces outside the artifact's scope, goal-drive records it but does **not**
execute it (MoSCoW "Won't this time" by default). Emergent items are a ledger of deferred
scope, never executable units, unless the user promotes one.

- **Markdown shapes (contract, phased):** an `## Emergent` section at the end of the file,
  one bullet per item: `- [wont] <description>`. The user promotes by changing the label to
  `[should]`/`[must]` and moving it into scope (a new phase, or a `done_when` line).
- **JSON checklist:** a top-level `"emergent": [{ "description": "...", "moscow": "wont" }]`
  array. Promote by moving an entry into `items` with a `state` and acceptance.

---

## Shape A — Contract (`GOAL.md`)

The existing `goal-elicit` contract (see its `contract-template.md`), optionally carrying an
`execution:` block. **No `execution:` block ⇒ elicit-only**, identical to today's behavior.

```yaml
# appended to the existing contract frontmatter; entirely optional
execution:
  work_shape: one_shot          # contracts are ALWAYS one_shot (checklist/phased use their own file)
  commit_policy: none           # none | per_unit  — per_unit AUTHORIZES local commits without asking
  authority:                    # omit ⇒ Default authority above
    allow_paths: ["src/**", "tests/**"]
    allow_commands: ["pytest"]
    stop_for: [deploy, db_migration, destructive, protected_branch_push, secrets, network_send]
```

**Contract execution semantics.** The whole goal is one unit, but its `done_when` checkboxes
are the per-item ledger:

- `- [ ] <criterion> → <evidence>` is `pending`; `- [x] … → <recorded evidence>` is `done`;
  `- [ ] … <!-- blocked: reason -->` is `blocked`.
- goal-drive does the work, then verifies each `done_when` item, checks `[x]` and writes the
  evidence after the arrow as it passes, and marks the contract `done` only when **every** box
  is `[x]`. A box that fails past the repair budget gets the `<!-- blocked: … -->` comment and
  execution stops.

**BYO conformance:** frontmatter with `schema_version` + `id` + `status`, and a `## Done when`
section with at least one item carrying an evidence source. The `execution:` block is optional
(absent ⇒ elicit-only). Other body sections are recommended, not required.

---

## Shape B — Checklist (`.claude/goals/<id>.checklist.json`)

For **enumerable, homogeneous** work processed in batches (e.g. a script-parsed list).

```json
{
  "schema_version": "goal-checklist/v1",
  "id": "20260601-1430-document-exports",
  "objective": "Add a docstring to every exported symbol in lib/",
  "done_when": "every item state=done AND `npm run lint:docs` exits 0",
  "acceptance_per_item": "symbol has a docstring; `npm run lint:docs <file>` passes",
  "batch_size": 10,
  "commit_policy": "none",
  "repair_budget": 3,
  "authority": { "allow_paths": ["lib/**"], "allow_commands": ["npm"], "stop_for": ["destructive", "protected_branch_push"] },
  "items": [
    { "id": "lib/auth.ts#login",  "state": "pending", "evidence": null, "note": "" }
  ],
  "emergent": []
}
```

Rules:
- Each item `id` is **stable and unique** — the idempotency key. Re-running skips items already `state: done`.
- **An executable checklist needs per-item acceptance:** a top-level `acceptance_per_item`
  **or** an `acceptance` field on each item. If neither is present, goal-drive verifies an
  item only by its `state` having been set, and relies on the goal-level `done_when` — state
  this is the weaker mode in the first status line.
- **`items` must be present and non-empty to execute.** goal-drive does **not** generate
  items. If `items` is empty (e.g. a script will fill it later), goal-drive treats the
  checklist as "awaiting items" and stops with that message rather than inventing work.
- `state: done` requires non-empty `evidence`; `state: blocked` requires a reason in `note`.
  `evidence`/`note` are optional only while `pending`. Extra user fields are preserved, never stripped.
- **Goal-completion predicate:** all items `done` AND the `done_when` string verifies. If every
  item is `done` but `done_when` fails, record the failure in `emergent`/a `note` and STOP
  (the goal is blocked) — do not reset items to pending.
- Update items **in place** (patch), never regenerate the file.

**BYO conformance:** `schema_version`, `id`, `done_when`, and a non-empty `items` array whose
entries each have `id` + `state`. `batch_size` defaults to 1, `commit_policy` to none,
`repair_budget` to 3.

---

## Shape C — Phased doc (`.claude/goals/<id>.plan.md`)

For a **sequential, heterogeneous build** with distinct per-phase acceptance.

```markdown
---
schema_version: goal-plan/v1
id: 20260601-1430-oauth
status: ready                # draft | ready | running | complete | blocked
commit_policy: none          # none | per_unit
repair_budget: 3
authority: { allow_paths: ["src/**","tests/**"], allow_commands: ["pytest","curl","jq"], stop_for: [deploy, db_migration, secrets, network_send] }
done_when: all phases state=done   # optional; default = all phases done
---

# <title> — design

## Objective / Scope / Constraints
<design prose — binding invariants the executor must respect>

## Phases

### Phase 1 — Token endpoint  [state: pending]
**Does:** <what changes>
**Acceptance:** `curl -s localhost/oauth/token -d @client.json | jq -e .jwt`   # command or Given/When/Then
**Evidence:** <null until done; command + result summary or observed artifact>
**Blocked:** <null unless blocked; reason + failed verification>
**Commit:** oauth: token endpoint + JWT issuance      # used only if commit_policy=per_unit
```

Rules:
- The per-phase **`[state: ...]` markers are the authoritative ledger.** `goal-drive` selects
  the first phase whose marker is not `done`. There is **no `current_phase` pointer** — deriving
  the next phase from the markers (not a fragile step counter) is what keeps resume idempotent.
- A phase flips to `done` only when its **Acceptance** verifies AND its **Evidence** line is
  non-empty; otherwise `[state: blocked]` with a filled **Blocked:** line, and execution stops.
- Phases are **execution units, not delivery promises** — the plan was approved once; phases are
  not re-approval gates.
- **Goal-completion predicate:** the frontmatter `done_when` (default: all phases `done`). If a
  `done_when` is given, goal-drive verifies it at FINISH after all phases are `done`.

**BYO conformance:** frontmatter with `schema_version` + `id` + `status`, and a `## Phases`
section whose headings each carry a `[state: ...]` marker and an `**Acceptance:**` line.
