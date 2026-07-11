#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HOOK="$ROOT/prevent-catastrophic-delete.sh"

run_hook() {
    local home=${2:-$HOME}
    jq -cn --arg command "$1" '{tool_input: {command: $command}}' | HOME="$home" "$HOOK"
}

expect_blocked() {
    local output
    output=$(run_hook "$1" "${2:-$HOME}")
    [[ $(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$output") == deny ]] || {
        printf 'expected blocked: %s\n' "$1" >&2
        exit 1
    }
}

expect_allowed() {
    local output
    output=$(run_hook "$1" "${2:-$HOME}")
    [[ -z "$output" ]] || {
        printf 'expected allowed: %s\n%s\n' "$1" "$output" >&2
        exit 1
    }
}

expect_payload_blocked() {
    local output
    output=$(printf '%s' "$1" | "$HOOK")
    [[ $(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$output") == deny ]] || {
        printf 'expected malformed payload blocked: %s\n' "$1" >&2
        exit 1
    }
}

expect_blocked 'rm -rf "$HOME"'
expect_blocked 'rm -fr ${CLEANUP_TARGET}'
expect_blocked 'rm -Rf "$HOME"'
expect_blocked 'rm -fR /'
expect_blocked 'rm -rf $(printf /)'
expect_blocked 'rm -rf `printf /`'
expect_blocked "rm -rf $HOME"
expect_blocked 'rm --recursive --force /'
expect_blocked 'rm -rf /*'
expect_blocked "rm -rf $HOME/*"
expect_blocked "rm -rf $HOME/.*"
expect_blocked "rm -rf $HOME/.[!.]*"
expect_blocked "rm -rf $HOME/{*,.*}"
expect_blocked 'rm -rf /Users/../Users'
expect_blocked 'rm -rf ///Users'
expect_blocked "rm -rf /Us''ers"
expect_blocked 'rm -rf /User\s'
expect_blocked "rm -rf /ho\"me\"" '/home/chrisliu'
expect_blocked "sh -c 'rm -rf /'"
expect_blocked 'bash -c "rm -rf $HOME"'
expect_blocked 'find "$HOME" -type f -delete'
expect_blocked 'find / -xdev -delete'
expect_blocked 'find "$CLEANUP_TARGET" -delete'
expect_blocked 'find $(printf /) -delete'
expect_blocked 'find /tmp/.. -delete'
expect_blocked 'find /Users/../Users -delete'
expect_blocked "find $HOME/. -delete"
expect_blocked "find $HOME/.. -delete"
expect_blocked 'cd /Users && rm -rf *' '/Users/testuser'
expect_blocked 'cd "$HOME" && rm -rf ./*'
expect_blocked 'rm -rf /home' '/home/chrisliu'
expect_blocked 'rm -rf /home/*' '/home/chrisliu'
expect_blocked 'find /home -delete' '/home/chrisliu'
expect_blocked 'find /home/chrisliu -delete' '/home/chrisliu'
expect_blocked 'diskutil eraseDisk APFS Empty /dev/disk9'
expect_blocked 'dd if=/dev/zero of=/dev/disk9'

expect_allowed 'rm -rf ./build'
expect_allowed "rm -rf $HOME/Developer/GitHub/example/build"
expect_allowed 'echo "$CI"; rm -rf ./build'
expect_allowed 'rm -rf ./build && echo "$HOME"'
expect_allowed "rm -rf /home/chrisliu/project/build" '/home/chrisliu'
expect_allowed 'find ./build -type f -delete'
expect_allowed 'git clean -fd -- build/'

# Both clients send the same relevant PreToolUse fields; extra envelope fields
# must not affect the decision. Malformed hook input fails closed.
expect_payload_blocked '{'
expect_payload_blocked '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf \"$HOME\""},"permission_mode":"bypassPermissions"}'

missing_jq_output=$(printf '%s' '{"tool_input":{"command":"rm -rf \"$HOME\""}}' | PATH=/bin /bin/bash "$HOOK")
[[ $(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$missing_jq_output") == deny ]] || {
    printf 'expected missing jq to fail closed\n' >&2
    exit 1
}

printf 'catastrophic-delete hook tests passed\n'
