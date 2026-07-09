#!/usr/bin/env bash
# test-gpt-pro.sh — offline smoke test for the gpt-pro wrapper.
#
# Injects a fake `ssh` (and, for local-mode cases, a fake `hostname` + `gpt-pro-relay`)
# ahead of PATH to drive the submit→poll state machine with ZERO Pro quota and no real
# macmini. Covers the SSH path that can't be exercised any other way without burning quota:
# success, empty-body guard, submit-drop retry, transport backoff, terminal errors, the
# 127→venv fallback, deadline phase-state (124 vs 255), plus the local blocking path.
#
# Run: bash agents/skills/gpt-pro-relay/scripts/test-gpt-pro.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WRAP="$HERE/gpt-pro"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/gptpro-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

mkdir -p "$TMP/binssh" "$TMP/binlocal"

# ---- fake ssh: emulates `ssh <opts> macmini gpt-pro-relay <sub> ...` ----
cat > "$TMP/binssh/ssh" <<'FAKE'
#!/usr/bin/env bash
args=("$@"); sub=""; is_venv=0
for ((i=0;i<${#args[@]};i++)); do
  case "${args[$i]}" in
    */gpt-pro-relay) is_venv=1; sub="${args[$((i+1))]:-}"; break ;;
    gpt-pro-relay)   sub="${args[$((i+1))]:-}"; break ;;
  esac
done
st="$GPRT_STATE"
bump(){ local f="$st/$1" n=0; [ -f "$f" ] && n=$(cat "$f"); n=$((n+1)); echo "$n">"$f"; echo "$n"; }
case "$sub" in
  ask)
    cat >/dev/null; n=$(bump ask)
    case "$GPRT_SCN" in
      submit_drop_recover) [ "$n" -lt 2 ] && { echo '{"submit":"drop"}'>&2; exit 255; }; echo '{"submitted":true}'>&2; exit 0 ;;
      submit_drop_persist) echo '{"submit":"drop"}'>&2; exit 255 ;;
      submit_127)          [ "$is_venv" -eq 0 ] && exit 127; echo '{"submitted":true,"via":"venv"}'>&2; exit 0 ;;
      usage_conflict)      echo '{"error":"run_id_conflict"}'>&2; exit 2 ;;
      *)                   echo '{"submitted":true}'>&2; exit 0 ;;
    esac ;;
  fetch)
    n=$(bump fetch)
    case "$GPRT_SCN" in
      success)            [ "$n" -lt 3 ] && exit 124; printf 'THE ANSWER\n'; echo '{"ok":true}'>&2; exit 0 ;;
      empty_body)         echo '{"ok":true}'>&2; exit 0 ;;            # rc 0 but empty stdout
      transport_recover)  [ "$n" -lt 2 ] && exit 255; printf 'RECOVERED\n'; echo '{"ok":true}'>&2; exit 0 ;;
      terminal_error)     echo '{"error":"needs_reauth"}'>&2; exit 1 ;;
      deadline_pending)   sleep 1; exit 124 ;;                        # throttle the busy-spin
      deadline_transport) exit 255 ;;
      submit_drop_recover|submit_127) printf 'THE ANSWER\n'; echo '{"ok":true}'>&2; exit 0 ;;
      *)                  printf 'THE ANSWER\n'; echo '{"ok":true}'>&2; exit 0 ;;
    esac ;;
  *) echo "fake-ssh: bad sub '$sub' in: ${args[*]}">&2; exit 99 ;;
esac
FAKE
chmod +x "$TMP/binssh/ssh"

# ---- fake hostname (local mode → returns macmini) ----
printf '#!/usr/bin/env bash\necho macmini\n' > "$TMP/binlocal/hostname"
chmod +x "$TMP/binlocal/hostname"

# ---- fake local engine gpt-pro-relay ----
cat > "$TMP/binlocal/gpt-pro-relay" <<'FAKE'
#!/usr/bin/env bash
case "$1" in
  ask)   cat >/dev/null
         case "$GPRT_SCN" in
           local_empty) echo '{"ok":true}'>&2; exit 0 ;;
           *)           printf 'LOCAL ANSWER\n'; echo '{"ok":true}'>&2; exit 0 ;;
         esac ;;
  fetch) printf 'LOCAL REATTACH\n'; echo '{"ok":true}'>&2; exit 0 ;;
  *)     echo "fake-engine: bad sub $1">&2; exit 99 ;;
esac
FAKE
chmod +x "$TMP/binlocal/gpt-pro-relay"

