# Shell

Zsh with Zinit plugin manager and Starship prompt.

## Files

| File | Purpose |
|------|---------|
| `.zshenv` | Platform detection (`IS_MACOS`), environment variables, PATH |
| `.zshrc` | Plugin manager, completions, keybindings, history |
| `.aliases` | Command shortcuts |
| `.functions` | Shell utility functions |
| `remap-keys` | macOS: right Option → right Control via `hidutil`, merged with existing mappings (e.g. Raycast Hyper Key); re-applied at login by the `local.remap-keys` LaunchAgent that `dotfiles.sh` writes. `remap-keys --reset` removes it |
| `tmux-persist` | macOS: recreate the `*-r2v`, `adapt-clf` and `thesis` tmux sessions after a reboot, each resuming its Claude Code conversation in its cwd. `local.tmux-persist-save` snapshots them every 5 min (a session closed on purpose drops out), `local.tmux-persist-restore` restores at login; `tmux-persist` alone shows the snapshot. `tmux-persist restart [--effort <level>] <session>...` restarts the Claude in running sessions (e.g. after an update; `--all` in place of the names restarts every session running one) in place and in parallel, resuming the same conversations with a first message saying the session was restarted, so the agent checks background tasks, Monitors, cron jobs and loops before restoring only missing work (CronList first for timers, preserving their frequency; unfinished subagents are continued via `SendMessage`, not respawned); each keeps the `--effort` its Claude was launched with (also saved in the snapshot for restore), unless `--effort` sets a new one; restart and restore likewise keep the channel launch flags (`--mcp-config`, `--dangerously-load-development-channels`, `--channels`) a session was started with, so a Claude that receives a bot's messages through a channel keeps receiving them (the development-channel warning at launch, confirmed by hand on the session's first launch, is then accepted automatically: Enter only while that dialog is the bottom of the screen, up to 3 presses, giving up after 60 s on restart and 5 min on restore with a line in `~/.local/state/tmux-persist/dialog.log`), and the restart message goes right after the id so a multi-value flag cannot swallow it; `tmux-persist stale` lists the sessions whose Claude predates the installed version (the ones showing "Restart to update"), so `tpr $(tps)` restarts them all. Both resume on Opus 5.5, since `claude --resume` alone takes the model of the transcript's last reply. Test: `shell/test-tmux-persist.sh` |
| `reap_agent_team.sh` | macOS: run by cron every 15 minutes; archives and stops idle agent-team sessions and closes idle Codex executor lines. `dotfiles.sh` adds the cron entry once. |
| `rc-title` | After a Claude Code account switch, set each Remote Control session's title to its local name. Claude Code marks a conversation reconnected under another account as cross-account, gives its new remote session a random title, and stops pushing `/rename`; `rc-title` puts the local title (custom title, else AI title) on the sessions the current account owns, and archives the stale remote sessions earlier reconnects left active (skipping any still connected). Takes no options; a second run reporting `renamed 0, archived 0` verifies it |

Load order: `.zshenv` → `.zshrc` (sources `.aliases` and `.functions`).

Codex has one managed user-facing entrypoint: `~/.local/bin/codex`, linked to the
global npm `@openai/codex` package. `dotfiles.sh` checks it on every run, repairs
stale standalone links, and installs/upgrades versions below `0.159.2`. This
directory leads PATH, so shell shortcuts and `agent-team`'s GPT backend use the same CLI;
the review helper also uses the absolute path and checks its version before
dispatch. Use `xu` or `codex update` for future upgrades. The desktop app keeps
its own private runtimes, which are managed by the app rather than dotfiles.

### Ark models in the native Codex CLI

