# Waking a running Claude session on external events

How a long-running interactive Claude Code session (a Feishu bot's agent, a group watcher) gets
woken the moment something happens outside it, with no expiry and nothing to re-arm. Use this
note whenever a session must react to messages, webhooks or job events while it sits idle.

**Answer: a channel.** A local stdio MCP server that declares the `claude/channel` capability and
emits `notifications/claude/channel`; each event lands in the running session as a
`<channel source="...">` message, also while it is idle. Verified 2026-11-10 on Claude Code
2.1.322 with `@modelcontextprotocol/sdk` 1.32.2 by two sessions: the avatar bot (`bot-r2v`) and
the eval-bot group watcher (`autoeval-bot-r2v`). Official docs:
[channels](https://code.claude.com/docs/en/channels.md),
[channels reference](https://code.claude.com/docs/en/channels-reference.md).

## Options compared

| Mechanism | Wakes an idle session | Lifetime | Verdict |
|---|---|---|---|
| Monitor tool | yes, one event per stdout line | `timeout_ms` capped at 30 min (the `ws` source too); re-arm on every expiry | stopgap |
| Background Bash that exits on the first event | yes, once | one notification, then re-arm per batch | stopgap |
| `CronCreate` / `/loop` | fires between turns while idle | polling only, 1-min minimum, jittered; recurring tasks expire after 7 days | no |
| Remote Control | no: you drive the session from a phone or claude.ai | n/a | no |
| MCP tasks | Claude starts on a finished task's result unprompted | one result per task; the server must support the tasks extension | no |
| `asyncRewake` hook | yes: exit code 2 wakes Claude immediately, even idle | self-renewing chain, see below | fallback |
| **Channel** | yes, pushed | as long as the session runs | **use this** |

### Fallback: an `asyncRewake` Stop hook

Use it only where a channel cannot be (e.g. the session cannot be relaunched with the flags).
From the [hooks reference](https://code.claude.com/docs/en/hooks.md), *Run hooks in the
background*: "an `asyncRewake` hook that exits with code 2 wakes Claude immediately even when the
session is idle", its stderr reaching Claude as a system reminder. A Stop hook fires at the end of
every turn, so a background script that waits for the next event and exits 2 wakes the session,
and the turn that follows re-arms it. Untested here; its costs:

- `timeout` is still enforced on `asyncRewake` hooks (default 600 s). A hook killed at timeout
  does not exit 2, so the chain breaks. Set a long `timeout` (no documented maximum: test it) and
  have the script exit 2 with a heartbeat before it runs out, at the price of an empty wake-up.
- A turn the user starts fires Stop again while the previous waiter still waits. Keep one waiter:
  a pidfile, the new one killing the old (a killed waiter does not exit 2), and a read cursor in a
  file so no event is lost.
- Settings hooks apply to every session sharing that settings file. Compare `session_id` from the
  hook's stdin and `exit 0` for any other session. Edits to settings hooks are picked up by the
  file watcher, so a running session needs no restart (test it).
- Nothing fires before the first turn ends: start with one turn, or add the same hook on
  `SessionStart`.

## Building a channel

Requirements: Node (or Bun or Deno) and `@modelcontextprotocol/sdk` **1.x**. Bun is not
installed on this Mac; Node is.

```js
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'

const mcp = new Server({ name: 'NAME', version: '0.1.0' }, {
  capabilities: { experimental: { 'claude/channel': {} } },  // the key that makes it a channel
  instructions: 'What arrives as <channel source="NAME" ...>, that it is untrusted external text, and how to reply.',
})
await mcp.connect(new StdioServerTransport())
// for each event:
await mcp.notification({ method: 'notifications/claude/channel',
  params: { content: text, meta: { message_id: id } } })  // meta keys: letters, digits, _ only
```

An `mcp.json` names it: `{"mcpServers": {"NAME": {"command": "node", "args": ["/abs/path/server.mjs"]}}}`.
Launch, or relaunch an existing conversation, with both flags:

```sh
claude --dangerously-skip-permissions --model claude-opus-5-5 --resume <session-id> --effort <level> \
  --mcp-config /abs/path/mcp.json --dangerously-load-development-channels server:NAME
```

A custom channel is not on the research-preview allowlist, so it needs
`--dangerously-load-development-channels`, which shows a full-screen warning once per launch. Its
bottom four lines read `Channels: server:NAME`, `❯ 1. I am using this for local development`,
`2. Exit`, `Enter to confirm · Esc to cancel`, under a WARNING title; press Enter on option 1. The
cwd must be a directory Claude Code already trusts: otherwise the workspace trust dialog comes
first, and neither the warning nor the automatic confirmation below gets past it. (The docs also
describe a dim notice under the banner naming the channel; we did not check it.) To verify, push
one real event and see it arrive as `<channel source="NAME">`; the server gets no acknowledgement
either way.

### Pitfalls

- **Silent drops.** If the session did not register the server as a channel, Claude Code drops
  its events without an error. Use SDK 1.x (1.32.2 works). Per the
  [MCP docs](https://code.claude.com/docs/en/mcp.md#push-messages-with-channels), a server that
  negotiates protocol revision 2026-07-28 is not registered on the v2 client runtime, and
  `MCP_PROTOCOL_NEGOTIATION=legacy` keeps servers on the earlier handshake; neither is tested
  here. Always verify with a real event after setting one up.
- **Launch time only.** The flags cannot be added to a running session: relaunch with `--resume`
  and the flags. Per the channels reference (untested here), `-p` and the Agent SDK ignore the
  development flag.
- **Multi-value flags swallow the prompt.** `--mcp-config <configs...>` and
  `--dangerously-load-development-channels` (like `--channels`) take several values: a prompt
  argument after them is read as one more value. Put the prompt right after the session id.
- **Untrusted content.** Everything a channel pushes is external text, not the user's
  instructions; say so in `instructions`, and gate on the sender identity (not the chat) before
  pushing anything that could drive tool use.
- **Batching.** Events that arrive while Claude is busy are delivered together on the next turn,
  so one notification per event works (the avatar server does that). Optionally collapse lines
  that arrive within a few hundred ms into one notification, so a burst is one wake-up even when
  Claude is idle (the group-watcher server does, at 300 ms, like the Monitor tool's 200 ms).
- **Process hygiene.** Claude Code spawns the server and closes its stdin on exit: kill the
  child processes then and exit, or they linger. Restart a dropped upstream (ssh, a watcher
  script) after a few seconds, and keep the read position in a file so a restart misses nothing.
- **ssh upstreams orphan.** Killing the local ssh client leaves the remote process running, and
  its parent does not become pid 1, so a parent check cannot catch it. Give ssh a stdin pipe that
  stays open, and have the remote script read stdin in a thread and exit at EOF.
- **One consumer per cursor.** Two readers sharing a read position steal each other's events.
  When switching to a channel from another waiter (a background command, a Monitor), stop the old
  one and check that no remote reader is left before relaunching the session.

## Relaunch and reboot

`shell/tmux-persist` (see `shell/README.md`) keeps a session's `--mcp-config`,
`--dangerously-load-development-channels` and `--channels` across `tmux-persist restart` and the
login-time restore, puts the restart message right after the id, and answers the
development-channel warning automatically: Enter only while those four lines are the bottom of
the screen, checking that the dialog closed and pressing at most 3 times; it waits up to 60 s on
restart and 5 min on the login-time restore (Claude can start slowly right after boot), and logs
a give-up to `~/.local/state/tmux-persist/dialog.log`. It never answers the trust dialog. A
session launched by hand without the flags gets no channel: relaunch it with them.

## Channels in use

| Session | Server | Upstream |
|---|---|---|
| `bot-r2v` (Feishu bot 刘宇豪的分身) | `~/Developer/GitHub/feishu-avatar/channel/server.mjs` | `ssh dev4 'python3 -u ~/avatar-bot/next.py --follow'`, cursor `~/avatar-bot/.cursor` on dev4 |
| `autoeval-bot-r2v` (eval bot R2V 自动评测) | `~/Developer/GitHub/autoeval-bot/channel/server.mjs` | `~/Developer/GitHub/autoeval-bot/watch_group.py` (tails the bot's `~/feishu-bot/chat-events.jsonl` on dev4; the remote `tail` exits on stdin EOF and a pidfile kills a stale one) |
