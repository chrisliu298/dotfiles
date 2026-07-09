# Weak → strong goals

Whole-goal rewrites for **Phase 4 drafting** — the complement to `question-bank.md` (which teaches
how to *ask*) and `anti-patterns.md` (which names failure *moves*). These show what a finished
artifact should read like once the interview is done: a vague seed turned into a verifiable contract.

**The core move: proof, not effort.** A weak goal names activity that never ends ("keep improving
X", "make it faster"); a strong goal names the *observable state that proves it's done* — a command's
exit code, a metric over a threshold, a search with zero hits, a file that now exists. If the draft
describes what the executor will *do* rather than what must become *true*, rewrite it.

## The shape (maps onto the contract fields)

```
objective   — what must become TRUE (not what to work on).
done_when   — the command / search / metric / observed state that PROVES it → its evidence.
scope_in / scope_out — the area it may touch + the tempting-adjacent action it must NOT.
verification / loop  — how the executor re-checks after each change (prefer an existing check).
rollback / blocked   — how to undo, and when to stop and report instead of forcing a pass.
```

The full schema (`contract-template.md`) adds Gherkin acceptance, `risks`, `observability`,
`durability`, etc. — this shape is the drafting skeleton, not a replacement for it.

## Pairs

Each strong version maps the seed onto the fields above; the annotation names what it fixes.

1. **Bug sweep** — *countable end state.*
   - Weak: `Find all bugs in the auth code.`
   - Strong: `objective:` every test in `test/auth` passes. `done_when:` `npm test -- test/auth`
     exits 0 → its output. `scope_out:` do not touch `src/api` or unrelated tests. `blocked:` report
     any failure you cannot fix, with location + reason. *(Fixes: no finish line → a shrinking list.)*

2. **Optimization** — *threshold metric, not a vibe.*
   - Weak: `Make renderFrame faster.`
   - Strong: `objective:` `renderFrame` is ≥3× faster on `bench/render`. `done_when:` `bench/render`
     reports ≥3.0× vs the baseline commit → the number. `blocked:` if <3× after several attempts,
     report the best result and why. *(Fixes: effort → a measured proof + honest stop.)*

3. **Migration** — *queue + off-limits fence.*
   - Weak: `Move the payment module to the new API.`
   - Strong: `objective:` no call site uses the old API. `done_when:` `rg 'oldPaymentClient' src/`
     returns zero hits **and** `npm test -- payment` exits 0. `scope_out:` do not change shared infra;
     stop and ask before touching it. *(Fixes: unbounded scope → a queue that empties + a fence.)*

4. **Vague UI polish** — *translate direction into checks (never a `done_when`).*
   - Weak: `Make the dashboard look premium.`
   - Strong: Record "premium" as design *guidance*. `done_when:` desktop+mobile screenshots reviewed,
     spacing/type on the token scale, ≤3 visual rounds. `scope_out:` no new component library.
     *(Fixes: an unverifiable taste word → observable checks; see anti-patterns "Vague-direction".)*

5. **External-oracle task** — *name what produces ground truth + one guard.*
   - Weak: `Get the classifier to match the reference labels.`
   - Strong: `done_when:` macro-F1 ≥0.90 on `data/gold.jsonl` → the score. `oracle:` gold set is
     frozen at commit `<sha>`; guard = re-hash it before scoring so a stale/wrong-locale copy can't
     pass. `blocked:` if the oracle looks wrong, stop and report. *(Fixes: trust-the-oracle → provenance + a guard.)*

6. **Load-bearing change** — *invariant, not just pass/fail.*
   - Weak: `Handle every error case in the parser.`
   - Strong: `objective:` malformed input is unrepresentable past the parse boundary (returns a typed
     error, never a partial struct). `done_when:` the fuzz target exits clean **and** no public
     function returns a half-built value. `durability: load_bearing` — acceptance emphasizes the
     invariant + reviewability, not "handle every case". *(Fixes: open-ended effort → a bad-state-unrepresentable invariant.)*

## Two drafting habits

- **Make it queue-shaped when the domain allows.** A finish line that *shrinks a list* — failing
  tests → 0, open issues → 0, `rg` hits → 0, files to migrate → done — is self-evident progress and
  hard to fake. Prefer it in a plain contract's `done_when`; promote to the checklist artifact only
  when the units are real work units, not an artificial count. **Do not force a count on `load_bearing`
  goals** where a shrinking list would reward "touch every file" over preserving the invariant.
- **Lean on existing verification.** Reuse tests, CI, type-checks, lint, or a zero-match `rg` as the
  proof before inventing a custom oracle — an existing check is what lets the goal run unattended and
  still be trusted (and it sidesteps the untrusted-oracle risk in `anti-patterns.md`).

**Longer runs are not better runs.** A tight contract that finishes in a handful of turns beats an
open-ended one that burns hours re-running the suite after every edit — shorter runs drift less and
are easier to trust.