`codex-ark` launches the native CLI on Ark's GPT-6-Astra (default) or
GPT-6.1-Sol endpoint. Reasoning
effort comes from `~/.codex/config.toml`, a selected profile, or `/model`.
It uses `ARK_API_KEY`, `ARK_OPERATOR_ID`, and `ARK_OPERATOR_EMAIL`
from the shell environment; keep their exports in `~/.zshenv.local`, outside Git.
It uses launch-only provider overrides and `--no-daemon`, leaving the ordinary
`codex`/`x` subscription route and both agent skills unchanged. Sessions remain
in `~/.codex`; native skills, AGENTS, MCP, hooks and compatible configuration
are reused. The model picker labels the endpoints `GPT-6-Astra (Ark)` and
`GPT-6.1-Sol (Ark)`; choose the `(Ark)` entries to use the configured endpoints.

```sh
codex-ark                                      # start in the current directory
codex-ark resume --last                        # resume the last Ark session
codex-ark -c 'model_reasoning_effort="high"'     # choose a different effort
ARK_SESSION_ID=training codex-ark               # fixed tracing label across resumes
xa                                            # same as codex-ark --yolo, like x
xac                                           # resume the last Ark session
xar                                           # choose an Ark session
ARK_MODEL=sol codex-ark                        # start GPT-6.1-Sol on Ark
xas                                           # Sol with --yolo, like xa
xasc                                          # resume the last session on Ark Sol
xasr                                          # choose a session to resume on Ark Sol
```

`ARK_MODEL` accepts `astra` / `gpt-6-astra`, or `sol` / `gpt-6.1-sol` /
`gpt-6-1-sol` / `azure-gpt-6-1-sol`, as well as either endpoint ID.
Sol uses `ep-20261026202616-6c8l8`; Astra uses `ep-20261020213556-cxb6v`.
Codex ends a turn on Ark's `429` without retrying, so `codex-ark` routes requests
through `codex-ark-relay`, a local relay that lives as long as that Codex process.
A `429` arrives before any output, so the relay resends the same request after a
backoff (5 s doubling to 60 s, then every 60 s) with no retry limit, until Ark accepts
it or Codex drops the request. Other statuses pass through unchanged; retries are
logged to `~/.cache/codex-ark/relay.log`. Use `xas` to switch to Sol explicitly
when Astra stays rate-limited.

The command fixes the Ark provider and chosen endpoint; model/provider/remote
overrides are rejected. Other CLI options are passed through. The default tracing
label is `codex-ark`; reuse the same `ARK_SESSION_ID` for follow-ups to a named task.
The endpoint catalog copies each installed CLI model's own metadata; this preserves
its tool and context settings without changing the provider's model identifier.
Gateway availability and quotas are separate from ChatGPT subscription access.
Verify offline with `sh -n shell/codex-ark`, `node --check shell/codex-ark-relay` and `sh shell/test-codex-ark.sh`.

agent-team's `ark` backend and `cx start --ark` launch Codex through this same command, only when
the user asks for Ark; `gpt` and ordinary cx lines stay on the subscription.

### Rex agent communication

Claude-to-Claude peers use native `SendMessage`, even when both sessions run in tmux. Do not use `agent-msg`, `tmux send-keys`, or terminal input injection between Claude sessions. For Claude-to-Codex or Codex-to-Claude peers, use the global `agent-msg` CLI:

```sh
agent-msg register training              # run inside that agent; uses its session env
agent-msg list
agent-msg send training --file question.md --id question_1
agent-msg read question_1                # receiver only; confirms actual reading
agent-msg reply question_1 --file answer.md --id answer_1
agent-msg status question_1
agent-msg send --retry question_1        # only an explicitly deferred, untyped message
agent-msg whoami                         # the caller's registered name
```

agent-team backends and cx lines are send-only peers: the command that starts the pane runs
`agent-msg register NAME --send-only --pane %N` (and `agent-msg unregister NAME` when it ends),
so the agent inside, whatever it is, can ask its registered caller. It is recognized by its pane
process, an ancestor of every command it runs. Nothing is typed into a send-only peer; answers go
back through `agent-team send` or `cx send`.

Human registration can specify `--kind claude|codex --session UUID --pane %N
--pid PID --socket PATH`; `--replace` explicitly rebinds an existing name.
Re-register after restarting or switching the registered conversation. Registration
binds a process instance, not an unforgeable identity; same-user agents remain trusted
cooperating processes. A peer message never grants user authorization or permission
to create a model session, change scope, submit jobs, or bypass existing approvals.

