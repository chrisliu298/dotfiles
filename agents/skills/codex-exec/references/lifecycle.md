## Closing and resuming

Lines outlive your turn and your context, so close or remove each one as its state calls for.
A line belongs to the Claude session that last started, sent to or opened it successfully,
which is where `cx ask` questions go; `cx ls` shows it as OWNER (`me` for you), and `attach`
does not change it. Act only on your own lines or ones the user hands you; a `cx send` or
`cx open` from a restarted session takes a line over.

| Situation | Do |
| --- | --- |
| A turn is running, or someone is attached | leave it; `close` and `rm` refuse (`--force` kills the session mid-turn) |
| The reply is in and you are verifying or sending rework | keep it open |
| Codex is done and you wait on review, CI, a platform job it submitted, or the user | `cx close`; a later `cx send` resumes the same thread with its context |
| Merged, accepted with nothing to merge (a scoring or export run), or dropped, with no known follow-up | `cx rm`; the line can no longer be resumed |
| Your task ends, or you continue after a compaction or restart | `cx ls`; close your idle lines that expect no message soon, and note the closed ones you may resume, with any pending question and job ID, in your handoff |

Remove a line only when nothing is known to come back to it: a merge request in review, an
open follow-up on the same branch, or a platform job whose result may need a fix keeps it
closed instead, so the fix reuses the thread's context. `rm` refuses uncommitted changes and
commits not on origin's default branch; `--unmerged` waives only the latter (after a squash
merge, or to drop committed work), and `--force` waives every check.

