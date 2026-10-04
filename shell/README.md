# Shell

Zsh with Zinit plugin manager and Starship prompt.

## Files

| File | Purpose |
|------|---------|
| `.zshenv` | Platform detection (`IS_MACOS`), environment variables, PATH |
| `.zshrc` | Plugin manager, completions, keybindings, history |
| `.aliases` | Command shortcuts |
| `.functions` | Shell utility functions |

Load order: `.zshenv` → `.zshrc` (sources `.aliases` and `.functions`).

Codex has one managed user-facing entrypoint: `~/.local/bin/codex`, linked to the
global npm `@openai/codex` package. `dotfiles.sh` checks it on every run, repairs
stale standalone links, and installs/upgrades versions below `0.159.2`. This
directory leads PATH, so shell shortcuts and `gpt-subagent` use the same CLI;
the review helper also uses the absolute path and checks its version before
dispatch. Use `xu` or `codex update` for future upgrades. The desktop app keeps
its own private runtimes, which are managed by the app rather than dotfiles.

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

The `ct` shell shortcut launches `codex-traex --yolo`, matching `x`'s approval
behavior. Its companion shortcuts mirror `xc`, `xr`, and `xu`:

| Official | TraeX | Action |
|----------|-------|--------|
| `x` | `ct` | Start a session |
| `xc` | `ctc` | Continue the most recent session |
| `xr` | `ctr` | Open the session picker, or resume the supplied session ID |
| `xu` | `ctu` | Update the shared native Codex CLI |

`ctc` and `ctr` select sessions from the independent TraeX home. Both accept
additional Codex arguments, such as `ctr <session-id>` or
`ctc --model GPT-5.6-Sol`. `ctu` calls `xu`; it does not update TraeX or the bridge.

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
run `traex login`, complete the authentication flow, and retry `ct`.
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

## Plugins (Zinit)

`zsh-syntax-highlighting`, `zsh-completions`, `zsh-autosuggestions`, `fzf` + `fzf-tab`, Oh My Zsh snippets (`git`, `sudo`, `command-not-found`). Modern Unix tools (`fd`, `rg`, `zoxide`, `delta`) installed via Zinit from GitHub releases.

## Key Aliases & Functions

See `.aliases` and `.functions` for the full list. Highlights:

- **Shell**: `ez` (reload), `o` (open), `b` (btop), `theme [light|dark|toggle|status]` / `theme --all <mode>` (OpenAI light/dark across terminal tools and macOS appearance)
- **Tmux**: `t`, `ta`, `tl`, `tn`, `tk`, `to` (new/attach to `$PWD` name), `tka` (kill all)
- **Python/uv**: `sv` (source venv), `us` (sync), `ua` (add)
- **Claude Code**: `c` (auto-accept), `cc` (continue), `cr` (resume), `cpu` (/push), `scout-papers-scholar-inbox-all` (sequentially scout five awesome lists with Opus at high effort, showing final messages only)
- **Codex**: `x` / `ct` (official / TraeX), `xc` / `ctc` (resume --last), `xr` / `ctr` (resume picker or session ID), `xu` / `ctu` (update shared CLI), `cal`/`cas`/`caw`/`caa` (codex-auth list/status/switch/login)
- **Homebrew**: `bi`/`bu`/`bic` (install/uninstall/cask), `bupd`/`bupg` (update/upgrade)
- **Functions**: `dfs` (pull + install + sync remote), `theme [light|dark|toggle|status]` / `theme --all <mode>` (Ghostty + Starship + btop + tmux + Neovim + Codex TUI + Claude Code ANSI-based theme + macOS; fastfetch follows ANSI; `--all` also applies to macmini and l40s), `synckeys` (propagate `~/.zshenv.local` API/plan keys to peers; dry-run by default, `synckeys apply` to write), `rename_device`

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