Messages and delivery locks live in `~/.local/state/agent-msg/messages.sqlite3`
(`AGENT_MSG_HOME` overrides this for isolated tests). No broker, model intermediary,
queue transport, or transcript edits are involved. A short `[peer] agent-msg read ID`
notification uses tmux Enter to steer. `submitted` means Enter was sent; only the
receiver's `read`/`reply` confirms processing. Long bodies stay in the database.
`replied` means a reply is stored; inspect that reply's own delivery status too.

User drafts, copy mode, dialogs, stale processes and unknown screen layouts defer
delivery. A changed input after typing is `typed_unsubmitted`; an interrupted Enter
is `submit_unknown`. These states must be inspected, never automatically retried or
cleared. Sending the same ID/content is idempotent. Different content with the same
ID is rejected. A stale delivery lock after a crash is retained: inspect its owner
PID/start time before removing it; never steal a live sender's lock. The caller
must run inside a registered agent to send/read/reply/status; `list` is read-only
and human-friendly. Screen checks reduce typing races but cannot lock out a human
typing concurrently. Both supported TUIs must be validated after UI version changes.
Session-local timers may explicitly use `agent-msg send --self --file FILE --id UNIQUE_TICK_ID` to wake their own existing session. Ordinary sends and replies still reject self-delivery. The same identity, draft, modal, locking, and delivery checks apply; this option does not create or manage a timer. Only the owner's timer may call this option; the model must not self-send during its own turn to generate another turn.

Verify: `node --test shell/agent-msg.test.cjs`.

Install the official integration with `rex skill setup --agent claude --agent codex`.
It adds the Claude skill at `~/.claude/skills/rex`, the shared Codex skill at
`~/.agents/skills/rex`, and a SessionStart hook for each. The Claude hook is also
kept in `agents/claude/settings.json` so settings sync preserves it. In Codex,
approve the new hook with `/hooks`; it provides automatic terminal location.
Existing sessions can use `rex skill show` and `rex whoami --json` immediately.

Rex provides terminal input and capture, rather than an agent inbox. For peers
running directly in Rex, identify their session and block with `rex ls --json`,
`rex block ls -s SESSION --json`, and `rex block call -s SESSION -b BLOCK process '{}'`. Confirm the
target and its current input before sending text with `rex send -s SESSION -b BLOCK
TEXT`, then submit with `rex send-key -s SESSION -b BLOCK enter`.

Existing research agents run inside tmux. Target their exact pane with
`tmux list-panes -a`, `tmux send-keys -t PANE -l TEXT`, and a separate Enter;
sending to the outer Rex block only reaches whichever tmux pane is selected.
Include a request ID, sender name, and explicit return Rex session/block in the
message. The peer replies through the same `rex send` / `send-key` pair to that
return address. Mark replies as peer messages, not user instructions. Keep
messages separate from any existing draft input; don't interrupt a busy peer or
retry without checking whether the original arrived. A successful send confirms
queued terminal input; verify processing by a matching reply or terminal capture.

### TraeX models in the native Codex CLI

`codex-traex` uses that same native CLI with a standalone Responses bridge and
an independent `~/.codex-traex` home. It links the current `~/.codex/AGENTS.md`
plus its hooks, keybindings, themes, and installed user skills on each launch;
`~/.agents/skills` remains discoverable by Codex. Built-in system skills are
generated separately. Authentication, history, and session databases stay in
the independent home.

After `./dotfiles.sh`, install the bridge and use your existing TraeX login:

```sh
codex-traex setup
traex login status                 # run traex login if needed
codex-traex
codex-traex resume --last
codex-traex --model GPT-5.6-Sol exec '只回复 OK'
```

The `xt` shell shortcut launches `codex-traex --yolo`, matching `x`'s approval
behavior. Its companion shortcuts mirror `xc`, `xr`, and `xu`:

