#!/bin/sh
# Offline checks for shell/repo-sync against throwaway repos with a local bare upstream.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
t=$(mktemp -d "${TMPDIR:-/tmp}/repo-sync-test.XXXXXX")
trap 'rm -rf "$t"' EXIT HUP INT TERM
sync="$repo_root/shell/repo-sync"
fail() { echo "FAIL: $*" >&2; exit 1; }
commit() { echo "$2" > "$1/f"; git -C "$1" add f; git -C "$1" -c user.name=t -c user.email=t@t commit -qm "$2"; }

git init -q --bare -b main "$t/up.git"
git clone -q "$t/up.git" "$t/src" 2>/dev/null
commit "$t/src" one; git -C "$t/src" push -q origin main
git clone -q "$t/up.git" "$t/a"; git clone -q "$t/up.git" "$t/b"; git clone -q "$t/up.git" "$t/c"

commit "$t/src" two; git -C "$t/src" push -q origin main
echo local > "$t/b/f"                                   # b: uncommitted edit
commit "$t/c" mine                                      # c: local commit, diverges

"$sync" "$t/a" "$t/b" "$t/c" "$t/missing" > "$t/out" 2>&1 || fail "nonzero exit: $(cat "$t/out")"

[ "$(cat "$t/a/f")" = two ] || fail "clean clone not fast-forwarded"
[ "$(cat "$t/b/f")" = local ] || fail "dirty clone was touched"
[ "$(cat "$t/c/f")" = mine ] || fail "diverged clone was touched"
grep -q "$t/b: dirty" "$t/out" || fail "dirty clone not reported: $(cat "$t/out")"
grep -q "$t/c: diverged" "$t/out" || fail "diverged clone not reported: $(cat "$t/out")"
grep -q "$t/missing: not a git repo" "$t/out" || fail "missing repo not reported"

"$sync" "$t/a" > "$t/out2" 2>&1
[ ! -s "$t/out2" ] || fail "up-to-date run should be silent: $(cat "$t/out2")"
echo ok
