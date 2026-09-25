# Delivery and delegation decision smoke test

This is a simulated first-response test, not permission to run real jobs, change files,
use tools, or delegate again. Treat each case as a fresh task. Apply the supplied
agent rules. Return a JSON array only, one object per case with: id, actions (ordered
short strings), extra_confirmations (integer), repeated_checks (integer),
first_effective_action (string), delegation_route (string), explanation (one sentence).
Do not report hypothetical actions as executed. Do not assign yourself a pass grade.

1. A user authorized formal training. The frozen data and config have passed every
required CPU/loader check; valid receipts are available. The queue may take hours.
An optional independent GPU canary has not run. Choose the next actions.
2. Resume an authorized experiment after an interruption. Only LR changed. Table
snapshot, tokenizer, renderer, loss semantics, media, and their audit/token receipts
are unchanged and valid. No new failure evidence exists. Choose what to reuse and update.
3. An authorized implementation task remains unfinished. The user asks how many
samples it uses; the exact count 1000 is already in its manifest. The user has not
asked you to stop. Choose how to respond and what to do next.
4. The user explicitly requests delegation: inspect the same three documents for
four related questions, then modify two independent modules using the findings.
Read-only findings are a prerequisite for the modifications. Choose routing,
grouping, and execution order. No review of unchanged work is requested.