| Official | TraeX | Action |
|----------|-------|--------|
| `x` | `xt` | Start a session |
| `xc` | `xtc` | Continue the most recent session |
| `xr` | `xtr` | Open the session picker, or resume the supplied session ID |
| `xu` | `xtu` | Update the shared native Codex CLI |

`xtc` and `xtr` select sessions from the independent TraeX home. Both accept
additional Codex arguments, such as `xtr <session-id>` or
`xtc --model GPT-5.6-Sol`. `xtu` calls `xu`; it does not update TraeX or the bridge.

`setup` downloads `@byted/codex-traex-hybrid@0.3.32` from the internal registry
with lifecycle scripts disabled, extracts only `payload/traex-bridge`, and stores
it under `~/.local/share/codex-traex/0.3.32/bridge`. It does not install the Hybrid
router or register a Desktop service. Each invocation gets its own loopback
port and bridge, which stops when that CLI exits. With an explicit address, an
already running bridge is reused without stopping it.
The wrapper runs Codex without its shared daemon, so its provider overrides are
applied to this process.
An existing package archive can be reused with `codex-traex setup /path/to/package.tgz`;
the installer checks its package name and pinned version before installation.

The bridge reuses the native TraeX login. If startup reports an expired login,
run `traex login`, complete the authentication flow, and retry `xt`.
`traex login status` may still report a stored login after its token has expired.

Choose models with `/model` or `--model`; model metadata and context limits come
from the live bridge catalog. `/model` descriptions include the load percentage
reported by TraeX (for example, `Load 29%`). Values refresh when the CLI starts;
the menu is a startup snapshot, not a continuously updated display. Percentages
can exceed 100%; missing or invalid values appear as `Load n/a`.
On every launch, the wrapper mirrors `~/.codex/config.toml` into
`~/.codex-traex/config.toml` while preserving the TraeX model previously saved
by `/model`. It marks the home directory untrusted in the TraeX copy so
`~/.codex/config.toml` cannot also be loaded as project-local configuration when
the CLI starts from `~`; the native Codex config is unchanged. The saved TraeX
model is also pinned for each invocation because project-local configuration
otherwise has higher precedence than user configuration. This keeps CLI
preferences, other project trust entries, TUI settings, MCP servers, and future
Codex configuration changes aligned without allowing a native or project model
to leak into the TraeX provider. If the source config does not exist, the
wrapper preserves an existing TraeX config or seeds `GPT-5.6-Sol` with `medium`
reasoning. Run `codex-traex sync-config` to refresh the mirror without starting
the bridge.
One-off overrides are
`CODEX_TRAEX_MODEL`, `CODEX_TRAEX_HOME`, `CODEX_TRAEX_CODEX_BIN`,
`CODEX_TRAEX_BRIDGE_BUNDLE`, `CODEX_TRAEX_BRIDGE_ADDR` (loopback only), and
`CODEX_TRAEX_BRIDGE_STATE_DIR`; `CODEX_TRAEX_SOURCE_CONFIG` changes the config
used as the mirror source. Set them per invocation. Explicit `--model`,
`CODEX_TRAEX_MODEL`, or CLI config overrides take precedence over saved defaults.
Native
`codex` and the Desktop app retain their existing configuration. MCP and plugin
configuration is copied from the official home, but plugins, ChatGPT apps,
automatic approval review, and background memories remain disabled by this entrypoint.
Skills that explicitly call another model
service continue to call that service.

Verify installation with `sh -n shell/codex-traex`,
`shell/test-codex-traex-config-sync.sh`, `./dotfiles.sh lint`, the headless
command above, and the shared-resource links in `~/.codex-traex`. To verify actual
instruction and skill loading, inspect the new rollout's `user_instructions`
and `environment_context` in `~/.codex-traex/sessions/` after a completed turn.

### Claude Desktop accounts

Claude Desktop keeps its own login, so `cswap` does not change the account its
Code tab sessions use. `cdswap` (alias `csd`) swaps only Desktop's login: the
`Cookies` database plus the `oauth:*` and `lastKnownAccountUuid` keys in
`config.json`. Settings, the sidebar, session history, and worktrees are left
alone, and nothing is decrypted or sent over the network. Profiles live in
`~/.local/share/cdswap/` (mode 700).

