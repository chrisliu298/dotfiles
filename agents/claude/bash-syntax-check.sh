#!/usr/bin/env bash
# PreToolUse(Bash) hook: refuse a command that does not parse.
#
# A reply cut off by a safeguards refusal can still have its tool call
# executed, so a command truncated mid-string would run as whatever prefix
# parses. The Bash tool runs commands through zsh, so check them with `zsh -n`
# and block (exit 2, reason on stderr) when parsing fails.
command=$(jq -r '.tool_input.command // empty')
[[ -n "$command" ]] || exit 0
if ! err=$(zsh -f -n -c "$command" 2>&1); then
    printf 'Command does not parse (%s); it may be truncated. Re-check what already ran before retrying.\n' \
        "$(head -1 <<<"$err")" >&2
    exit 2
fi
exit 0
