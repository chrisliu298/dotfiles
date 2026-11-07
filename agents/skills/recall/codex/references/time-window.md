## Review a time window

For a request scoped by time rather than topic ("看下今天早上说的事情是不是都落实了",
"what did I ask for yesterday"), list what was said instead of searching. Resolve
the time yourself and state the window you chose (morning: 00:00–12:00 local):

```bash
uv run --quiet --script "$RECALL" timeline --agent codex \
  --since 2026-10-31 --until 2026-10-31T12:00
```

Results are user messages in time order, grouped by session, across all projects;
add `--project`, `--session`, `--source all` or `--roles both` as needed. Peer-session
relays, scheduled prompts and harness notices are dropped; the current session is
included. `messages_omitted` above 0 means raise `--limit`; `truncated` messages need
`show`. Prompts one agent typed into another's session (agent-team, relays) still
appear as user messages: judge from the text and don't report them as the user's asks.
Codex question-tool answers are not recorded, so a scope set that way can be missing.

To check follow-through, extract each concrete ask from the list, then verify each
one against later messages in its session (`search --session`, `show`) **and** live
state (git, files, services): an assistant saying "done" is a claim, not proof. Report
each ask as done, not done or unverified, with its evidence.


Before running the timeline or show commands above, define the shared helper:

```bash
RECALL="$(dirname "$(realpath "${CODEX_HOME:-$HOME/.codex}/skills/recall")")/shared/global_recall.py"
```
