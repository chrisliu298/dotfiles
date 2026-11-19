# `carbon` and `neon` backends

Both use Cursor Agent (`cursor-agent`) in native Agent mode with automatic `--trust`
for the authorized working directory, and differ only in the model: `carbon`
runs `gemini-4-carbon-<effort>`, `neon` runs `gemini-4-neon-<effort>`, where `<effort>`
is the call's `--effort` (`medium` or `high`); Cursor carries the tier in the model id.
Mode and model flags are not exposed. The calling agent can select either backend directly when the
CLI is installed. Everything below applies to both. Sessions started as `cursor-review-*`
or `gemini-review-*` under the former backend names are `carbon` sessions.

Cursor has full tool permissions: file reads/writes, shell commands, web fetch
and MCP tools. The isolated session configuration clears inherited deny rules
and allows these tools; both launch paths use `--force --sandbox disabled
--approve-mcps`. Global and workspace settings are not edited. Read-only task
scope is an assignment instruction, not a permission sandbox. Reviewers can
inspect the repository directly and run commands; no document bundle is required.
Node.js and jq are required. For a document-only brief, its scratch directory is
a suitable workspace. Existing running sessions keep their startup permissions;
the full-permission launch flags apply when a session is started.

`send` submits the native input and activates steering when offered. It confirms
activation or receipt in the primary transcript, waiting up to 10 seconds. The
supplement is consumed at a safe boundary; an in-flight action may finish first.
`confirmed` therefore does not mean the supplement has joined the turn: Cursor
marks it `· steering` until then, and during tool-free text generation the next
boundary is the end of that output. The footer's `enter interrupt and send`
discards the in-progress output, so it is not steering. If the active turn ends
at arrival, the supplement can become a follow-up in the same chat.
Cursor steers one message at a time; a supplement sent while another is steering
stays queued and returns 124 (unconfirmed), and `wait` steers it once Cursor offers.
Do not automatically resend. Do not manually press extra Enter, which can interrupt
pending steering.

`wait` requires successful explicit `turn_ended` with assistant text in the primary
JSONL transcript, covering the latest message. Partial/malformed snapshots and
old answers do not satisfy it; transcript rewrites are deduplicated. User records
Cursor injects itself (steering continuations, background-task notices) neither
start a new reply nor hide the latest message, so the reply spans them. A turn
ending in error (e.g. `WritableIterable is closed`) fails `wait` with that error
rather than leaving it to time out; any text written before it follows on stderr,
marked unverified. Treat it as possibly incomplete. Transient stream and provider
errors (`WritableIterable is closed`, `Connection stalled`, `Provider Error`) are
first resumed: `wait` sends a continuation and keeps waiting, at most twice per
request, noting each on stderr; only a further failure is reported. A turn that
fails before a steered or queued message joins it is not resumed: if Cursor does
not submit that message as a follow-up within 30 seconds, `wait` fails saying it
was not delivered, so resending it is safe. A turn that ended before the message
joined never counts as its reply. `interrupt`
sends Ctrl-C. Inspect status/pane before relying on cancellation of background work.

On macOS, Cursor uses Keychain for login. `SecItemCopyMatching failed -50` with
exit 139 can mean a restricted command context blocked Keychain. Use the command
runner's narrowly scoped unsandboxed option when available and authorized; do not
change credentials or the pinned model on this evidence alone. Report unavailable
models rather than falling back to Auto.

One-shot mode validates a non-empty successful terminal result. A verified result
preceding `WritableIterable is closed` can be recovered; that error alone does not
upgrade opening text to success.