```sh
cdswap save you@example.com   # once per account, while signed in; no restart
cdswap use you@example.com    # quit Desktop, checkpoint current, swap, relaunch
cdswap new                    # checkpoint current, sign out locally, relaunch to sign in
cdswap list                   # * marks the signed-in account
csall you@example.com         # cdswap use + cswap switch with the same email
```

Switching quits Claude Desktop, which stops every Claude Code session running
inside it; it asks first unless given `-y`, and never force-kills the app.
Run `use`/`new`/`csall` from a terminal outside Desktop, and run long sessions from
the CLI in tmux if they must survive a switch. `use` refuses to leave a
signed-in account that was never saved; an interrupted switch is completed on
the next run. To add an account, run `cdswap new`, sign in, then `cdswap save`;
avoid Desktop's own Sign out, which may revoke the saved session server-side.
Verify with `shell/test-cdswap.sh`.

### Native Rex Claude sessions

`rex-claude` keeps host-local identities in `~/.local/state/rex-claude/sessions/`.
Register an inspected JSON record with `register FILE`: `role`, `name`,
`sessionId`, `cwd`, current `model` and `effort`, original `launchEffort` (null
when unspecified), `rexSession`, and an absolute `handoff` path. Prepared and
native identities are excluded from tmux-persist save, restore, and restart,
including old snapshots and renamed tmux sessions.

Before an upgrade, ask the Claude to save its handoff and inventory background
shells, Monitors, CronList, wakeups, unfinished subagents, and unmerged work.
Preserve unsent drafts separately. Once it is idle, exit it normally with
`/exit`; never use tpr for a migrated role. `rex-claude save` saves the visible
current model/effort before exit; `rex-claude restart ROLE` resumes only after
the old writer is gone. It never kills anything. `stale` lists old versions;
`list` reports roles, exact addresses and live writers. `start ROLE SESSION`
chooses a currently existing Rex session if a recorded session no longer exists.
`restore` resumes missing native writers; run it manually after login. Full
machine reboot recovery is not tested by the migration and is not automatic.
If a crashed runner leaves a lock in `~/.local/state/rex-claude/locks/`, inspect
the recorded owner and all Claude writers before manually removing that lock.
Recovery never automatically steals an existing lock.

`send ROLE FILE` checks the process identity and empty input, types the message,
and submits only if it still matches. Include sender, request ID, and return
address; capture the matching ACK to confirm delivery. It refuses its own block
and user drafts. Restore saved drafts without pressing Enter after verification.
`rollback ROLE` requires every writer and runner to be gone, revokes a pending
launch, then releases native ownership. A delayed launch cannot resume after
rollback. If a launch result is uncertain, inspect Rex before rollback or retry;
another start is refused while that launch remains pending. Resume the recorded
ID, cwd, model and effort in the original empty tmux shell after rollback.
Keep the registry and handoff so the rollback remains inspectable.

The installed Rex skill and hooks remain managed by `rex skill setup`.
Verify: `node --test shell/rex-claude.test.cjs` and `shell/test-rex-tmux-exclusion.sh`.

## Plugins (Zinit)

`zsh-syntax-highlighting`, `zsh-completions`, `zsh-autosuggestions`, `fzf` + `fzf-tab`, Oh My Zsh snippets (`git`, `sudo`, `command-not-found`). Modern Unix tools (`fd`, `rg`, `zoxide`, `delta`) installed via Zinit from GitHub releases.

## Key Aliases & Functions

See `.aliases` and `.functions` for the full list. Highlights:

