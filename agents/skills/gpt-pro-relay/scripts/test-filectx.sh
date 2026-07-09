#!/usr/bin/env bash
# Tests for filectx — the shared file-context resolver/packer.
# Self-contained: builds a sandbox under a temp dir, exercises resolve/pack and
# every fail-closed guard, prints PASS/FAIL per case, exits nonzero on any failure.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
FILECTX="$HERE/filectx"
[ -x "$FILECTX" ] || { echo "test: filectx not executable at $FILECTX"; exit 1; }

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '        %s\n' "$2"; }

# pass <desc> <cmd...>   — expects exit 0
pass() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d" "expected success, got exit $?"; fi; }
# fail <desc> <cmd...>   — expects nonzero exit
fail() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then bad "$d" "expected failure, got success"; else ok "$d"; fi; }
# eqout <desc> <expected> <cmd...> — expects stdout to equal <expected>
eqout(){ local d="$1" exp="$2"; shift 2; local got; got=$("$@" 2>/dev/null); if [ "$got" = "$exp" ]; then ok "$d"; else bad "$d" "want [$exp] got [$got]"; fi; }

SB=$(mktemp -d "${TMPDIR:-/tmp}/filectx-test.XXXXXX")
trap 'rm -rf "$SB"' EXIT
SB=$(cd "$SB" && pwd -P)   # canonicalize (macOS /var → /private/var) to match filectx output

# ---- sandbox layout ----
mkdir -p "$SB/src" "$SB/docs" "$SB/tree/sub" "$SB/tree/.git" "$SB/tree/node_modules" "$SB/secrets"
printf 'print("a")\n'      > "$SB/src/a.py"
printf 'print("b")\n'      > "$SB/src/b.py"
printf '# readme\n'        > "$SB/docs/readme.md"
printf 'top\n'             > "$SB/tree/top.txt"
printf 'sub\n'             > "$SB/tree/sub/nested.txt"
printf 'ignored\n'         > "$SB/tree/.git/config"
printf 'ignored\n'         > "$SB/tree/node_modules/pkg.js"
printf 'KEY=abc\n'         > "$SB/secrets/.env"
printf 'KEY=example\n'     > "$SB/secrets/.env.example"
printf -- '-----BEGIN RSA PRIVATE KEY-----\nx\n-----END RSA PRIVATE KEY-----\n' > "$SB/secrets/leak.txt"
head -c 200 /dev/zero > "$SB/src/bin.dat"   # NUL bytes → binary
printf 'a.py\nb.py\n# comment\n\n' > "$SB/list.txt"

A="$SB/src/a.py"; B="$SB/src/b.py"

echo "== filectx tests =="

# --- resolve basics ---
eqout "resolve single abs file"           "$A"           "$FILECTX" resolve -- "$A"
eqout "resolve @base-relative"            "$A"           "$FILECTX" resolve --base "$SB" -- "@src/a.py"
eqout "resolve bare-relative via --base"  "$A"           "$FILECTX" resolve --base "$SB" -- "src/a.py"
pass  "resolve two files"                                "$FILECTX" resolve -- "$A" "$B"

# --- dedup ---
eqout "dedup identical specs"             "$A"           "$FILECTX" resolve -- "$A" "$A"

# --- globs ---
pass  "single-level glob matches"                        "$FILECTX" resolve --base "$SB" -- "src/*.py"
fail  "glob zero matches is fail-closed"                 "$FILECTX" resolve --base "$SB" -- "src/*.nope"

# --- directories ---
fail  "bare directory spec rejected"                     "$FILECTX" resolve -- "$SB/src"
pass  "--tree includes recursively"                      "$FILECTX" resolve --tree "$SB/tree"
# tree skips .git + node_modules + hidden; should resolve exactly top.txt + sub/nested.txt
eqout "--tree count (vendor/hidden pruned)" "2" bash -c "'$FILECTX' resolve --tree '$SB/tree' | wc -l | tr -d ' '"
fail  "--tree file cap enforced"                         "$FILECTX" resolve --tree "$SB/tree" --tree-max-files 1

# --- --from list ---
pass  "--from list file resolves"                        "$FILECTX" resolve --base "$SB/src" --from "$SB/list.txt"
eqout "--from skips comments/blanks (2 files)" "2" bash -c "'$FILECTX' resolve --base '$SB/src' --from '$SB/list.txt' | wc -l | tr -d ' '"

# --- missing / unreadable ---
fail  "missing file rejected"                            "$FILECTX" resolve -- "$SB/src/nope.py"

# --- caps ---
fail  "per-file cap rejected"                            "$FILECTX" resolve --max-bytes 1 -- "$A"
fail  "total cap rejected"                               "$FILECTX" resolve --max-total 1 -- "$A" "$B"

# --- binary ---
fail  "binary file as spec rejected"                     "$FILECTX" resolve -- "$SB/src/bin.dat"
# binary inside a tree is skipped, not fatal:
cp "$SB/src/bin.dat" "$SB/tree/blob.bin"
pass  "binary inside --tree is skipped, not fatal"       "$FILECTX" resolve --tree "$SB/tree"
rm -f "$SB/tree/blob.bin"

