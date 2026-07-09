## Grounding external facts

Some questions turn on facts not in the pasted context — current versions, releases, dates,
prices, API/library behavior, specs, benchmarks, CVEs, recent events, current best practices:
anything that changes over time or that you'd otherwise answer from memory. For any such fact
you MUST use the web to ground the answer in what you find — do not answer external or
time-sensitive questions from memory.

Reach the web with whatever your harness provides. **In the Claude Code harness — Claude
subagents and the GLM / Kimi / DeepSeek / MiMo relay peers — use the native `WebSearch` /
`WebFetch` tools; if one does not work (unavailable, errors, or returns no real results),
use Jina instead** via Bash:
- search (needs `JINA_API_KEY`): `curl -s 'https://s.jina.ai/<URL-encoded query>' -H 'Accept: application/json' -H "Authorization: Bearer $JINA_API_KEY"`
- fetch: `curl -s -X POST 'https://r.jina.ai/' -H 'Content-Type: application/json' -H 'Accept: application/json' ${JINA_API_KEY:+-H "Authorization: Bearer $JINA_API_KEY"} -d '{"url":"<url>"}'`

**Codex, Grok, and gpt-pro** run their own harness with their own native web search/fetch — use those directly; the `WebSearch` / `WebFetch` and Jina details above are Claude-Code-only. Either way, what matters is that the fact is grounded in a live source.

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
