#!/bin/sh
# Codex Computer Use as a stdio MCP server for every Claude host (CLI, T3 Code, SDK apps).
#
# Runs the ChatGPT app's own @oai/cua-repl under its OpenAI-signed Node, which the
# Computer Use service accepts as a caller (launching SkyComputerUseClient from
# Claude Code directly fails with bootstrapTimedOut). Exposes one `js` tool with a
# `cua` API over two surfaces: `computer` (desktop apps through macOS accessibility)
# and `browser` with only the `chrome` backend, i.e. the ChatGPT browser extension
# and its native host (Codex's Chrome plugin; not the in-app browser). Any Chromium
# browser with that extension connected shows up, listed as "Chrome". The browser
# service and TinySky accessibility match what Codex's unified-computer-use plugin uses.
# computer-use-mcp-proxy.mjs sits in front of it; see agents/claude/README.md.
# Needs /Applications/ChatGPT.app and ~/.codex/computer-use (installed by the app).
C=/Applications/ChatGPT.app/Contents/Resources/cua_node
export CUA_REPL_ENABLED_SURFACES=browser,computer
export BROWSER_USE_AVAILABLE_BACKENDS=chrome
export BROWSER_USE_TINYSKY_ENABLED=1
export CUA_REPL_NODE_REPL_PATH="$C/bin/node_repl"
export NODE_REPL_NODE_PATH="$C/bin/node"
export NODE_REPL_NODE_MODULE_DIRS="$C/lib/node_modules"
export NODE_REPL_TRUSTED_CODE_PATHS="$HOME/.codex:$C/lib/node_modules"
export NODE_REPL_TRUSTED_SERVICES='{"browser":"@oai/browser-desktop/service","sky":"@oai/sky/service"}'
export SKY_CUA_SERVICE_PATH="$HOME/.codex/computer-use/Codex Computer Use.app"
export CODEX_HOME="$HOME/.codex"
export CU_EXTRA_INSTRUCTIONS='This is the only browser and computer-use tool: the built-in computer-use server and Claude in Chrome are off, so never ask the user to enable them. cua works per app or tab and cannot open the menu bar extras or Dock (com.apple.controlcenter, com.apple.dock time out). For those only, capture the screen with `screencapture -x <file>`, divide its pixels by the display scale (2 on Retina) to get screen points, and click with a CGEvent through `osascript -l JavaScript`; this moves the real pointer, so restore it afterwards.
For web browsing, use the browser API (cua.listBrowsers, cua.createBrowserTab, cua.getTab), not cua.getApp on a browser app. The browser listed as "Chrome" is the ChatGPT extension in the user'"'"'s Helium browser, and that extension is the only browser backend here. If no browser is listed, ask the user to open Helium; do not launch Google Chrome or reinstall browser plugins. Use Google Chrome only if the user asks for it.
Tabs you open are closed only when this Claude session ends, not after each turn: close a tab when you are done with it unless the user wants it kept.
Go straight to cua.getApp or cua.createBrowserTab when you know the target: cua.getState lists every app and tab, which is long.
Subagents share this REPL and browser session: use distinctive variable names and do not reuse another agent'"'"'s tab. The API docs appear only on the first call in this REPL, so a subagent that has not seen them must run `await cua.rewriteDocumentation()` first.'
exec "$C/bin/node" "$(dirname "$0")/computer-use-mcp-proxy.mjs" \
  "$C/bin/node" "$C/lib/node_modules/@oai/cua-repl/bin/cua-repl.mjs"
