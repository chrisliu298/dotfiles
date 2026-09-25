# Delivery decision smoke test — 2026-09-06

Scope: four simulated first responses using the current global instructions.
One dual-subagent call, effort high, ran Claude and Cursor concurrently; both
completed successfully. Cursor helper pins GPT-5.6 Sol high. The Claude helper
uses the installed relay configuration; its served model identity was not audited.
No real training, file modification, or nested delegation was authorized in the cases.

Acceptance criteria were: (1) enqueue ready authorized training without an optional
GPU gate; (2) reuse unchanged data evidence when only LR changes; (3) answer the
sample-count question and continue implementation; (4) batch related reading into
one dual call, followed by parallel native modification assignments.

| Case | Claude | Cursor |
|---|---|---|
| Ready training | PASS: submit now | PASS: submit now |
| Only LR changed | PASS: reuse data evidence | PASS: reuse data evidence |
| Mid-task question | PASS: answer 1000, continue | PASS: answer 1000, continue |
| Delegation routing | PASS: one dual, then two native edits | PASS: one dual, then two native edits |

Both responses propose zero extra confirmations and zero repeated checks in all
four cases. These counts describe the returned action plans, not observed live tool
calls. First useful actions are retained in the JSON; elapsed time to a real action
was not measured because the cases did not execute actions. Cursor also proposed
an optional GPU canary if it caused no delay or contention; necessity of that
additional experiment was not established by this test.

Limitations: n=1 per peer; shared case context; no baseline, no exact GPT-6 run,
no live queue or tool trace. This confirms these peers can state the intended
choices, not that GPT-6 production behavior or delivery time has improved. Use
real task traces to assess those outcomes; do not turn this smoke test into a
mandatory gate for every ordinary change.
