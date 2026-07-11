#!/usr/bin/env bash
set -euo pipefail

deny() {
    if command -v jq >/dev/null 2>&1; then
        jq -cn --arg reason "$1" '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: $reason
        }
    }'
    else
        printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Safety hook dependency jq is unavailable."}}'
    fi
    exit 0
}

payload=$(cat)
command -v jq >/dev/null 2>&1 || deny "Safety hook dependency jq is unavailable."
command=$(jq -er '.tool_input.command // empty | strings' <<<"$payload" 2>/dev/null) \
    || deny "Blocked a Bash tool call with malformed hook input."
cwd=$(jq -r '.cwd // empty | strings' <<<"$payload" 2>/dev/null)

[[ -n "$command" ]] || exit 0

recursive_rm='(^|[[:space:]])(command[[:space:]]+)?(\\)?(/bin/|/usr/bin/)?rm[[:space:]]+([^[:space:]]+[[:space:]]+)*(-[^[:space:]]*[rR][^[:space:]]*|--recursive)([[:space:]]|$)'
home_re=$(printf '%s' "$HOME" | sed 's/[][\\.^$*+?{}|()]/\\&/g')
home_parent=$(dirname "$HOME")
home_parent_re=$(printf '%s' "$home_parent" | sed 's/[][\\.^$*+?{}|()]/\\&/g')
protected_target="(/|${home_parent_re}|${home_re})"

# Inspect simple command clauses independently so an unrelated variable in a
# neighboring clause does not turn safe cleanup into a false positive.
set -f
old_ifs=$IFS
IFS=$'\n'
clauses=($(printf '%s\n' "$command" | tr ';&|' '\n'))
IFS=$old_ifs
set +f

for clause in "${clauses[@]}"; do
    inspection=$clause
    if ! grep -Eq "$recursive_rm" <<<"$inspection"; then
        if grep -Eq '(^|[[:space:]])(sh|bash|zsh)[[:space:]].*-c[[:space:]]' <<<"$clause"; then
            inspection=$(tr "\"'" '  ' <<<"$clause")
        fi
        grep -Eq "$recursive_rm" <<<"$inspection" || continue
    fi

# A cleanup variable can unexpectedly expand to $HOME or /, which caused the
# incident this hook primarily guards against. Command substitutions, globs,
# and absolute paths containing .. are likewise unresolved bulk targets.
    if grep -Eq '\$\{?[A-Za-z_][A-Za-z0-9_]*(\}|[:+?=-])?|\$\(|`' <<<"$inspection" \
        || grep -Eq "(^|[[:space:]\"'])~(/|[[:space:]\"']|$)" <<<"$inspection"; then
        deny "Blocked recursive deletion with a dynamic shell expansion. Resolve and verify the target first, then use a literal path."
    fi
    if grep -Eq "(^|[[:space:]\"'])/[^[:space:]\"']*/\\.\\.?(/|[[:space:]\"']|$)|(^|[[:space:]\"'])/{2,}" <<<"$inspection"; then
        deny "Blocked recursive deletion through an unnormalized absolute path. Resolve the target first."
    fi
    if grep -Eq "/[^[:space:]\"']*([\"'][^[:space:]]|\\\\[^[:space:]])" <<<"$inspection"; then
        deny "Blocked recursive deletion with a shell-fragmented absolute path. Use one verified literal token."
    fi

# Refuse the root, the home parent (/Users or /home), the home directory, and
# wildcard forms that erase their contents. Literal descendants remain allowed.
    if grep -Eq "(^|[[:space:]\"'])${protected_target}/*([[:space:]\"']|$)" <<<"$inspection" \
        || grep -Eq "(^|[[:space:]\"'])${protected_target}/?[^/[:space:]\"']*[?*[{]" <<<"$inspection"; then
        deny "Blocked recursive deletion of a protected root or all of its contents. Delete a verified literal descendant instead."
    fi
done

# A relative all-contents target becomes catastrophic after changing into a
# protected directory in the same compound command.
if grep -Eq "(^|[;&|[:space:]])cd[[:space:]]+([\"']?(\\\$HOME|\\\$\{HOME|~|${protected_target})[\"']?)([;&|[:space:]]|$)" <<<"$command" \
    && grep -Eq "(^|[;&|[:space:]])(\\\\)?(command[[:space:]]+)?(/bin/|/usr/bin/)?rm[[:space:]].*(-[^[:space:]]*[rR][^[:space:]]*|--recursive).*(^|[[:space:]\"'])(\\.?/?[?*[]|\\{)" <<<"$command"; then
    deny "Blocked bulk recursive deletion after changing into a protected directory."
fi

if [[ "$cwd" == / || "$cwd" == "$HOME" || "$cwd" == "$home_parent" ]] \
    && grep -Eq "(^|[;&|[:space:]])(\\\\)?(command[[:space:]]+)?(/bin/|/usr/bin/)?rm[[:space:]].*(-[^[:space:]]*[rR][^[:space:]]*|--recursive).*(^|[[:space:]\"'])(\\.?/?[?*[]|\\{)" <<<"$command"; then
    deny "Blocked a recursive all-contents deletion from a protected working directory."
fi

# Cover common non-rm spellings of the same catastrophic operation.
for clause in "${clauses[@]}"; do
    if grep -Eq '(^|[[:space:]])find[[:space:]].*(-delete|-exec[[:space:]]+rm)' <<<"$clause"; then
        if grep -Eq '\$\{?[A-Za-z_][A-Za-z0-9_]*(\}|[:+?=-])?|\$\(|`' <<<"$clause" \
            || grep -Eq "(^|[[:space:]\"'])~(/|[[:space:]\"']|$)" <<<"$clause" \
            || grep -Eq "(^|[[:space:]\"'])/[^[:space:]\"']*/\\.\\.?(/|[[:space:]\"']|$)|(^|[[:space:]\"'])/{2,}" <<<"$clause"; then
            deny "Blocked bulk find deletion with a dynamic or unnormalized target."
        fi
        if grep -Eq "(^|[[:space:]\"'])${protected_target}/*([[:space:]\"']|$)" <<<"$clause" \
            || grep -Eq "(^|[[:space:]\"'])${protected_target}/?[^/[:space:]\"']*[?*[{]" <<<"$clause"; then
        deny "Blocked bulk find deletion rooted at a protected home or filesystem path. Narrow the search to a verified descendant."
        fi
    fi
done

if grep -Eqi '(^|[;&|[:space:]])(diskutil[[:space:]]+(erase|partition|apfs[[:space:]]+delete)|mkfs([.]|[[:space:]])|newfs([_]?[a-z0-9]+)?[[:space:]]|dd[[:space:]].*of=/dev/(disk|rdisk))' <<<"$command"; then
    deny "Blocked disk formatting or raw disk overwrite. Run this manually outside the agent session if intentional."
fi

exit 0
