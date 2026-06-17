#!/usr/bin/env python3
"""goal-loop frozen-oracle manifest — validator + live RED/GREEN evaluator.

The manifest (`.goals/<id>.oracles.json`, schema `goal-oracles/v1`) is the operator's executable
acceptance oracles, authored AT SIGN-OFF and frozen with the spec. It is what lets `--auto` safely
auto-fix: a finding mapped to an AC whose oracle is currently RED is the only auto-acceptable class
(see references/loop-protocol.md § The frozen-oracle manifest; scripts/oracle_gate.py is the offline
proof that gating on it is safe — false-auto=0).

What this script does and does NOT do:
- `validate` checks schema, unique oracle_ids, kind/command consistency, that `spec_sha256` is present
  and well-formed, and (with `--strict`, used by `--auto`) that every `ac_id` exists in the artifact.
- `evaluate` runs each mechanical oracle's command and reports RED/GREEN/manual/TIMEOUT. A RED state is
  NECESSARY but NOT SUFFICIENT for AUTO-FIX — the full apply gate (RED→GREEN + preservation GREEN +
  paths within authority + no test/spec/oracle edit + behavioral-delta containment + anti-overfit) is
  enforced by the `--auto` protocol, NOT by this script. `oracle_gate.py` is the offline proof of that
  gate's safety; it is never run live, and this script only supplies the RED/GREEN evidence the gate
  consumes. `spec_sha256` staleness (manifest vs the current frozen spec block) is likewise checked by
  the `--auto` entry precondition, not here.

Trust model: the commands are OPERATOR-authored at sign-off (trusted), frozen, author/fixer-separated.
This runner executes them with a timeout to compute state. A fix round must never edit the manifest
(its paths are excluded from the fix allow_paths).

  python3 oracle_manifest.py validate <manifest.json> [<artifact.md>] [--strict]   # schema + AC check
  python3 oracle_manifest.py evaluate <manifest.json> [--cwd DIR]                   # run oracles → state
  python3 oracle_manifest.py selftest                                              # self-check (no deps)

exit 0 = ok/pass, 1 = invalid/fail.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

SCHEMA = "goal-oracles/v1"
KINDS = {"mechanical", "manual"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _env_timeout():
    try:
        return max(1, int(os.environ.get("ORACLE_TIMEOUT", "300")))
    except (ValueError, TypeError):
        return 300


DEFAULT_TIMEOUT = _env_timeout()


def load(path):
    with open(path) as f:
        return json.load(f)


def validate(manifest, artifact_text=None, strict=False):
    """Return (errors, warnings). errors empty => valid.

    strict=True (used by --auto) promotes the AC-membership check to a hard error: an oracle whose
    ac_id is absent from the frozen artifact signals a stale/mismatched manifest, which under --auto
    must fail closed rather than warn.
    """
    errs, warns = [], []
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"], warns
    if manifest.get("schema_version") != SCHEMA:
        errs.append(f"schema_version must be {SCHEMA!r}")
    for field in ("id", "source_artifact", "oracles"):
        if field not in manifest:
            errs.append(f"missing required field {field!r}")
    sha = manifest.get("spec_sha256")
    if not isinstance(sha, str) or not SHA256_RE.match(sha):
        errs.append("spec_sha256 must be a 64-char lowercase-hex sha256 of the frozen spec at sign-off")
    oracles = manifest.get("oracles")
    if not isinstance(oracles, list):
        return errs + ["'oracles' must be a list"], warns
    seen_ids = set()
    for i, o in enumerate(oracles):
        where = f"oracle[{i}]"
        if not isinstance(o, dict):
            errs.append(f"{where} is not an object")
            continue
        oid = o.get("oracle_id")
        ac = o.get("ac_id")
        kind = o.get("kind")
        if not isinstance(oid, str) or not oid:
            errs.append(f"{where} missing non-empty oracle_id")
        elif oid in seen_ids:
            errs.append(f"{where} duplicate oracle_id {oid!r}")
        else:
            seen_ids.add(oid)
        if not isinstance(ac, str) or not ac:
            errs.append(f"{where} missing non-empty ac_id")
        elif artifact_text is not None and ac not in artifact_text:
            if strict:
                errs.append(f"{where} ac_id {ac!r} not found in the artifact (stale/mismatched manifest)")
            else:
                warns.append(f"{where} ac_id {ac!r} not found in the artifact (soft check)")
        if kind not in KINDS:
            errs.append(f"{where} kind must be one of {sorted(KINDS)}")
        cmd = o.get("command")
        if kind == "mechanical":
            if not isinstance(cmd, str) or not cmd.strip():
                errs.append(f"{where} mechanical oracle needs a non-empty 'command'")
            for key in ("allowed_paths", "preservation"):
                v = o.get(key, [])
                if not isinstance(v, list) or any(not isinstance(p, str) or not p.strip() for p in v):
                    errs.append(f"{where} '{key}' must be a list of non-empty strings")
        elif kind == "manual" and cmd is not None:
            errs.append(f"{where} manual oracle must have command: null")
    return errs, warns


def _run(cmd, cwd, timeout):
    """Run a shell command; return (exit_code, timed_out)."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=timeout)
        return r.returncode, False
    except subprocess.TimeoutExpired:
        return None, True


