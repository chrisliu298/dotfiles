# Recovery — manual fallback when prism-launch is missing

Read this **only** when `~/.claude/skills/prism/scripts/prism-launch` does not exist at all (a broken install). A bare-name "command not found" is **NOT** this case — re-invoke by the absolute path `~/.claude/skills/prism/scripts/prism-launch`.

This flow bypasses **every** mechanical guard (roster contract, floor check, injection guards, manifest `.shape`), so it is the one path where a partial roster can slip through unchecked. Never reach for it to "move faster" or to dodge a floor-check failure — that failure is the system working; fix the dispatch instead.

**The invariant survives even here: enforce the FULL roster yourself — one relay call per standard peer + one Agent call per subagent, no family omitted unless the user explicitly authorized it.**

1. **First repair the install:** `cd ~/dotfiles && ./dotfiles.sh`.
2. **If repair is truly impossible**, render each launcher and dispatch by hand:
   - Render each launcher with
     `sed -e 's|{{SHARED_PACKET_PATH}}|...|g' -e 's|{{LENS_NAME}}|...|g' -e 's|{{LENS_DESC}}|...|g' templates/launcher-<kind>.tmpl`.
   - Dispatch one `relay call --to <peer> --name prism-<slug>` heredoc per parallax tier (GPT `--effort xhigh`, Grok Build `--effort high`, no `--effort` on the rest; background each, `timeout: 3660000`).
   - Issue one Agent call per subagent using the rendered subagent launcher.
