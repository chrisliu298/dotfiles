Write the summary as the minimal state needed to resume the work correctly:

- the current goal, the next step, pending tasks, and the user's authorization scope and prohibitions;
- decisions already made, each with a short reason that can be checked;
- the parameters, data contracts, metric definitions and versions the next steps must keep, one short line
  each, tied to a commit, SHA or snapshot where there is one;
- identifiers: job and run IDs, commits, SHAs, MR numbers, table names, file and document paths;
- the key numbers the next decisions depend on (current best scores, thresholds, fresh results);
- any operation whose outcome is not yet verified (a submitted job, a write, a deletion, a remote command),
  any change of the active model, and the checks to run before continuing;
- open questions and anything waiting on the user.

Point to code, configs, diffs and logs that can be re-read from a fixed version instead of copying large
blocks of them. Do not reconstruct earlier step-by-step reasoning; refer to a record file for any history.
