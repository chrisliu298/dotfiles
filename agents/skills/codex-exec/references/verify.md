## Verify

Codex's reply is a claim. Before accepting:

1. Run `cx diff NAME`: nothing uncommitted, then read every commit and the full diff since
   the line's base.
2. Rerun the acceptance commands yourself, or recompute the number by an independent route.
3. Check the diff stays within the plan and the repository's rules.

If anything fails, `cx send` the specific failure and what to change, then wait again. When
it passes, carry on with the repository's normal flow (review, merge request, merge), and
close or remove the line as "Closing and resuming" says. Code Codex wrote still goes through the repository's usual review; the
executor line is never a reviewer of its own work.
