---
description: |
  Fetch web page content or search the web via Jina AI (r.jina.ai / s.jina.ai).
  Use this skill when the built-in WebFetch tool fails, returns empty/garbage content,
  or when fetching from sites that need JS rendering: x.com/Twitter, Notion pages,
  SPAs, JS-heavy sites, PDFs at a URL, or any page behind Cloudflare. Also use when
  the user asks to search the web and you need grounded results with full page content
  (not just snippets). Triggers on "fetch this URL", "read this page", "search for",
  "what does this page say", or when you get a WebFetch error/empty result.
  Do NOT use for URLs that WebFetch already handles well (simple static HTML).
user-invocable: false
allowed-tools: Bash(curl:*)
effort: medium
---

# Jina

Fetch web content and search the web using Jina AI's Reader and Search APIs.

## When to use

- WebFetch returned an error, empty content, or garbled HTML
- The URL points to a JS-rendered page (x.com, Notion, SPAs, React/Vue apps)
- The URL points to a PDF
- You need web search results with full page content (not just titles/snippets)

## Reader — fetch a URL

```bash
curl -s -X POST 'https://r.jina.ai/' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'X-Timeout: 30' \
  ${JINA_API_KEY:+-H "Authorization: Bearer $JINA_API_KEY"} \
  -d '{"url": "TARGET_URL"}'
```

Always use POST (not the GET prefix `r.jina.ai/URL`) because GET silently drops `#` fragments, breaking SPA URLs.

### Response

JSON with `data.content` (markdown), `data.title`, `data.url`, `data.usage.tokens`.
Check `data.warning` — Reader returns HTTP 200 even when the target site errors (e.g., 404). A non-empty `warning` field means something went wrong.

### Useful headers

Add these as `-H 'Header: value'` to the curl command when needed:

| Header | When to use |
|--------|------------|
| `X-Wait-For-Selector: <css>` | SPA content loads after JS — wait for a specific element |
| `X-Target-Selector: <css>` | Extract only a specific part of the page |
| `X-Remove-Selector: <css>` | Strip navbars, ads, cookie banners before extraction |
| `X-No-Cache: true` | Need fresh content (default cache is ~1 hour) |
| `X-With-Links-Summary: true` | Append a list of all links found on the page |
| `X-With-Images-Summary: all` | Append a list of all image URLs (useful since images are lost in markdown) |
| `X-Retain-Images: none` | Strip all images to reduce output size |
| `X-Engine: direct` | Skip browser rendering (faster, but misses JS content) |

For **x.com/Twitter** specifically, add:
```
-H 'X-Wait-For-Selector: [data-testid="tweetText"]' \
-H 'X-With-Images-Summary: all'
```

## Search — web search with full content

```bash
curl -s 'https://s.jina.ai/QUERY_URL_ENCODED' \
  -H 'Accept: application/json' \
  -H "Authorization: Bearer $JINA_API_KEY"
```

An API key is **required** for search (free key works — get one at https://jina.ai/?sui=apikey).

Returns top 5 results, each with `title`, `content` (full page markdown), and `url`.

To restrict to specific sites, append `?site=example.com`.

## Parsing the response

Pipe through python to extract the content:

```bash
# Reader — extract markdown content
... | python3 -c "
import sys, json
r = json.load(sys.stdin)
d = r.get('data', {})
if d.get('warning'):
    print('WARNING:', d['warning'], file=sys.stderr)
print(d.get('content', d.get('text', '')))"

# Search — extract all results
... | python3 -c "
import sys, json
r = json.load(sys.stdin)
for i, item in enumerate(r.get('data', []), 1):
    print(f'## Result {i}: {item.get(\"title\", \"\")}')
    print(f'URL: {item.get(\"url\", \"\")}')
    print(item.get('content', ''))
    print()"
```

## Limitations

- **Images are lost** — pages convert to markdown text. Image URLs may appear via `X-With-Images-Summary` but the images themselves are not rendered.
- **Login-required pages fail** — Reader cannot authenticate. Paying more does NOT unlock more sites.
- **Bot-protected sites may fail** — Cloudflare challenges, aggressive CAPTCHAs. Reader does not bypass anti-bot measures.
- **Search costs 10K tokens minimum** per request regardless of output size.
- **Rate limits without key**: Reader ~20 RPM, Search blocked. With free key: Reader 500 RPM, Search 100 RPM.
