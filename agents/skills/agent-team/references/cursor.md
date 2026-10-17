# Cursor backend

Uses Cursor Agent with fixed `gemini-4-argon-high`, native Agent mode, and automatic
`--trust` for the authorized working directory. Mode/model/effort flags are not
exposed. The calling agent can select this backend directly when the CLI is installed.

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
If the active turn ends at arrival, it can become a follow-up in the same chat.
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
marked unverified. Treat it as possibly incomplete. `interrupt`
sends Ctrl-C. Inspect status/pane before relying on cancellation of background work.

On macOS, Cursor uses Keychain for login. `SecItemCopyMatching failed -50` with
exit 139 can mean a restricted command context blocked Keychain. Use the command
runner's narrowly scoped unsandboxed option when available and authorized; do not
change credentials or the pinned model on this evidence alone. Report unavailable
models rather than falling back to Auto.

One-shot mode validates a non-empty successful terminal result. A verified result
preceding `WritableIterable is closed` can be recovered; that error alone does not
upgrade opening text to success.
