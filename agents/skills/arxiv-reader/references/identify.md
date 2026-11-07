### Step 1: Extract the Arxiv ID

Parse the arxiv ID from whatever the user provides. Strip query strings, anchors, and `.pdf` suffixes.

| Input format | Example | Extracted ID |
|---|---|---|
| Abstract URL | `arxiv.org/abs/2401.12345` | `2401.12345` |
| PDF URL | `arxiv.org/pdf/2401.12345` | `2401.12345` |
| HTML URL | `arxiv.org/html/2401.12345` | `2401.12345` |
| HuggingFace URL | `huggingface.co/papers/2401.12345` | `2401.12345` |
| Bare ID | `2401.12345` | `2401.12345` |
| Bare ID (old numeric) | `1706.03762` | `1706.03762` |
| Legacy ID (pre-2007) | `hep-th/9905111` | `hep-th/9905111` |
| With version | `2401.12345v2` | `2401.12345v2` |

For legacy IDs containing `/` (e.g., `hep-th/9905111`), use a sanitized form for filesystem paths: replace `/` with `_` (e.g., `hep-th_9905111` for temp directories). The URL `https://arxiv.org/src/hep-th/9905111` works as-is.

If the user provides a versioned ID (e.g., `2401.12345v2`), keep the version — it fetches that specific version. If no version is specified, arxiv returns the latest.

If the user gives a vague reference (paper title, author name) instead of a URL/ID:
1. Search the web for `site:arxiv.org <query>` using any available search tool. If no web search is available, try the Semantic Scholar API: `curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=URL_ENCODED_QUERY&limit=3&fields=externalIds,title"` and extract the arxiv ID from the response.
2. Extract the arxiv ID from the result
3. Confirm with the user if the match is ambiguous (multiple plausible results or title doesn't closely match the query). Proceed without confirming if there's exactly one clear match.

### Handling Multiple Papers

If the user shares multiple arxiv papers in one conversation, fetch them in parallel when possible. Keep track of which paper is which — refer to them by first author and year (e.g., "Schulman 2017" vs "Ouyang 2022") to avoid confusion.

