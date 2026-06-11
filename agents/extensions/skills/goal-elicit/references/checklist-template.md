# Checklist template (goal-checklist/v1)

For **enumerable, homogeneous** work the executor processes in batches (e.g. a script-parsed
list of files/symbols/endpoints). Written to `.goals/<id>.checklist.json` (legacy artifacts under `.claude/goals/` are still recognized). The
authoritative format and state model live in the goal-drive skill's
`references/artifact-formats.md`; this is the fill-in scaffold.

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

goal-elicit rules:

- **No verification theater, here too.** `done_when` (goal-level) and `acceptance_per_item`
  must each name concrete evidence — a command, file artifact, metric, or observable behavior.
  Reject "looks good". An **executable** checklist needs `acceptance_per_item` (or a per-item
  `acceptance`); without it goal-drive can only verify by state and the goal-level `done_when`.
- **`items` must be non-empty to be executable.** You need not enumerate them yourself — if the
  user has a script that generates the list, set the header fields and leave `items: []`; tell
  the user goal-drive will wait until the items are filled. If you do enumerate, give each a
  **stable, unique `id`** (the executor's idempotency key).
- `state` ∈ `pending | done | blocked`. A `done` item needs non-empty `evidence`; a `blocked`
  item needs its reason in `note`. `commit_policy` defaults to `none`; `repair_budget` to `3`.
- Write the file and **STOP**. goal-drive executes it; goal-elicit does not.
