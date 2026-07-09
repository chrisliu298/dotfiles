#!/usr/bin/env python3
"""goal-loop empirical gate — replays the real roadmap review (18 findings) through the
deterministic finding router. Auto-apply MUST NOT be enabled until this PASSES (false-auto == 0,
the loud NO-SHIP F8 → STOP, refactors not auto-applied).

CURRENT VERDICT: **FAIL** → goal-loop ships **report-only** (auto-apply disabled). The lexical
router clears every other check but false-autos F1 and F16: each names a real code identifier
(`load_items`, `classify_method`) that also appears in an acceptance criterion, yet addresses a
DIFFERENT, unmapped concern — lexically indistinguishable from a true map. Stopword tuning cannot
fix this (it is semantic, not lexical). A lexical router alone therefore cannot reach false-auto=0;
the live executed-RED→GREEN-test backstop (validated against the real code, not in this offline
harness) is the necessary second gate before auto-apply can be considered.

Note on routing: with no human in the loop, this harness scores `in_scope-unmapped` as STOP (in the live
skill those are *surfaced* in the actionable batch for the human). F8 (the loud NO-SHIP) STOPs as
`in_scope-unmapped` — the right *action* the human took (out-scope), reached for a different *reason*
(no covering AC) than the human's needs_user scope call. Run: python3 empirical_gate.py
"""
import re
from collections import Counter

AC = {
  "C1":"Frontmatter canonical; method state lives in sidecar YAML; no JSON of record.",
  "C2":"Deterministic: no LLM call in build update today start method weekly; classify_method pure regex lookup.",
  "C3":"Non-destructive: never modify a user's source study notes.",
  "C4":"No-clobber on rebuild: method-stage and method-evidence are user-owned and MUST survive build via rmlib._PRESERVED_KEYS; a method-id set override must persist.",
  "C5":"Single renderer: cmd_build.build stays the only renderer; loop commands finish by calling it.",
  "C6":"WIP discipline: today shows at most one method-next line per active item.",
  "C7":"Method notes are not items: playbooks carry keyword/roadmap-method; load_items skips them; not mintable; extend _is_tracking_note _ROADMAP_PREFIXES.",
  "C8":"No overclaim: do not assert the layer improves learning; weekly metrics descriptive.",
  "P1":"parse_playbooks returns the 5 method-ids with stages; codebase-system has >=6 stages; validate_tags ok.",
  "P2":"classify_method routes 5 material types plus unset; method-stage method-evidence in _PRESERVED_KEYS.",
  "P3":"start stamps method-id method-stage 1; method command show advance --evidence set; refuse advance without evidence; set resets method-stage to 1; exclude playbooks from mint.",
  "P4":"today renders one method-next line; complete adds a non-blocking advisory warning when method-stage below last stage.",
  "P5":"weekly method metrics with-vs-unset stalled-at-stage time-to-first-evidence pass-rate-by-method; tests.",
  "P6":"no-clobber build preserves method-stage and method-evidence; docs in SKILL README; check-state exits 0.",
}
FINDINGS = [
  ("F1","blocker","load_items reads method-evidence and method-stage raw, so a hand-edited string explodes into list of chars and a non-numeric stage crashes","parse the fields through the schema loader before use","unmapped"),
  ("F2","should","method set with the same method-id silently wipes method-stage and method-evidence","on set to the current method-id warn and preserve stage and evidence instead of resetting","mapped"),
  ("F3","should","method and start stamp method-id and method-stage on non unit item kinds like artifact and gate","guard so only kind in unit or item gets method fields","mapped"),
  ("F4","should","method cursor math is triplicated and the incomplete warning reads an unclamped method-stage","centralize the cursor clamp so the warning uses the clamped value","unmapped"),
  ("F5","could","dead parse_playbooks binding left in weekly","remove the unused parse_playbooks call in weekly","out_of_scope"),
  ("F6","should","method-id is not in _PRESERVED_KEYS so a user set override can be regenerated away","add method-id to _PRESERVED_KEYS once set","mapped"),
  ("F7","should","pre-layer started items never receive a method-id without a migration that resets review dates","add a one-off migration to stamp method-id on already-started items","needs_user"),
  ("F8","blocker","malformed YAML makes parse_frontmatter return empty so build wipes all preserved sidecar state","make parse_frontmatter fail closed and keep prior state on a parse error","needs_user"),
  ("F9","should","method set destroys method-evidence on a genuine method switch","decide whether a real method switch preserves or clears evidence","needs_user"),
  ("F10","should","an unparseable method-stage is coerced to 1 on rebuild silently losing the cursor","surface a bad method-stage instead of coercing to 1","unmapped"),
  ("F11","should","orphan cleanup deletes a sidecar that still carries method state","make _cleanup_orphans aware of method state","out_of_scope"),
  ("F12","could","final-stage method-evidence has nowhere to go and the cursor off-by-one semantics are ambiguous","clarify the final-stage cursor semantics","out_of_scope"),
  ("F13","should","a playbook stage-count shrink leaves a stale over-cursor persisted in the sidecar","clamp the persisted method-stage when the playbook shrinks","unmapped"),
  ("F14","should","a missing or deleted playbook gives an unhelpful error and a silent cockpit","emit a clear error when a referenced playbook is missing","unmapped"),
  ("F15","could","there is no command path to set a method back to unset","allow method set unset","unmapped"),
  ("F16","should","classify paper-concept is weak on real titles because the url is never extracted","extract the url for classify_method on real items","unmapped"),
  ("F17","could","cockpit rendering is duplicated across render_today and today","de-duplicate the today and render_today rendering","out_of_scope"),
  ("F18","could","weekly is a god-function with regex sprawl start double-reads the sidecar and mtime uses float vs ns without fsync","refactor weekly single-read start fix mtime fsync durability","unmapped"),
]
STOP=set("a an the of to in on for and or but is are be by it its with as at from that this not no never only one per so do does add make use used set get keep stop should must may can into out off up down when where while which what who whose real really below above same other another various given since both each any all some most more less than then else even still yet a so".split())
GEN=set("method method-id stage state build item items unit units sidecar field fields evidence note notes playbook playbooks user command rebuild loop today render renderer line value values preserve preserves preserved clears clear wipe wipes lose loses warning warn".split())
KNOWN=set("classify_method parse_playbooks parse_frontmatter _preserved_keys _track_keys load_items cmd_build.build write_tracking_note read_tracking_note _cleanup_orphans _is_tracking_note _roadmap_prefixes method-stage method-evidence method-id validate_tags review_log _mint_item valid_evidence render_today".split())
def ident(t): return ("_" in t) or ("." in t) or (t.startswith("method-")) or (t in KNOWN)
def terms(x):
    toks=re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]*[A-Za-z0-9_]|[A-Za-z]+",x.lower())
    return {t for t in toks if t not in STOP and len(t)>2}
