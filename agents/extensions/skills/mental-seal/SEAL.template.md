---
id: YYYY-MM-DD-priority-slug   # stable id; supersedes + History entries reference this
status: active            # active | released | superseded | needs_review
scope: project
set_by: user              # who set it — never self-set silently
set_at: YYYY-MM-DD
priority: "<one sentence — the single supreme priority for this task/session>"
purpose: "<why it matters — the intent behind the priority>"
end_state: "<what done looks like, concretely and checkably>"
discharge_when: "<observable condition that releases the seal>"
expires_if: "<condition that makes the seal stale — e.g. the user changes the goal>"
supersedes: null          # id of the prior seal this replaced (its full record is under ## History)
last_recalled: null       # YYYY-MM-DD — stamped ONLY during a reconcile that re-checked the seal, never on a bare recall
---

# THE SEAL — one thing held

## Litany   (recite at set / conflict / discharge — not every turn)
I hold one thing: **<priority>**.
When the path forks, the fork that serves the seal wins — unless the user redirects, and then I follow them. Scope that does not serve the seal waits.
The vow serves the user, not itself — if it ever fights the goal or their explicit instruction, I surface it; I do not obey it blindly.
I keep it until it is verified, released, or deliberately replaced.

## Commander's intent
- Purpose: <purpose>
- End state: <end_state>
- Non-goals: <what this seal explicitly does NOT authorize — the scope fence>

## If-then wards   (the compliance engine — keep these in working memory)
- IF about to plan, edit, run a tool batch, or finalize → THEN ask: does this serve the seal? If not, name the drift before proceeding.
- IF a request or temptation competes with the seal → THEN surface the conflict and ask whether to keep, suspend once, or supersede; never silently override.
- IF the context was resumed or compacted → THEN re-read this file and reconcile it against reality before trusting it.
- IF `discharge_when` is met → THEN release the seal; do not keep polishing.

## History
<!-- Released/superseded seals are archived here, never deleted. On supersede, the active
     frontmatter + body above is replaced by the new seal and the prior seal's full record
     moves here. One entry per past seal:
     - <id> — <released|superseded> <YYYY-MM-DD> — priority: "<one sentence>" — evidence/reason: <what verified it or why it changed> -->