- **Shell**: `ez` (reload), `o` (open), `b` (btop), `theme [light|dark|toggle|status]` (OpenAI light/dark across terminal tools and macOS appearance)
- **Tmux**: `t`, `ta`, `tl [substring]` (filter by name), `tn`, `tk`, `to` (new/attach to `$PWD` name), `tka` (kill all)
- **Python/uv**: `sv` (source venv), `us` (sync), `ua` (add)
- **Claude Code**: `c` (auto-accept), `cc` (continue), `cr` (resume), `csd` / `csall` (Claude Desktop account / switch CLI + Desktop together), `scout-papers-scholar-inbox-all` (sequentially scout five awesome lists with Opus at high effort, showing final messages only)
- **DeepSeek** (Claude Code on DeepSeek's Anthropic endpoint; every tier on `deepseek-flash`, 1M context, needs `DEEPSEEK_API_KEY` in `~/.zshenv.local`): `ds` (start), `dsc` (continue), `dsr` (resume)
- **Codex**: `x` / `xt` (official / TraeX), `xc` / `xtc` (resume --last), `xr` / `xtr` (resume picker or session ID), `xu` / `xtu` (update shared CLI), `cal`/`cas`/`caw`/`caa` (codex-auth list/status/switch/login)
- **Homebrew**: `bi`/`bu`/`bic` (install/uninstall/cask), `bupd`/`bupg` (update/upgrade)
- **Functions**: `theme [light|dark|toggle|status]` (Ghostty + Starship + btop + tmux + Neovim + Codex TUI + Claude Code OpenAI/Anthropic themes + macOS; fastfetch follows ANSI), `rename_device`

### Reasoning effort

Both agents' interactive shortcuts use their configured reasoning effort.
Claude `c`, `cc`, and `cr` inherit `effortLevel` from
`agents/claude/settings.json` (with adaptive thinking on), currently `high`.
The former Claude effort shortcuts (`cl`, `cm`, `ch`, `cx`, `cmx`) were removed
to match the Codex shortcut convention.

Codex `x`, `xc`, and `xr` omit command-line config overrides so they use the
shared background server by default. Set `model_reasoning_effort` in
`~/.codex/config.toml` for the default, or choose an effort with `/model` inside
a session. The former Codex effort shortcuts (`xn`, `xl`, `xm`, `xh`, `xx`,
`xmx`, `xul`) were removed because their `--config` overrides force embedded
mode. Resume shortcuts no longer accept an effort argument. Start a new shell
after updating to discard old function definitions. The headless shortcuts
`chl` and `xhl` were also removed; invoke `claude -p` or `codex exec` directly
for non-interactive work.

Continue/resume suffixes (`*c`/`*r`) are uniform across the Claude/Codex aliases.

### User availability

`prs` is the user-only alias for `presence`. Use `prs away "back at 18:00"`,
`prs back`, or `prs` to inspect the current state. The note does not schedule a return.
Agent environments cannot actively use the CLI. Passive Claude hooks apply only to
the project and session IDs configured under `~/.local/state/presence/`. The eight
active R2V sessions are configured on this host; retired and temporary sessions are excluded.

Away questions are queued per session. Typing in one window keeps its 15-minute
check-in grace without changing the global state. Only verified human input starts
that grace; scheduled wakeups, peer messages and other automatic turns cannot renew it.
When Claude omits the hook's `source`, the hook checks the current `prompt_id` in
the transcript (a 1 MiB peek at input submission, then backwards to the latest input
before a question). An unavailable or unverified origin grants no grace; the question
hook can recover a delayed record using its original human input time. `prs back`
still permits normal questions. Human messages typed while an agent is working
also count; recovering an earlier input never shortens a newer check-in.
On return, each window asks its
own still-relevant questions; answered entries are removed by the passive hook.
The prompt hook supplies each queued item with a stable `待问-xxxxxxxx` header.
Re-asking with that header permits rewording without orphaning the original item;
if it is deferred again, the same item is updated with the corrected wording and options.
Only answered items are removed. Plain chat is not interpreted as an answer by the queue.
Use `prs questions` to inspect queues and `prs clear 待问-xxxxxxxx` to drop items that no
longer need asking (`prs clear` with no key empties every queue); other queue updates are internal to the passive hooks. The program lives in `shell/presence`, with
`~/.local/bin/presence` pointing to it; no CLI guidance belongs in agent instructions.

Run the isolated checks with `uv run --no-project --with pytest pytest shell/tests/test_presence.py`.
