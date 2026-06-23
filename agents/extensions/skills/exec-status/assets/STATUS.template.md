# STATUS — <plain-English one-line goal, no jargon>

Health: <ON TRACK | WATCH | BLOCKED | DONE | UNKNOWN> — <one-line plain reason> · Fresh as of: <YYYY-MM-DD HH:MM TZ>

## Bottom line
<2 sentences, decision-grade answer first (not background): how it's going, why, and the single most important
thing right now. If `Needs a human?` is not "none", say the ask here too. A stranger reads only this and is 80%
oriented. No unexplained terms.>

## Should you be worried?
<No — because <…>. / Yes — <what it is, and what we'd do about it>.
If nothing is wrong, name what has NOT been tested or proven yet, so "all clear" stays honest.>

## What we've found so far
- **<plain-English finding that changes the goal, risk, choice, or next step>** — <so what: why it matters to a non-expert, one sentence>.
  Checked against: <a handle a skeptic could verify, e.g. "experiment 21 in results.tsv">. Confidence: <early | moderate | strong> (<plain gloss, e.g. "seen once only">).
- <…keep to about 3; gloss every model/dataset/method/metric name the first time it appears>

## Where we are
- Progress: <OPTIONAL — include only when the run has a finite, decision-relevant scope. One line, no sub-bullets; count outcomes not activity ("3 of 4 gates passed", never "ran 47 commands"); point at the operator checklist instead of pasting its rows, e.g. "7 of 10 services migrated; the 3 remaining include the only high-risk one. Full checklist: TODO.md". OMIT entirely for open-ended/exploratory work — a forced or stale count manufactures false precision.>
- Done: <highest-level completed milestone, in plain words>
- Now: <current activity; say plainly if waiting on a long-running job>
- Next: <next meaningful step or decision>
- Needs a human? <none | the specific decision or input required>

## How current is this
Last checked against: <the latest durable evidence this report reflects — a result row, commit, run, test, or source>
Out of date if: <the next durable event, threshold, or result that could change the stakeholder answer>

## For the AI — skip if you're the human
<!-- For the next model after a context reset, not the CEO. Never put commands the human should run here. -->
- You are maintaining this file as a live, plain-English executive briefing. If you're reading it on resume or after a context reset, treat this as your re-brief: reconcile every section against reality (via the checks below) before continuing. The rules below are the whole discipline — you need nothing else. The human owns no maintenance burden — your job is to earn their silence: they should only ever read this file or answer a specific `Needs a human?` ask, never nudge you to update it.
- Update whenever the answer a stakeholder would give changes: a finding lands / is reproduced / is overturned, a phase or experiment completes, a blocker appears or clears, or Health would change. Skip routine commands that change nothing a stakeholder cares about.
- Edit the section that changed in place (don't rewrite the whole file) and move the three freshness lines (Fresh as of / Last checked against / Out of date if) together — never bump the time without re-checking the evidence boundary. Full reconcile on resume, at phase boundaries, and when control returns from a long command.
- Keep it plain and small: gloss every model/dataset/method/metric on first use, never paste logs or tables, prefer UNKNOWN to optimism. This is a one-screen snapshot you overwrite, not a log — replace stale findings (keep ~3), don't accumulate, and never add a history section.
- The `Progress:` line in `Where we are` is optional: keep it only when scope is finite and decision-relevant, count CEO-relevant outcomes, cite the durable source of truth, and never duplicate `TODO.md`, experiment tables, logs, or history. Drop it for open-ended work — a stale count is false precision, and detailed per-item counting belongs in `todo`/`TODO.md`, not here.
- Health: default toward WATCH/UNKNOWN and treat ON TRACK/DONE as claims that must be earned (an always-green run is a warning sign). ON TRACK only with an explicit success criterion met by current evidence; WATCH for mixed/thin evidence; BLOCKED when stuck; DONE when the goal is met and verified; UNKNOWN when the goal/baseline/eval isn't established. Confidence on a finding: early = seen once; moderate = reproduced once or corroborated; strong = reproduced under the intended comparison and not contradicted.
- Check before trusting/continuing: <files or commands, e.g. results.tsv, run.log, git log --oneline -5>
- Keep this section current as the evidence boundary shifts (new files, commands, or checkpoints).
