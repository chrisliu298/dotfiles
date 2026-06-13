#!/usr/bin/env python3
"""Frozen-oracle gate — the empirical test of whether ORACLE-GATING (verify the change against a
pre-signed executable oracle) closes the F1/F16 wall that the lexical router (empirical_gate.py)
could not.

The gate is mechanical and COMPUTES every route from behavior tokens — it never looks up a desired
answer. A patch AUTO-APPLIES iff: it flips a currently-RED, pre-signed oracle to GREEN (it provides
every behavior that oracle asserts), it regresses no GREEN oracle, every behavior it introduces is
AUTHORIZED by a flipped oracle (behavioral-delta containment), it does not edit a frozen oracle, it
stays in allowed paths, and it survives the anti-overfit (mutation/differential) check. Else STOP.

Two manifests:
  M1 = the roadmap's ACTUAL executable `Acceptance:` commands (plan.md phases). The impl is COMPLETE,
       so every M1 oracle is GREEN.
  M2 = a mid-drive state with the SAME oracles plus two STRONGER oracles (covering method-id
       preservation and the kind-guard) that are currently RED — i.e. a spec author wrote richer
       oracles and the impl hasn't satisfied them yet.

Run: python3 oracle_gate.py
"""
from itertools import chain

# ── Behavior tokens: an oracle ASSERTS a set; a fix PROVIDES a set. Routing is set algebra. ──
# M1 oracles = the roadmap's real executable acceptance commands (all GREEN — impl is complete).
def O(asserts, state="GREEN", allow=("roadmap",)):
    return {"asserts": set(asserts), "authorizes": set(asserts), "state": state, "frozen": True, "allow": set(allow)}

M1 = {
    "P1": O({"parse:5playbooks", "parse:stages", "validate:tags"}),
    "P2": O({"classify:deterministic", "classify:5routes", "preserve:stage", "preserve:evidence"}),
    "P3": O({"start:stamp", "method:show", "method:advance-evidence", "method:refuse-no-evidence",
             "method:set-reset", "mint:exclude-playbooks"}),
    "P4": O({"today:method-line", "complete:advisory-warn"}),
    "P5": O({"weekly:metrics"}),
    "P6": O({"build:no-clobber-stage-evidence"}),
    "C7": O({"loaditems:skip-playbooks"}),
}
# M2 = M1 (still green) + two stronger, currently-RED oracles the author could have signed.
M2 = {**{k: {**v, "state": "GREEN"} for k, v in M1.items()},
      "C4-methodid":  O({"preserve:method-id"},   state="RED"),   # "a user `set` override must persist" (C4 prose) — now an oracle, currently failing
      "C7-kindguard": O({"method:kind-guard"},     state="RED")}  # "method fields only on unit/item" — now an oracle, currently failing

# ── The 18 real review findings: what behavior each fix PROVIDES (faithful to the proposed fix). ──
# (no `breaks`, no oracle edits, fixes are real → mutation_survives=True)
def F(provides):
    return {"provides": set(provides), "breaks": set(), "edits_oracle": False, "touches": {"roadmap"}, "mutation_survives": True}

FINDINGS = {
    "F1":  F({"loaditems:parse-robustness"}),
    "F2":  F({"method:set-preserve-on-same-id"}),   # NB: contradicts P3's signed `method:set-reset`
    "F3":  F({"method:kind-guard"}),
    "F4":  F({"cursor:clamp-consistency"}),
    "F5":  F({"hygiene:dead-code-removed"}),
    "F6":  F({"preserve:method-id"}),
    "F7":  F({"migration:pre-layer-items"}),
    "F8":  F({"parse:fail-closed"}),
    "F9":  F({"method:switch-evidence-policy"}),
    "F10": F({"cursor:preserve-bad-stage"}),
    "F11": F({"orphan:method-aware"}),
    "F12": F({"cursor:final-stage-semantics"}),
    "F13": F({"cursor:clamp-persisted"}),
    "F14": F({"error:missing-playbook"}),
    "F15": F({"method:set-unset"}),
    "F16": F({"classify:url-extraction"}),
    "F17": F({"hygiene:dedupe-render"}),
    "F18": F({"refactor:weekly", "durability:mtime-fsync"}),
}
# Adversarial patches (run only against M2, where a real RED oracle exists to exploit):
ADV = {
    "ADV-wrong-but-green-regress": {"provides": {"preserve:method-id"}, "breaks": {"loaditems:skip-playbooks"},
                                     "edits_oracle": False, "touches": {"roadmap"}, "mutation_survives": True},
    "ADV-unauthorized-delta":      {"provides": {"preserve:method-id", "classify:url-extraction"}, "breaks": set(),
                                     "edits_oracle": False, "touches": {"roadmap"}, "mutation_survives": True},
    "ADV-overfit-rewardhack":      {"provides": {"preserve:method-id"}, "breaks": set(),
                                     "edits_oracle": False, "touches": {"roadmap"}, "mutation_survives": False},
    "ADV-edits-the-oracle":        {"provides": {"preserve:method-id"}, "breaks": set(),
                                     "edits_oracle": True,  "touches": {"roadmap"}, "mutation_survives": True},
}
ALLOWED_PATHS = {"roadmap"}

