## Grounding external facts

Some questions turn on facts not in the pasted context — current versions, releases, dates,
prices, API/library behavior, specs, benchmarks, CVEs, recent events, current best practices:
anything that changes over time or that you'd otherwise answer from memory. For any such fact
you MUST use the web to ground the answer in what you find — do not answer external or
time-sensitive questions from memory.

Reach the web with whatever works in your harness: **if your `WebSearch` / `WebFetch` tools
return live results, use them.** Fall back to **Jina** via Bash when a tool is unavailable,
returns no live results, OR may be answering from training data rather than the live web (some
peers' native search is silently stale — you can't always tell; when in doubt on a
time-sensitive fact, use Jina):
- search (needs `JINA_API_KEY`): `curl -s 'https://s.jina.ai/<URL-encoded query>' -H 'Accept: application/json' -H "Authorization: Bearer $JINA_API_KEY"`
- fetch: `curl -s -X POST 'https://r.jina.ai/' -H 'Content-Type: application/json' ${JINA_API_KEY:+-H "Authorization: Bearer $JINA_API_KEY"} -d '{"url":"<url>"}'`

Either path is fine; what matters is that the fact is grounded in a live source.

When you search:
- Corroborate each load-bearing fact across at least two independent sources (prefer
  primary/official). If sources conflict or only one exists, say so and mark it low-confidence.
- Cite the specific page URL you actually opened, inline next to the claim — never a homepage,
  a search-results page, or a URL reconstructed from memory. Didn't open it? Don't cite it.
- Include a `## Sources` list (immediately before your `## Digest`): every URL you opened, each with one line on what you took from it.

Do NOT search when the task is self-contained — pure reasoning, math, or analysis of the pasted
code/text — or to confirm stable facts you already know. If you didn't need external facts, say
so in one line ("No external sources needed — reasoning over the pasted material.") rather than
just omitting citations: that line tells the caller a deliberate skip from a missed one.
