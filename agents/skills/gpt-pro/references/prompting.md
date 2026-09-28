# Conditional prompt guidance

## Grounding external facts

Web research is one of gpt-pro's **two first-class modes** (alongside deep reasoning), not an
afterthought — but it stays **conditional**. Local context is pasted in (above); **public,
external facts are searched for.** When the answer turns on information not in the pasted
context, GPT-Pro must search the web and ground its answer in cited sources. The directive below
is **conditional** — a no-op on pure-reasoning tasks — so include it in `prompt.md` whenever the
task could depend on external facts. Paste it verbatim:

```text
## Grounding external facts

Some questions turn on facts not in the pasted context — current versions, releases, dates,
prices, API/library behavior, specs, benchmarks, CVEs, recent events, current best practices:
anything that changes over time or that you'd otherwise answer from memory. For any such fact
you MUST use web search and ground the answer in what you find — do not answer external or
time-sensitive questions from memory.

When you search:
- Corroborate each load-bearing fact across at least two independent sources (prefer
  primary/official). If sources conflict or only one exists, say so and mark it low-confidence.
- Cite the specific page URL you actually opened, inline next to the claim — never a homepage,
  a search-results page, or a URL reconstructed from memory. Didn't open it? Don't cite it.
- End with a `## Sources` list: every URL you opened, each with one line on what you took from it.

Do NOT search when the task is self-contained — pure reasoning, math, or analysis of the pasted
code/text — or to confirm stable facts you already know. If you didn't need external facts, say
so in one line ("No external sources needed — reasoning over the pasted material.") rather than
just omitting citations: that line tells the caller a deliberate skip from a missed one.
```

**On return**, verify grounding cheaply: a fact-dependent answer should carry inline URLs and a
`## Sources` list — spot-check one or two with the Read/WebFetch tools (does the page resolve,
does it actually say that) before relying on it. A fact-heavy answer with no sources *and* no
"no external sources needed" line is ungrounded — re-prompt or discount it.

## Calibration block

For **judgment tasks** — analysis, recommendations, design, second opinions — have gpt-pro end
with a reasons-based calibration block. Its slowness and cost make a self-graded score *more*
tempting and *no* better calibrated, so ask for assumptions and failure modes, not a number.
**Skip it for deterministic lookups or mechanical transforms.** Paste this into `prompt.md`
(alongside the grounding directive when both apply):

```text
## Calibration

End your response with this block exactly:
- Key assumptions: 1-3 the answer depends on ("none material" only if true)
- Most likely wrong because: the strongest failure mode, missing info, or counterargument
- Would change my conclusion: the specific fact, test, or counterexample that would flip it
- Best next check: the single source, test, or lookup that would most reduce uncertainty
- Verify before acting: specific current/high-stakes claims to check ("none" for pure reasoning)

No numeric %, probability, star rating, or High/Medium/Low label — this block is for routing and
verification, not a calibrated probability.
```

**On return**, treat it as the action plan: run the `Best next check` and verify the listed
claims before relying on the answer. Because a re-query costs another run (5–20 min, up to
1–2 hours), a targeted check is almost always cheaper than re-running. Discount any answer that self-asserts
confidence in place of naming its assumptions.
