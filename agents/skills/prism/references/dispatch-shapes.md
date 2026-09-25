# Dispatch file — canonical example, key grammar, and what prepare enforces

Read this when hand-authoring a dispatch beyond what `scaffold` prints for you: custom lenses, `N > 1`, tier exclusions, a no-subagents or gpt-pro-only run, or recovering after a `prepare` bounce. For the common case, `scaffold --n <N>` (optionally `--preset <type>`, `--m <M>`, `--no-subagents`) prints a ready, canonical dispatch to stdout — copy from there. The dispatch is plain `Key: value` lines in blank-line-separated records — no braces/commas/quoting/escaping.

The partial-roster / `Variant: no-subagents` authorization rules stay in SKILL.md (*Execution Spine* → Roster contract) — that authority gate is prose-only (`prepare` records a `Partial-User-Quote` but cannot prove it), so it is not extracted here.

## Canonical default (both tiers at N=1, lenses from distinct axis families)

```text
Shared-Packet: /tmp/prism-<id>.md
Prism-Mode: full
Prism-N: 1
Prism-M: 0

Type: subagent
Lens: Simplicity
Lens-Desc: weigh the approach that requires the fewest moving parts

Type: parallax
To: gpt
Name: adversarial
Lens: Adversarial
Lens-Desc: weigh the strongest attacks on the proposal
```

## Key grammar

`Shared-Packet:` once; `Prism-Mode:` required. Optional top-level file keys: `Include:` (repeatable), `Include-Base:` (once), `Include-From:`/`Include-Tree:` (repeatable) — the ergonomic file front door (see SKILL.md *Shared Context* → Reference materials); mutually exclusive with `Reference:`. Each record starts at `Type: parallax|subagent|gpt-pro`; blank lines separate records; `#` begins a comment. `parallax` needs `To:`/`Lens:`/`Lens-Desc:` (`Name:` optional, defaults to the slugified lens); `subagent` needs only `Lens:`/`Lens-Desc:`; `gpt-pro` needs `Lens:`/`Lens-Desc:` + optional `Posture:` (`To:`/`Name:` rejected) — the `Type:` value must be the hyphenated `gpt-pro`; the hyphen-less `gptpro` and underscore `gpt_pro` spellings are rejected. **Never author `Effort:`** — `prism-launch` derives it and rejects the line. Everything after the **first** `:` is the literal value (quotes, colons, `>`, `<`, single braces fine) — except the reserved `</` and `{{` (injection guard), which `prepare` rejects.

## What prepare enforces (the --dispatch path)

So the SKILL.md prose can defer to it: packet has the required sections; no dispatch-only key misplaced in the packet body (`Include:`/`Include-*`/`Shared-Packet:`/`Prism-*`/`Variant:`/`Partial-User-Quote:` belong in the **dispatch** — in the packet they are inert and silently attach nothing, so `prepare` bounces before mutating it; fenced code blocks are exempt); canonical blocks injected; no surviving `{{slot}}`; each launcher's first line is `CRITICAL:`; dispatch shape valid (`Type`, `To` ∈ registry, required keys); `Prism-Mode: full` floor-checks every standard tier + subagents at N and gpt-pro at M, naming any offender; `Prism-Mode: partial` requires a non-empty quote; `Variant: no-subagents` (partial only, requires `Prism-N ≥ 1` + quote, rejected on `full`) floor-checks the parallax tier at N + **zero** subagents + gpt-pro at M, rejecting a smuggled subagent record; effort registry-derived (`Effort:` rejected); duplicate lens/relay-name/slug rejected; *declared* gpt-pro references + 5 MB caps validated (an **absent** reference source defaults to packet-only with a warning, not an abort); `N=0` legal only with `M ≥ 1`; malformed `.shape` rejected; injection tokens (`</`, `{{`) rejected; zero-records rejected. `parallax` refuses a manifest with no valid `.shape`.
