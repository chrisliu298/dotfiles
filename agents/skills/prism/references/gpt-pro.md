# GPT-Pro tier — mechanics

Read this when a run has `M > 0` (you decided to add gpt-pro lenses), **before authoring the `Type: gpt-pro` dispatch records or launching**. The hot decision — whether to add gpt-pro, and the posture that matches the binding axis — stays in SKILL.md (*Choosing N and gpt-pro* and *Agents and lanes → GPT-Pro tier*); this file owns the record format, launch command, notification accounting, and recovery.

`prepare` validates every gpt-pro record fail-closed (posture enum, key names, declared references, 5 MB caps), so a mistake here surfaces as a `prepare` bounce, not a silent defect.

## Declaring lenses in the dispatch

**Declare gpt-pro lenses in the dispatch file — `prepare` composes the launcher; you never hand-inline.** Add one `Type: gpt-pro` record per lens (`Lens` + `Lens-Desc`, optional `Posture: deep-reasoning|research-grounded`). gpt-pro runs in a web tab and **cannot read any local file**, so `prepare` builds a self-contained launcher = template header (anti-recursion guard line 1 + lens) + the frozen packet verbatim (which already carries Grounding) + every reference file's contents + the calibration block. Reference list: the dispatch `Reference:` keys when present, else the packet's `### Reference Materials`. **With no reference source at all, `prepare` defaults to packet-only and prints a non-blocking warning** — a self-contained packet is valid gpt-pro input (it gets the full frozen packet inlined, exactly what `Reference: none` makes explicit), so a zero-file gpt-pro run is **not** a bounce. Any *declared* reference is still validated fail-closed (missing/dir/unreadable/whitespace path, or any single ref or composed prompt over the 5 MB cap, aborts *before* any quota).

```text
Shared-Packet: /tmp/prism-<id>.md
# roster contract still REQUIRED; set Prism-M to the gpt-pro count.
# For a gpt-pro-ONLY run use Prism-N: 0 and Prism-M >= 1. (Standard-tier records omitted here.)
Prism-Mode: full
Prism-N: 1
Prism-M: 1
# Reference: is OPTIONAL — omit it and gpt-pro gets the shared packet ONLY (prepare warns, no error).
# Prefer attaching files with Include: lines (it feeds gpt-pro's inline list too). `none` = packet only.
# Reference: /abs/path/1

Type: gpt-pro
Lens: Deep-Reasoning
Lens-Desc: weigh the hardest end-to-end reasoning
Posture: deep-reasoning
```

Inline `#` comments belong on their **own line** — the dispatch parser only treats a line whose first non-space character is `#` as a comment, so `Prism-M: 1  # note` would make the value `1  # note` and bounce. (`scaffold` already emits comments this way.) **Fastest path:** `scaffold --m <M>` (added to any scaffold form) emits `M` ready `Type: gpt-pro` records with canonical postures; `--n 0 --m <M>` scaffolds a gpt-pro-only run (`Prism-N: 0`, legal only with `M ≥ 1`).

## Posture

gpt-pro has two first-class families — **Deep-Reasoning** and **Research-Grounded**. For `M=1` pick the posture matching the binding axis; for `M=2` pair one of each (e.g. `Depth-Weighted` + a web-tilted `Research-Grounded`); for `M≥3` add distinct postures, never copies. Names must stay distinct across the whole run.

## Launch

**Launch** the exact line `prepare` printed — one backgrounded Bash call per lens, concurrently with the parallax fan and Agent calls:

```bash
gpt-pro < /tmp/prism-<id>-gpt-pro-<slug>.md > /tmp/prism-<id>-gpt-pro-<slug>.res.md 2> /tmp/prism-<id>-gpt-pro-<slug>.log
```

with `run_in_background: true`, `timeout: 7260000` (fall back to `~/.claude/skills/gpt-pro-relay/scripts/gpt-pro` if not on PATH). Each is its **own** completion notification — `prepare`'s printed count includes them.

## Collect + recover

**Collect** with `prism-launch results`/`digest` (both read the gpt-pro lane; gpt-pro is its own `GPT-Pro` digest lineage). **`PL results <manifest>` is the authoritative lane status and the first move on any suspected lens failure** — never the Bash task's `.output`, never the run dir. It already draws the distinction that matters: `[pending]` + exit 2 = **still running, NOT a failure** (a queued lens can sit 15+ min before `sent` — 961 s observed on a live worker misread as lost), `[FAILED]` + exit 1 = finished and needs action, printed with the recovery row for the exit code observed.

**Recovery:** each gpt-pro Bash call is a *Bash* task, so reading its `.output` for the `run_id=` line is correct and required (the "never read a subagent's `.output`" rule does **not** apply here) — but the run-id is the **only** thing it is for; never infer lane state from task output. For the `reason` behind an exit 1, follow the [[gpt-pro-relay]] exit-code table (README summarizes it).

**A gpt-pro lens whose run returns `status: error` is VOID.** It contributes nothing. It is never reconstructed from `run_dir`, and a failed run's answer file never enters the digest, the tally, or the synthesis — **however complete, well-formed, and on-topic it reads**. Quality is not evidence of provenance: the audit voids an answer because it cannot attribute it to the model dispatched, not because the text is bad (a real incident: a complete 13k-char answer served by GPT-5.5 Pro instead of Sol). The engine now quarantines the artifact itself: the body is published under a name its outcome earned, and **`response.md` exists only on `status: "ok"`** — a rejected model audit lands at `response.rejected.md`, a timeout at `response.partial.md`, a run that died before any verdict at `response.pending.md`, and a failure before extraction publishes nothing. So on a *failed* lens there is no `response.md` to salvage at all, and reading the body takes deliberately naming a file marked rejected/partial/pending. Treat the guardrail as a backstop, not the rule: the rule is that a `status: error` lens is void **whatever** its body is called. Options are exactly: (a) resubmit as a fresh run with a new run-id (re-burns 5–20 min of Pro quota → **the user decides**), or (b) an explicitly user-authorized `Prism-Mode: partial`. Silently proceeding, or backfilling with the quarantined artifact, is the defect. This upholds the engine's invariant — *"Never return an answer from a model we haven't verified: a served slug outside `PRO_MODEL_SLUGS` is fatal"* (gpt-pro `CLAUDE.md`) — and the audit has **no override flag, by design**; `cat`-ing the run dir is hand-rolling one.

**Never raise `GPT_PRO_MAX_PARALLEL` from prism** (account anti-abuse risk).
