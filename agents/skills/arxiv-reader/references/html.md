#### Method 3: Arxiv HTML

Arxiv renders most papers as HTML via LaTeXML. This is a strong fallback when available, covering papers that aren't indexed by HuggingFace. Never rely on raw HTML as the primary reading format — always convert to markdown first.

1. **Fetch and convert to markdown** using any available page-to-markdown mechanism:
   - If `defuddle` CLI is available: `defuddle parse "https://arxiv.org/html/{id}" --md`
   - Otherwise use any web-fetching tool that converts HTML to markdown (WebFetch, Jina Reader at `r.jina.ai`, or similar)
   - If conversion yields mostly navigation/boilerplate with no real paper content, treat it as failed
2. **Validate**: The converted markdown should have section headings, body text, and recognizable paper structure. If it's truncated or garbled → fall through to Method 4
3. **If arxiv HTML returns 404** (very old papers without HTML rendering) → fall through to Method 4