def gate(fix, oracles):
    if fix["edits_oracle"]:
        return "STOP", "edits a frozen oracle/spec (reward-hacking guard)"
    if not fix["touches"] <= ALLOWED_PATHS:
        return "STOP", "touches paths outside authority"
    flipped = [oid for oid, o in oracles.items() if o["state"] == "RED" and o["asserts"] <= fix["provides"]]
    if not flipped:
        return "STOP", "no currently-RED signed oracle is satisfied by this fix"
    broken = sorted(oid for oid, o in oracles.items() if o["state"] == "GREEN" and (fix["breaks"] & o["asserts"]))
    if broken:
        return "STOP", f"would regress GREEN oracle(s) {broken}"
    authorized = set(chain.from_iterable(oracles[oid]["authorizes"] for oid in flipped))
    unauthorized = fix["provides"] - authorized
    if unauthorized:
        return "STOP", f"unauthorized behavioral delta {sorted(unauthorized)} (behavioral-delta containment)"
    if not fix["mutation_survives"]:
        return "STOP", "fix overfits the oracle — mutation/differential check failed"
    return "AUTO_FIX", f"flips RED→GREEN {sorted(flipped)}"

def run(label, oracles, cases):
    print(f"\n══ {label} ══")
    auto, stop = [], []
    for fid, fix in cases.items():
        action, why = gate(fix, oracles)
        (auto if action == "AUTO_FIX" else stop).append(fid)
        if action == "AUTO_FIX" or fid in ("F1", "F16", "F6", "F3") or fid.startswith("ADV"):
            print(f"  {fid:28} -> {action:9} {why}")
    print(f"  AUTO_FIX={auto or '∅'}   STOP={len(stop)} findings")
    return set(auto)

# Lexical router's false-autos for contrast (from empirical_gate.py):
LEXICAL_FALSE_AUTO = {"F1", "F16"}

print("Frozen-oracle gate — does oracle-gating close the F1/F16 wall?")
print(f"(lexical router false-auto'd {sorted(LEXICAL_FALSE_AUTO)})")

a1 = run("Test 1 — M1 = real executable acceptance commands, impl COMPLETE (all oracles GREEN)", M1, FINDINGS)
a2 = run("Test 2 — M2 = mid-drive, stronger oracles for method-id & kind-guard are RED (+adversarials)",
         M2, {**FINDINGS, **ADV})

print("\n══ Verdict ══")
t1_ok = (a1 == set())                                   # post-convergence: nothing is auto-eligible
t2_real_auto = a2 & set(FINDINGS)
t2_adv_auto = a2 & set(ADV)
f1f16_stop = not ({"F1", "F16"} & a2)
adv_all_stop = (t2_adv_auto == set())
print(f"Test 1: auto-apply set = {a1 or '∅'}  → {'all review findings STOP (no executable oracle covers them)' if t1_ok else 'UNEXPECTED'}")
print(f"Test 2: real fixes auto-applied = {sorted(t2_real_auto)} (the ones whose stronger oracle was RED)")
print(f"        F1/F16 STOP under oracle-gating: {f1f16_stop}   adversarials all STOP: {adv_all_stop} ({sorted(t2_adv_auto) or 'none auto'})")
print(f"        false-auto (any adversarial or F1/F16 auto-applied): {sorted((t2_adv_auto) | ({'F1','F16'} & a2)) or 'NONE'}")
PASS = t1_ok and f1f16_stop and adv_all_stop and (t2_real_auto == {"F3", "F6"})
print(f"\nORACLE-GATE: {'PASS ✅ — false-auto=0; F1/F16 closed by construction; residual is oracle COVERAGE' if PASS else 'CHECK'}")
print("Finding: against the roadmap's REAL acceptance oracles, oracle-gating auto-applies NOTHING")
print("(Test 1) — the review findings are all about behavior no signed oracle asserts. Auto-apply")
print("does work only where a stronger oracle is RED (Test 2: F3, F6); F1/F16 and every adversarial")
print("(wrong-but-green, unauthorized-delta, overfit, oracle-edit) STOP. The residual moved from")
print("'semantic mapping' to 'oracle coverage' — improvable by authoring stronger oracles at sign-off.")