# --- secrets ---
fail  "secret filename (.env) denied by default"         "$FILECTX" resolve -- "$SB/secrets/.env"
pass  ".env.example is NOT a secret"                      "$FILECTX" resolve -- "$SB/secrets/.env.example"
fail  "secret content signature (private key) denied"    "$FILECTX" resolve -- "$SB/secrets/leak.txt"
pass  "--allow-secret overrides one path"                "$FILECTX" resolve --allow-secret "$SB/secrets/.env" -- "$SB/secrets/.env"
pass  "FILECTX_SECRETS=warn includes secret"             env FILECTX_SECRETS=warn "$FILECTX" resolve -- "$SB/secrets/.env"
pass  "FILECTX_SECRETS=off disables scan"                env FILECTX_SECRETS=off "$FILECTX" resolve -- "$SB/secrets/leak.txt"
# provider token signatures (regression: this helper ships context TO ChatGPT)
printf 'OPENAI_KEY=sk-proj-abcdEFGH0123456789ijklMNOP\n' > "$SB/secrets/openai.txt"
printf 'KEY=AIzaSyA0123456789abcdefABCDEFGHIJKLMNOPQ\n'   > "$SB/secrets/google.txt"
fail  "OpenAI sk-proj token content denied"              "$FILECTX" resolve -- "$SB/secrets/openai.txt"
fail  "Google AIza token content denied"                 "$FILECTX" resolve -- "$SB/secrets/google.txt"
# --allow-secret with an @base-relative spec (regression: must resolve against --base)
pass  "--allow-secret matches @base-relative form"       "$FILECTX" resolve --base "$SB" --allow-secret "@secrets/.env" -- "@secrets/.env"

# --- symlink-to-secret bypass (regression: BLOCKER — link name hid the real .env) ---
ln -s "$SB/secrets/.env" "$SB/innocent.txt"
fail  "symlink to a .env is caught (real target classified)"  "$FILECTX" resolve -- "$SB/innocent.txt"
ln -s "$SB/secrets/leak.txt" "$SB/innocent2.txt"
fail  "symlink to a private-key file is caught"               "$FILECTX" resolve -- "$SB/innocent2.txt"
# a legit (non-secret) symlink still resolves
ln -s "$SB/src/a.py" "$SB/alink.py"
pass  "legit symlink still resolves to its target"            "$FILECTX" resolve -- "$SB/alink.py"

# --- secret deeper than the old 16 KB scan window (regression: HIGH) ---
{ head -c 20000 /dev/zero | tr '\0' x; printf '\nAKIAIOSFODNN7EXAMPLE\n'; } > "$SB/secrets/deep.txt"
fail  "AWS key past 16 KB is caught (whole-file scan)"        "$FILECTX" resolve -- "$SB/secrets/deep.txt"

# --- broadened provider-token coverage (regression: HIGH) ---
printf 'tok=ASIAZ7Y4EXAMPLE12345\n'                     > "$SB/secrets/asia.txt"
printf 'PAT=ghu_abcdefghijklmnopqrstuvwxyz0123456789\n' > "$SB/secrets/ghu.txt"
printf 'GL=glpat-abcdef0123456789xyzAB\n'               > "$SB/secrets/glpat.txt"
printf 'OAI=sk-svcacct-abcdEFGH0123456789ijklMNOP\n'    > "$SB/secrets/svcacct.txt"
fail  "AWS temp key (ASIA) content caught"               "$FILECTX" resolve -- "$SB/secrets/asia.txt"
fail  "GitHub ghu_ token content caught"                 "$FILECTX" resolve -- "$SB/secrets/ghu.txt"
fail  "GitLab glpat- token content caught"               "$FILECTX" resolve -- "$SB/secrets/glpat.txt"
fail  "OpenAI service-account key content caught"        "$FILECTX" resolve -- "$SB/secrets/svcacct.txt"
# secret filename classes
printf 'x\n' > "$SB/secrets/kubeconfig"; printf 'x\n' > "$SB/secrets/.npmrc"
fail  "kubeconfig filename denied"                       "$FILECTX" resolve -- "$SB/secrets/kubeconfig"
fail  ".npmrc filename denied"                           "$FILECTX" resolve -- "$SB/secrets/.npmrc"

# --- --tree must not count skipped binaries toward the file cap (regression: MEDIUM) ---
mkdir -p "$SB/tcap"; printf 'text\n' > "$SB/tcap/only.txt"
head -c 100 /dev/zero > "$SB/tcap/b1.bin"; head -c 100 /dev/zero > "$SB/tcap/b2.bin"
pass  "--tree file cap counts only included files (binaries skipped)" \
  "$FILECTX" resolve --tree "$SB/tcap" --tree-max-files 1

# --- glob whose last match is a directory (regression: set -e silent-abort blocker) ---
mkdir -p "$SB/gx/zsub"; printf 'm\n' > "$SB/gx/main.py"; printf 'sub\n' > "$SB/gx/zsub/inner.py"
eqout "glob skips a trailing dir match, keeps the file" "$SB/gx/main.py" \
  "$FILECTX" resolve --base "$SB" -- "gx/*"

# --- pack format ---
PK=$("$FILECTX" pack -- "$A" 2>/dev/null)
case "$PK" in
  *"### $A"*'```'*'print("a")'*) ok "pack emits fenced block with path header" ;;
  *) bad "pack emits fenced block with path header" "got: $PK" ;;
esac

# --- json ---
if command -v jq >/dev/null 2>&1; then
  eqout "json total_bytes correct" "$(( $(wc -c < "$A") ))" \
    bash -c "'$FILECTX' resolve --json -- '$A' | jq -r .total_bytes"
  eqout "json file count" "2" \
    bash -c "'$FILECTX' resolve --json -- '$A' '$B' | jq -r '.files|length'"
fi

# --- usage errors (exit 2) ---
fail  "no mode is a usage error"                         "$FILECTX"
fail  "unknown mode is a usage error"                    "$FILECTX" frobnicate -- "$A"
fail  "--json on pack is a usage error"                  "$FILECTX" pack --json -- "$A"
fail  "no files resolved is an error"                    "$FILECTX" resolve

echo
echo "== filectx: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
