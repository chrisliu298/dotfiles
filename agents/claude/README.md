# agents/claude — Claude Code agent home

Config for [Claude Code](https://claude.com/claude-code). Everything here targets `~/.claude/`. The global `~/.claude/CLAUDE.md` is a symlink to the shared [`agents/AGENTS.md`](../AGENTS.md).

| Path | Installed as | Notes |
|------|--------------|-------|
| `keybindings.json` | symlink | Custom key and chord bindings. |
| `settings.json` | **merged** by `dotfiles.sh` | Merged onto the live file so keys Claude Code writes (e.g. `/effort`'s `modelSettings`) survive; repo values win and arrays are replaced whole, so a key deleted here must also be deleted from `~/.claude/settings.json`. `~/` is expanded to an absolute path, which Claude Code requires. `theme` is not set here; `shell/theme-apply` owns it (see below). |
| `lang-guard.py` | symlink | Stop and PostToolUse hooks that keep interactive replies in Simplified Chinese: an English final reply is blocked once and rewritten, English narration before a tool call adds a reminder to the context. |
| `computer-use-mcp.sh`, `computer-use-mcp-proxy.mjs`, `computer-use-mcp-smoke.mjs`, `computer-use-mcp-browser-smoke.mjs` | not installed; Claude and Codex MCP registrations point at the same repo path | The shared `codex-computer-use` MCP server — see [Codex Computer Use](#codex-computer-use). Tests: `node --test agents/claude/computer-use-mcp-proxy.test.mjs`. |
| `statusline-command.sh` | symlink | Status line renderer. ANSI *named* colors only, so it follows the terminal palette — see below. |
| `themes/anthropic-{dark,light}.json` | symlinks | Claude themes in Anthropic's brand palette, built on the ANSI variants so code syntax follows the terminal. |
| `themes/openai-{dark,light}.json` | symlinks | Claude themes based on the built-in ANSI variants, with tuned text hierarchy, surfaces, and diff backgrounds. |
| `themes/{anthropic,openai}.json` | generated files | Active "Anthropic (follows theme)" and "OpenAI (follows theme)" entries, replaced by `theme` so running Claude sessions can reload their colors. |

`dotfiles.sh` writes two keys in `~/.claude.json`. It marks Claude Code's scratch root (`/tmp/claude-<uid>`, real path) trusted, so unattended sessions launched in a session scratchpad (agent-team's `claude` and `ds`) don't stall on the workspace trust dialog; trust covers every subdirectory except nested git repositories. It also removes `computer-use` from every project's `enabledMcpServers`, because `codex-computer-use` is the only computer-use tool.

Skills are not here — they are symlinked into `~/.claude/skills/` from `agents/skills/` by the
`SKILLS` table in `dotfiles.sh`.

## Codex Computer Use

`codex-computer-use` is the shared browser and computer-use tool for Claude and Codex. Claude's
built-in `computer-use` server and Claude in Chrome are off: `settings.json` denies their tools
and sets `CLAUDE_CODE_ENABLE_CFC=0`. Codex's native UI plugins and legacy UI MCP servers are
disabled by [`../codex/computer-use-config.mjs`](../codex/computer-use-config.mjs), using Codex's
own config reader/writer; generic `node_repl` remains available for non-UI work. The shared
[`agents/AGENTS.md`](../AGENTS.md) routes both agents to this MCP without automatic UI fallbacks.
It gives both agents (CLI, desktop and SDK hosts)
the computer-use runtime of the ChatGPT app: one `js` tool with a `cua` API for desktop apps
(macOS accessibility) and for the browser through the ChatGPT browser extension, which runs in
Helium. `dotfiles.sh` registers the same launcher at user scope in both agents only on machines
with the ChatGPT app and `~/.codex/computer-use`. It reconciles Codex routing on every run,
including when the repository fingerprint is unchanged. Restart existing sessions after switching;
already-connected tools and MCP processes do not reload automatically.

This is our minimal version based on [amontlabs/lcu](https://github.com/amontlabs/lcu). When a
ChatGPT update or the Computer Use service breaks it, check how lcu handled the problem first.

- **How it runs.** `computer-use-mcp.sh` starts the app's own `@oai/cua-repl` under the app's
  OpenAI-signed Node, the only caller the Computer Use service accepts. Only the `computer`
  surface and the `chrome` (extension) browser backend are on; Codex's in-app browser is not
  used. Each MCP process runs its own server (~100 MB idle, more once used).
- **Same lifecycle in both hosts.** The proxy owns session/turn ids and replaces incoming host
  ids on every tool call, including `js_reset`; shutdown cleans up that same session. A conversation
  turn ending does not end the MCP session. Close task-created tabs when finished; `js_reset`
  preserves them, and process exit provides cleanup. Explicit screenshots are scaled with the same
  coordinate note in both hosts; implicit browser UI screenshot metadata is omitted.
  Codex's `js` output budget is 25,000 tokens, matching its native runtime; Claude's
  `anthropic/maxResultSizeChars` remains 200,000 so first-use/reset documentation stays inline.
- **Verification.** `node --test agents/codex/computer-use-config.test.mjs` checks migration and
  idempotence with the installed Codex parser in an isolated `CODEX_HOME`, without model calls.
  `node agents/claude/computer-use-mcp-browser-smoke.mjs` exercises both host request shapes
  against a temporary local page and the real browser, including input, iframe, reset and exit
  cleanup. It opens temporary test tabs; Helium and the ChatGPT extension must be connected.
- **Over SSH.** `mbp16-computer-use` runs this same script as
  `ssh mbp16 CU_SSH_ALIAS=mbp16 ~/dotfiles/agents/claude/computer-use-mcp.sh`. `CU_SSH_ALIAS` tells
  the model that `js` and its Bash are on different Macs, so the menu bar and Dock fallback has
  to go through `ssh`. It is explicit because `SSH_CONNECTION` is also set when Claude itself
  runs inside an SSH login.
- **Full permission, no prompts.** The proxy grants every app approval for the session
  itself, except 1Password (`DENIED_APPS`), and the browser follows
  `~/.codex/browser/config.toml`, where every approval mode is `never_ask` with full CDP
  access. That file is host-local and shared with Codex, so set it on each machine; the smoke
  check warns when it isn't. Any agent, including one steered by page content, can therefore
  use every other app and the logged-in Helium without asking.
- **`js` is also a shell.** It can import `node:child_process` and `node:fs` and use `fetch`,
  outside Claude's Bash hooks and deny rules. So tightening Bash permissions doesn't constrain
  this server, page content could lead to local commands, and `DENIED_APPS` only prevents
  accidents.
- **Revoking.** Approvals the Codex app stored as "always allow" are shared with Codex and live in
  `~/Library/Group Containers/2DC432GLL2.com.openai.sky.CUAService/Library/Application Support/Software/ComputerUseAppApprovals.json`.
  macOS blocks ordinary shells from that folder (`Operation not permitted`), including `js`.
  Stored approvals may skip the proxy, so check them if a denied app still opens.
- **Proxy.** `computer-use-mcp-proxy.mjs` makes every host behave the same; its header comment
  lists what it does and why.
- **Requirements.** Helium open with the ChatGPT extension connected (its native host
  manifest comes from the Codex app). After a ChatGPT update, restart long-running sessions
  so their servers pick up the new runtime, and run
  `node agents/claude/computer-use-mcp-smoke.mjs`, which drives the real runtime without
  changing anything (unless the refusal is broken, when it may launch 1Password), checks that
  1Password is refused and lists what it could not confirm.

## Status line

`statusline-command.sh` owns its entire output string. It uses ANSI *named* colors only
(`\033[34m` etc.), which the Ghostty palette remaps per mode. Project and
worktree names use blue, branches and additions use green, and deletions use red.
Elapsed time uses cyan, context percentage uses purple, and cost uses gold;
context labels and token counts stay muted so the status line remains scannable.

The default layout has two rows: model/project/git/session details first, then
context/5-hour and 7-day limits/cost/changed lines. It reads Claude Code's
`COLUMNS` and wraps at field boundaries in narrow panes, reserving four columns
for footer spacing. A field wider than the pane wraps within the field without
dropping text. ANSI colors and OSC 8 links do not count toward width and remain
intact across rows; CJK and combining text use Unicode display widths. The
renderer uses `jq` and macOS's bundled Perl (`Unicode::UCD`). Without a valid
`COLUMNS`, it assumes 120 columns.

Two theme families are installed, each with a stable entry that follows the
light/dark mode: `custom:openai` (the default) and `custom:anthropic`. `theme`
copies the matching tracked variants to `~/.claude/themes/anthropic.json` and
`~/.claude/themes/openai.json`; Claude watches the selected file and reloads
changes in running sessions. Pick a family with `/theme`; `theme-apply` keeps
either choice and only sets `custom:openai` when the selection is anything
else. A session opened with an older selection (such as `custom:openai-dark`)
needs one manual `/theme` pick (or a restart) to start following a stable file.

### Anthropic

Both variants take their colors from the design tokens on anthropic.com,
claude.com, and claude.ai: warm slate neutrals for text and surfaces (user
messages sit on slate-800 in dark, slate-150 in light), clay `#d97757` for the
Claude label, spinner, mascot, and usage meter, sky for permission prompts and
inline code, plum for auto-accept and skills, fig for bash mode, mineral for plan
mode, and olive/error red for success and failure. Light mode darkens the accents
(clay to the official `#c6613f` hover shade, sky/plum/fig/mineral/olive to about
5:1 on white) so text stays readable. Selections use peach in light mode and a
dark clay tint in dark mode.

Code syntax still uses Ghostty's ANSI colors through the `*-ansi` bases; a
non-ANSI base would switch Claude to its built-in Monokai/GitHub syntax and fixed
diff backgrounds. Diffs use olive added rows and terracotta removed rows. The four
diff tokens are `ansi256()` indices (dark 58/88/107/167, light 193/217/107/167),
separate from the OpenAI ones, that the Ghostty themes remap, because Claude
limits diff backgrounds to 256 colors inside tmux. The word-highlight tokens also
color the `+N`/`-N` counts.

### OpenAI

Both variants inherit Claude's ANSI syntax palette, with green added rows and
red removed rows. Neutral text and surfaces are overridden to keep the hierarchy clear. The
Claude mascot uses its built-in coral, `rgb(215,119,87)`; the ANSI preset would
turn it bright red in the OpenAI terminal palette. In tmux, where Claude renders
256 colors, the RGB value may quantize toward pink. The light-mode assistant label uses a darker
orange for readable text, with a lighter spinner shimmer.
Word highlights use softer green/red shades than the built-in ANSI palette;
the same theme tokens also color `+N` and `-N` counts. Inside tmux, Claude
quantizes light RGB word colors to indices 72 and 174; Ghostty remaps those
along with row colors to keep the appearance consistent. The empty usage-meter track stays neutral.
Dark mode sets `error` (errors and the bypass-permissions indicator) to
normal `ansi:red` instead of the preset's bright red, matching the status line's red.
Ghostty's `faint-opacity = 0.75` helps dimmed deletion text remain legible.
