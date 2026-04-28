---
name: pro-relay
description: |
  Send a prompt to ChatGPT Pro Extended via the gpt-pro service running on macmini, over SSH.
  Use this whenever the user wants a deep ChatGPT Pro response from a machine that's not their
  primary Chrome session — triggers on "ask gpt-pro", "send to gpt-pro", "use gpt-pro", "get a
  Pro Extended take", "ask the deep model", "second opinion from chatgpt pro". Different from
  the `chatgpt` skill, which drives live Chrome via in-chrome MCP. Returns response on stdout.
allowed-tools: Bash(ssh:*), Read, Write
user-invocable: true
---

# pro-relay

One prompt in, one response out. The actual ChatGPT browser automation runs on macmini behind SSH — no local Chrome, no extension required, just SSH access to macmini and a logged-in dedicated profile there.

## The command

```bash
ssh macmini /Users/chrisliu298/Developer/GitHub/gpt-pro/.venv/bin/gpt-pro ask <<'PROMPT'
... the prompt ...
PROMPT
```

- **stdout** = the ChatGPT response
- **stderr** = JSON status: `{"status":"ok","url":"...","run_dir":"...","response_chars":N}`
- **exit 0** = success. Anything else = read stderr for the structured reason.

Use a heredoc, not `echo "$prompt"` — bare echo mangles prompts containing `$`, backticks, or quotes.

## Cost gate

Pro Extended runs cost real Pro quota and take 5–20 minutes per prompt. Before invoking, ask the user unless they explicitly named gpt-pro in their request:

> "Send this to gpt-pro? It'll take ~5–20 min and use your Pro quota."

If they explicitly invoked the skill or named it, they've consented — just go.

## Background and timeout

`gpt-pro ask` blocks for the full reasoning duration. Always:

- `run_in_background: true`
- `timeout: 1800000` (30 min, well above typical max)

Wait for the completion notification — do NOT poll the output file.

## Errors

The stderr JSON's `reason` field tells you what failed:

| reason | meaning | what to do |
|---|---|---|
| `needs_reauth` | session cookie missing or expired | Tell the user to run `gpt-pro login` on macmini |
| `model_select_failed` | couldn't get Pro selected in the picker | Selectors drifted; surface `run_dir` to the user |
| `reasoning_mismatch` | Extended Pro chip absent after model select | Same — selectors drifted |
| `timeout` | no completion within 35 min | Inspect `run_dir/streaming-*.png` for what got stuck |
| `empty_prompt` | nothing on stdin | You forgot the heredoc |

`run_dir` lives on macmini at `~/.gpt-pro/runs/<ts>-ask/` — screenshots, DOM snapshot, network log. Reach for it via `ssh macmini ls/cat <run_dir>/...` when diagnosing.

## When to use vs the `chatgpt` skill

| Want | Use |
|---|---|
| Pro Extended, from any machine with SSH to macmini | `pro-relay` |
| Any model + any effort, driving your local live Chrome | `chatgpt` |
| Multi-turn follow-ups in the same chat | `chatgpt` (pro-relay is one-shot) |

## Multi-turn

pro-relay is one-shot per invocation — every call is a fresh ChatGPT conversation. To continue a thread, paste the prior response into the next prompt yourself. The dedicated profile retains login but does not persist conversation context across calls.

## Why this exists

The `chatgpt` skill is great when you're at the desk where Chrome is. pro-relay is the SSH-shaped variant: anywhere → macmini → ChatGPT Pro → response. No tunnel, no daemon, no API surface beyond SSH itself.