# ---- runner ----
EXP_OUT=""; EXP_ERR=""
run_case() {  # <name> <mode ssh|local> <scenario> <expected-exit> <wrapper-extra-args>
  local name="$1" mode="$2" scn="$3" exp_exit="$4" extra="$5"
  local sd; sd="$(mktemp -d "$TMP/st.XXXXXX")"
  local path; [ "$mode" = local ] && path="$TMP/binlocal:$TMP/binssh:$PATH" || path="$TMP/binssh:$PATH"
  local out rc
  out="$(printf 'PROMPT BODY\n' | env PATH="$path" GPRT_SCN="$scn" GPRT_STATE="$sd" bash "$WRAP" $extra 2>"$sd/err")"; rc=$?
  local err; err="$(cat "$sd/err")"
  local ok=1 why=""
  [ "$rc" -eq "$exp_exit" ] || { ok=0; why+="exit got=$rc want=$exp_exit; "; }
  [ -z "$EXP_OUT" ] || grep -qF "$EXP_OUT" <<<"$out" || { ok=0; why+="stdout missing '$EXP_OUT' (got '${out:0:60}'); "; }
  [ -z "$EXP_ERR" ] || grep -qF "$EXP_ERR" <<<"$err" || { ok=0; why+="stderr missing '$EXP_ERR'; "; }
  if [ "$ok" -eq 1 ]; then printf 'PASS  %s\n' "$name"; PASS=$((PASS+1))
  else printf 'FAIL  %s\n        %s\n' "$name" "$why"; FAIL=$((FAIL+1)); fi
  EXP_OUT=""; EXP_ERR=""
}

echo "── SSH path ──"
EXP_OUT="THE ANSWER";                       run_case "success: pending×2 then body"        ssh success            0   ""
EXP_ERR="empty response";                   run_case "empty body on rc0 → exit 1"          ssh empty_body         1   ""
EXP_OUT="THE ANSWER"; EXP_ERR="retrying once"; run_case "submit drop (255) → retry → ok"    ssh submit_drop_recover 0  ""
EXP_ERR="submit state unknown";             run_case "submit drop ×2 → exit 255"           ssh submit_drop_persist 255 ""
EXP_OUT="THE ANSWER";                        run_case "127 → venv fallback → ok"            ssh submit_127         0   ""
EXP_ERR="run_id_conflict";                   run_case "submit usage error → exit 2"         ssh usage_conflict     2   ""
EXP_OUT="RECOVERED"; EXP_ERR="ssh dropped";  run_case "poll transport drop → backoff → ok"  ssh transport_recover  0   ""
EXP_ERR="needs_reauth";                      run_case "poll terminal error → exit 1"        ssh terminal_error     1   ""
EXP_ERR="still pending";                     run_case "deadline while pending → exit 124"   ssh deadline_pending   124 "--max-wait 3"
EXP_ERR="transport unknown";                 run_case "deadline all-transport → exit 255"   ssh deadline_transport 255 "--max-wait 3"

echo "── local (macmini) path ──"
EXP_OUT="LOCAL ANSWER";                      run_case "local blocking ask → ok"             local local_success    0   ""
EXP_ERR="empty response";                    run_case "local empty body → exit 1"           local local_empty      1   ""
EXP_OUT="LOCAL REATTACH";                    run_case "local --run-id blocking fetch → ok"  local local_reattach   0   "--run-id ask-20260530T000000Z-abc"

# ---- file inclusion (-f / --file) composition, via the shared filectx helper ----
# These exercise the compose-before-submit path: a clean file composes and submits
# (fake-ssh success), while a missing/secret file fails closed at exit 2 with no quota.
INCF="$TMP/inc"; mkdir -p "$INCF"
printf 'ALPHA CONTENTS\n' > "$INCF/a.txt"
printf 'PW=secret\n'      > "$INCF/.env"
EXP_ERR="included 1 local file"; run_case "-f attaches one file → composes + submits ok" ssh success 0 "-f $INCF/a.txt"
EXP_ERR="no quota burned";       run_case "-f missing file → fail-closed exit 2"          ssh success 2 "-f $INCF/nope.txt"
EXP_ERR="no quota burned";       run_case "-f secret .env → refused exit 2"               ssh success 2 "-f $INCF/.env"
EXP_OUT="THE ANSWER";            run_case "--allow-secret overrides the secret screen"    ssh success 0 "--allow-secret $INCF/.env -f $INCF/.env"
printf '%s\n' "$INCF/a.txt" > "$INCF/list.txt"
mkdir -p "$INCF/tree"; printf 'TT\n' > "$INCF/tree/t.txt"
EXP_ERR="included 1 local file"; run_case "--files-from composes the listed file"          ssh success 0 "--files-from $INCF/list.txt"
EXP_ERR="included 1 local file"; run_case "--include-tree composes a directory"            ssh success 0 "--include-tree $INCF/tree"
EXP_ERR="would include";         run_case "--dry-run lists resolved files, no submit"       ssh success 0 "--dry-run -f $INCF/a.txt"

echo
echo "──────────────────────────────"
printf 'total: %d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
