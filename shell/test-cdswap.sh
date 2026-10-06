#!/bin/sh
# Offline checks for shell/cdswap against a fake Claude Desktop data dir.
# CDSWAP_SKIP_APP=1 skips quitting/launching the real app.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/cdswap-test.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

app="$test_root/app"
mkdir -p "$app/IndexedDB"
export CDSWAP_APP_DATA="$app" CDSWAP_HOME="$test_root/store" CDSWAP_SKIP_APP=1
cdswap="$repo_root/shell/cdswap"

fail() { echo "FAIL: $*" >&2; exit 1; }

# login <uuid> <sessionKey>: simulate Desktop signed in as an account.
login() {
    rm -f "$app/Cookies"
    sqlite3 "$app/Cookies" "create table cookies(host_key, name, value);
        insert into cookies values('.claude.ai', 'sessionKey', '$2');"
    jq -n --arg u "$1" --arg k "$2" '{
        locale: "en-US",
        "oauth:tokenCache": ("cache-" + $k),
        "oauth:tokenCacheV2": ("v2-" + $k),
        lastKnownAccountUuid: $u,
        windowControlsZoomFactor: 1
    }' > "$app/config.json"
}
live_key() { sqlite3 "$app/Cookies" "select value from cookies where name='sessionKey'"; }
live_cfg() { jq -r "$1" "$app/config.json"; }

# Switching away from an account that was never saved must refuse.
login uuid-a key-a
"$cdswap" use nobody >/dev/null 2>&1 && fail "use of missing profile succeeded"
"$cdswap" save 'bad/name' >/dev/null 2>&1 && fail "invalid name accepted"

"$cdswap" save alice >/dev/null
login uuid-b key-b
"$cdswap" use alice >/dev/null 2>&1 && fail "switched away from unsaved account"
"$cdswap" save bob >/dev/null

# Non-account state changed while signed in as bob must survive the switch.
jq '.locale = "zh-CN"' "$app/config.json" > "$test_root/c" && mv "$test_root/c" "$app/config.json"
echo keep > "$app/IndexedDB/marker"
printf 'stale' > "$app/Cookies-journal"

"$cdswap" use alice >/dev/null
[ "$(live_key)" = key-a ] || fail "cookies not restored: $(live_key)"
[ "$(live_cfg '.lastKnownAccountUuid')" = uuid-a ] || fail "uuid not restored"
[ "$(live_cfg '."oauth:tokenCacheV2"')" = v2-key-a ] || fail "token not restored"
[ "$(live_cfg '.locale')" = zh-CN ] || fail "non-account config key changed"
[ "$(live_cfg '.windowControlsZoomFactor')" = 1 ] || fail "non-account config key dropped"
[ -f "$app/IndexedDB/marker" ] || fail "unrelated app data touched"
[ ! -e "$app/Cookies-journal" ] || fail "stale cookie journal left in place"

# Leaving bob checkpoints him, so a rotated sessionKey is not lost.
"$cdswap" list | grep '^\* alice' >/dev/null || fail "list does not mark alice current"
sqlite3 "$CDSWAP_HOME/bob/Cookies" "select value from cookies" | grep -qx key-b \
    || fail "bob checkpoint missing"
sqlite3 "$app/Cookies" "update cookies set value='key-a2'"
"$cdswap" use bob >/dev/null
[ "$(live_key)" = key-b ] || fail "switch back to bob failed"
sqlite3 "$CDSWAP_HOME/alice/Cookies" "select value from cookies" | grep -qx key-a2 \
    || fail "rotated alice session not checkpointed"

[ "$(stat -f %Lp "$CDSWAP_HOME")" = 700 ] || fail "store is not private"

# An interrupted restore (bob's Cookies, alice's config) is finished on the
# next run instead of being checkpointed over alice's profile.
cp "$CDSWAP_HOME/alice/Cookies" "$test_root/alice-cookies"
cp "$CDSWAP_HOME/bob/Cookies" "$app/Cookies"
jq --slurpfile p "$CDSWAP_HOME/alice/account.json" '. + $p[0]' "$app/config.json" > "$test_root/c" \
    && mv "$test_root/c" "$app/config.json"
echo bob > "$CDSWAP_HOME/.pending"
"$cdswap" use alice >/dev/null
cmp -s "$CDSWAP_HOME/alice/Cookies" "$test_root/alice-cookies" || fail "mixed state overwrote alice"
[ ! -e "$CDSWAP_HOME/.pending" ] || fail "pending marker left behind"
[ "$(live_key)" = key-a2 ] || fail "switch after recovery failed"

# A profile hidden by an interrupted capture is put back.
mv "$CDSWAP_HOME/bob" "$CDSWAP_HOME/.bob.old"
"$cdswap" list | grep 'bob' >/dev/null || fail "interrupted capture lost bob"

# Signed out (UUID lingers, no sessionKey): nothing to save or checkpoint.
sqlite3 "$app/Cookies" "delete from cookies"
"$cdswap" save alice >/dev/null 2>&1 && fail "saved a signed-out session"
cmp -s "$CDSWAP_HOME/alice/Cookies" "$test_root/alice-cookies" || fail "signed-out save touched alice"
"$cdswap" use alice | grep Switched >/dev/null || fail "signed-out use alice did not restore"
[ "$(live_key)" = key-a2 ] || fail "signed-out restore failed"

# Mutations are serialized.
mkdir "$CDSWAP_HOME/.lock"
"$cdswap" use bob >/dev/null 2>&1 && fail "ran while another cdswap held the lock"
rmdir "$CDSWAP_HOME/.lock"

echo "cdswap: all checks passed"