AT={k:terms(v) for k,v in AC.items()}
DF=Counter()
for ts in AT.values():
    for t in ts: DF[t]+=1
def distinct(t): return DF.get(t,0) and DF[t]<=2 and t not in GEN and ident(t)
ONE=re.compile(r"\b(delete|drop|migrat|deploy|publish|reset review|resets review)",re.I)
NEEDS=re.compile(r"\b(decide whether|choose whether|whether a |whether the |clarify|policy)",re.I)
REF=re.compile(r"\b(refactor|de-?duplicat|dedupe|centralize|simplif|god-function|sprawl|clean ?up)",re.I)
def route(fid,sev,claim,fix):
    if ONE.search(fix): return "STOP","needs_user"
    if NEEDS.search(fix) or NEEDS.search(claim): return "STOP","needs_user"
    if sev=="could": return "DEFER","out_of_scope"
    if REF.search(fix) or REF.search(claim): return "DEFER","out_of_scope"
    ft=terms(claim+" "+fix)
    hits={ac:{t for t in (ft&ats) if distinct(t)} for ac,ats in AT.items()}
    hits={a:s for a,s in hits.items() if s}
    if not hits: return "STOP","in_scope-unmapped"
    common=set.intersection(*hits.values()) if len(hits)>1 else next(iter(hits.values()))
    if len(hits)>1 and not common: return "STOP","needs_user"  # ambiguous: different subjects
    if len(fix.split())<3: return "STOP","in_scope-unmapped"
    return "AUTO_FIX","in_scope-mapped"

auto=set();defer=set();stop=set();rows=[]
for fid,sev,claim,fix,gold in FINDINGS:
    a,sc=route(fid,sev,claim,fix); rows.append((fid,sev,gold,a,sc))
    (auto if a=="AUTO_FIX" else defer if a=="DEFER" else stop).add(fid)
SAFE={"F2","F3","F6"};REFC={"F5","F17","F18"};MUST={"F8","F7","F9"};fa=auto-SAFE
for fid,sev,gold,a,sc in rows:
    fl="  <<FALSE-AUTO" if (a=="AUTO_FIX" and fid not in SAFE) else ("  ok-recovered" if a=="AUTO_FIX" else "")
    if fid=="F8": fl+="  <== loud NO-SHIP"
    print(f"{fid:4}{sev:8}{gold:13}-> {a:9}{sc:18}{fl}")
print(f"\nAUTO={sorted(auto)}  DEFER={sorted(defer)}  STOP={sorted(stop)}")
print(f"false-auto={sorted(fa) or 'NONE'} | F8 stop={'F8' in stop} | refactor safe={not(REFC&auto)} | needs_user stop={MUST<=stop} | recall(auto∩safe)={sorted(auto&SAFE)}")
PASS=(not fa) and ("F8" in stop) and not(REFC&auto) and MUST<=stop and bool(auto)
print("v2 GATE:", "PASS" if PASS else "FAIL")
