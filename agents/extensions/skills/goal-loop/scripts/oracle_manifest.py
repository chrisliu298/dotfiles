#!/usr/bin/env python3
"""goal-loop frozen-oracle manifest — validator + live RED/GREEN evaluator.

The manifest (`.goals/<id>.oracles.json`, schema `goal-oracles/v1`) is the operator's executable
acceptance oracles, authored AT SIGN-OFF and frozen with the spec. It is what lets `--auto` safely
auto-fix: a finding mapped to an AC whose oracle is currently RED is the only auto-acceptable class
(see references/loop-protocol.md § The frozen-oracle manifest; scripts/oracle_gate.py is the offline
proof that gating on it is safe — false-auto=0).

Trust model: the commands are OPERATOR-authored at sign-off (trusted), frozen, author/fixer-separated.
This runner executes them with a timeout to compute state. A fix round must never edit the manifest
(its paths are excluded from the fix allow_paths).

  python3 oracle_manifest.py validate <manifest.json> [<artifact.md>]   # schema check (+ soft AC cross-ref)
  python3 oracle_manifest.py evaluate <manifest.json> [--cwd DIR]       # run oracles → RED/GREEN/manual
  python3 oracle_manifest.py selftest                                   # self-check (no external deps)

exit 0 = ok/pass, 1 = invalid/fail.
"""
import json
import os
import subprocess
import sys
import tempfile

SCHEMA = "goal-oracles/v1"
KINDS = {"mechanical", "manual"}
DEFAULT_TIMEOUT = int(os.environ.get("ORACLE_TIMEOUT", "300"))


def load(path):
    with open(path) as f:
        return json.load(f)


def validate(manifest, artifact_text=None):
    """Return (errors, warnings). errors empty => valid."""
    errs, warns = [], []
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"], warns
    if manifest.get("schema_version") != SCHEMA:
        errs.append(f"schema_version must be {SCHEMA!r}")
    for field in ("id", "source_artifact", "oracles"):
        if field not in manifest:
            errs.append(f"missing required field {field!r}")
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
            warns.append(f"{where} ac_id {ac!r} not found in the artifact (soft check)")
        if kind not in KINDS:
            errs.append(f"{where} kind must be one of {sorted(KINDS)}")
        cmd = o.get("command")
        if kind == "mechanical":
            if not isinstance(cmd, str) or not cmd.strip():
                errs.append(f"{where} mechanical oracle needs a non-empty 'command'")
            if not isinstance(o.get("allowed_paths", []), list):
                errs.append(f"{where} 'allowed_paths' must be a list")
            if not isinstance(o.get("preservation", []), list):
                errs.append(f"{where} 'preservation' must be a list")
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


def evaluate(manifest, cwd=".", timeout=DEFAULT_TIMEOUT):
    """Return a list of {ac_id, oracle_id, state} where state in RED|GREEN|manual|TIMEOUT."""
    rows = []
    for o in manifest.get("oracles", []):
        ac, oid, kind = o.get("ac_id"), o.get("oracle_id"), o.get("kind")
        if kind == "manual":
            state = "manual"
        else:
            code, to = _run(o["command"], cwd, timeout)
            state = "TIMEOUT" if to else ("GREEN" if code == 0 else "RED")
        rows.append({"ac_id": ac, "oracle_id": oid, "state": state})
    return rows


def selftest():
    ok = True

    def check(cond, label):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    good = {
        "schema_version": SCHEMA, "id": "t", "source_artifact": "a.md",
        "oracles": [
            {"ac_id": "AC-1", "oracle_id": "O1", "kind": "mechanical",
             "command": "exit 0", "allowed_paths": ["src"], "preservation": ["exit 0"]},
            {"ac_id": "AC-2", "oracle_id": "O2", "kind": "mechanical",
             "command": "exit 1", "allowed_paths": ["src"], "preservation": []},
            {"ac_id": "AC-3", "oracle_id": "O3", "kind": "manual", "command": None},
        ],
    }
    errs, warns = validate(good, artifact_text="AC-1 AC-2 AC-3")
    check(not errs, f"valid manifest passes (errs={errs})")
    check(not warns, f"no warnings when all ac_ids present (warns={warns})")

    _, warns2 = validate(good, artifact_text="AC-1 only")
    check(len(warns2) == 2, "missing ac_ids in artifact produce soft warnings, not errors")

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
    }
    for label, oracles in bad_cases.items():
        errs, _ = validate({"schema_version": SCHEMA, "id": "t", "source_artifact": "a.md", "oracles": oracles})
        check(bool(errs), f"rejects: {label}")
    errs, _ = validate({"id": "t", "source_artifact": "a.md", "oracles": []})
    check(bool(errs), "rejects: missing schema_version")

    # round-trip through a temp file (validate reads JSON off disk)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(good, f)
        tmp = f.name
    try:
        errs, _ = validate(load(tmp))
        check(not errs, "round-trips through a file on disk")
    finally:
        os.unlink(tmp)

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
            print("usage: oracle_manifest.py validate <manifest.json> [<artifact.md>]", file=sys.stderr)
            return 1
        artifact_text = None
        if len(argv) >= 3:
            with open(argv[2]) as f:
                artifact_text = f.read()
        errs, warns = validate(load(argv[1]), artifact_text)
        for w in warns:
            print("warning:", w, file=sys.stderr)
        for e in errs:
            print("error:", e, file=sys.stderr)
        print("VALID" if not errs else "INVALID")
        return 0 if not errs else 1
    if cmd == "evaluate":
        cwd = "."
        if "--cwd" in argv:
            cwd = argv[argv.index("--cwd") + 1]
        rows = evaluate(load(argv[1]), cwd=cwd)
        for r in rows:
            print(f"{r['ac_id']:10} {r['oracle_id']:8} {r['state']}")
        red = [r["ac_id"] for r in rows if r["state"] == "RED"]
        print(f"\nRED (auto-fix-eligible ACs)={red or 'none'}  total={len(rows)}")
        return 0
    print(f"unknown command {cmd!r}; see --help", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