def evaluate(manifest, cwd=".", timeout=DEFAULT_TIMEOUT, validate_first=True):
    """Return a list of {ac_id, oracle_id, state} where state in RED|GREEN|manual|TIMEOUT.

    Fails closed: by default validates first and raises ValueError on a malformed manifest, so a
    caller (e.g. --auto) treats an invalid manifest as 'no usable oracles' instead of crashing mid-run.
    """
    if validate_first:
        errs, _ = validate(manifest)
        if errs:
            raise ValueError("invalid manifest: " + "; ".join(errs))
    rows = []
    for o in manifest.get("oracles", []):
        ac, oid, kind = o.get("ac_id"), o.get("oracle_id"), o.get("kind")
        if kind == "manual":
            state = "manual"
        else:
            code, to = _run(o.get("command") or "false", cwd, timeout)
            state = "TIMEOUT" if to else ("GREEN" if code == 0 else "RED")
        rows.append({"ac_id": ac, "oracle_id": oid, "state": state})
    return rows


def selftest():
    ok = True

    def check(cond, label):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    HASH = "0" * 64

    def wrap(oracles):
        return {"schema_version": SCHEMA, "id": "t", "source_artifact": "a.md",
                "spec_sha256": HASH, "oracles": oracles}

    good = wrap([
        {"ac_id": "AC-1", "oracle_id": "O1", "kind": "mechanical",
         "command": "exit 0", "allowed_paths": ["src"], "preservation": ["exit 0"]},
        {"ac_id": "AC-2", "oracle_id": "O2", "kind": "mechanical",
         "command": "exit 1", "allowed_paths": ["src"], "preservation": []},
        {"ac_id": "AC-3", "oracle_id": "O3", "kind": "manual", "command": None},
    ])
    errs, warns = validate(good, artifact_text="AC-1 AC-2 AC-3")
    check(not errs, f"valid manifest passes (errs={errs})")
    check(not warns, f"no warnings when all ac_ids present (warns={warns})")

    _, warns2 = validate(good, artifact_text="AC-1 only")
    check(len(warns2) == 2, "missing ac_ids → soft warnings (non-strict)")
    errs_s, _ = validate(good, artifact_text="AC-1 only", strict=True)
    check(len(errs_s) == 2, "missing ac_ids → hard errors under --strict (stale manifest)")

    states = {r["oracle_id"]: r["state"] for r in evaluate(good)}
    check(states == {"O1": "GREEN", "O2": "RED", "O3": "manual"},
          f"evaluate computes GREEN/RED/manual from exit codes ({states})")

    bad_cases = {
        "duplicate oracle_id": [
            {"ac_id": "A", "oracle_id": "X", "kind": "manual", "command": None},
            {"ac_id": "B", "oracle_id": "X", "kind": "manual", "command": None}],
        "mechanical without command": [
            {"ac_id": "A", "oracle_id": "X", "kind": "mechanical", "command": ""}],
        "manual with command": [
            {"ac_id": "A", "oracle_id": "X", "kind": "manual", "command": "exit 0"}],
        "unknown kind": [
            {"ac_id": "A", "oracle_id": "X", "kind": "other", "command": None}],
        "allowed_paths not strings": [
            {"ac_id": "A", "oracle_id": "X", "kind": "mechanical", "command": "exit 1",
             "allowed_paths": [1, ""], "preservation": []}],
    }
    for label, oracles in bad_cases.items():
        errs, _ = validate(wrap(oracles))
        check(bool(errs), f"rejects: {label}")
    check(bool(validate({"id": "t", "source_artifact": "a.md", "spec_sha256": HASH, "oracles": []})[0]),
          "rejects: missing schema_version")
    check(any("spec_sha256" in e for e in validate(
        {"schema_version": SCHEMA, "id": "t", "source_artifact": "a.md", "oracles": []})[0]),
        "rejects: missing spec_sha256")
    check(any("spec_sha256" in e for e in validate(
        {"schema_version": SCHEMA, "id": "t", "source_artifact": "a.md",
         "spec_sha256": "nothex", "oracles": []})[0]),
        "rejects: malformed spec_sha256")

    # round-trip through a temp file (validate reads JSON off disk)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(good, f)
        tmp = f.name
    try:
        errs, _ = validate(load(tmp))
        check(not errs, "round-trips through a file on disk")
    finally:
        os.unlink(tmp)

    # TIMEOUT path: a command that outlasts the deadline reports TIMEOUT, not GREEN/RED
    slow = wrap([{"ac_id": "A", "oracle_id": "O", "kind": "mechanical",
                  "command": "sleep 5", "allowed_paths": [], "preservation": []}])
    tstates = {r["oracle_id"]: r["state"] for r in evaluate(slow, timeout=1)}
    check(tstates == {"O": "TIMEOUT"}, f"evaluate reports TIMEOUT past the deadline ({tstates})")

    # fail-closed: evaluate refuses a malformed manifest (raises, never crashes mid-run)
    try:
        evaluate(wrap([{"ac_id": "A", "oracle_id": "O", "kind": "mechanical", "command": ""}]))
        check(False, "evaluate refuses an invalid manifest")
    except ValueError:
        check(True, "evaluate refuses an invalid manifest (fails closed)")

    # malformed ORACLE_TIMEOUT env must not crash the import-time parse
    check(_env_timeout() >= 1, "_env_timeout returns a sane default")

    print("oracle_manifest selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "selftest":
        return selftest()
    if cmd == "validate":
        if len(argv) < 2:
            print("usage: oracle_manifest.py validate <manifest.json> [<artifact.md>] [--strict]", file=sys.stderr)
            return 1
        strict = "--strict" in argv
        pos = [a for a in argv[1:] if a != "--strict"]
        artifact_text = None
        if len(pos) >= 2:
            with open(pos[1]) as f:
                artifact_text = f.read()
        errs, warns = validate(load(pos[0]), artifact_text, strict=strict)
        for w in warns:
            print("warning:", w, file=sys.stderr)
        for e in errs:
            print("error:", e, file=sys.stderr)
        print("VALID" if not errs else "INVALID")
        return 0 if not errs else 1
    if cmd == "evaluate":
        if len(argv) < 2:
            print("usage: oracle_manifest.py evaluate <manifest.json> [--cwd DIR]", file=sys.stderr)
            return 1
        cwd = "."
        if "--cwd" in argv:
            i = argv.index("--cwd")
            if i + 1 >= len(argv):
                print("error: --cwd needs a directory argument", file=sys.stderr)
                return 1
            cwd = argv[i + 1]
        try:
            rows = evaluate(load(argv[1]), cwd=cwd)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        for r in rows:
            print(f"{r['ac_id']:10} {r['oracle_id']:8} {r['state']}")
        red = [r["ac_id"] for r in rows if r["state"] == "RED"]
        timo = [r["ac_id"] for r in rows if r["state"] == "TIMEOUT"]
        mech = [r for r in rows if r["state"] in ("RED", "GREEN", "TIMEOUT")]
        green = sum(1 for r in rows if r["state"] == "GREEN")
        print(f"\nRED mechanical-oracle ACs (necessary, NOT sufficient — the full apply gate runs next)={red or 'none'}")
        if timo:
            print(f"TIMEOUT/unknown ACs (block AUTO-COMPLETE; treat as not-GREEN, may warrant HALT)={timo}")
        print(f"mechanical: {green}/{len(mech)} GREEN  total oracles={len(rows)}")
        return 0
    print(f"unknown command {cmd!r}; see --help", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
