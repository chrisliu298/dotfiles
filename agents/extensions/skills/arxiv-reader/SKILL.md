---
name: arxiv-reader
user-invocable: true
description: Read arxiv papers by fetching their original TeX source for full-fidelity access to math, tables, and figures. Use whenever the user shares an arxiv URL or paper ID and wants to discuss, understand, or ask questions about the paper — even if they don't say "read". Triggers on arxiv URLs (abs, pdf, html), bare arxiv IDs like "2401.12345", or phrases like "read this paper", "what does this paper say", "explain this arxiv paper", "go through this paper". Also use when the user pastes an arxiv link alongside a question. Do NOT use for generating Obsidian notes (use /note-gen instead) or for citation management (use /citation-assistant).
effort: high
allowed-tools: Bash(curl:*), Bash(file:*), Bash(tar:*), Bash(mkdir:*), Bash(mv:*), Bash(rm:*), Bash(head:*), Bash(defuddle:*), Read, Grep
---

# Arxiv Reader

Read arxiv papers and respond conversationally. The goal is to build grounded access to the paper's content so the assistant can answer the user's question accurately.

This skill is a paper reader, not a note generator. Don't produce a structured summary unless the user asks for one. Just load the paper and respond to whatever they need.

## Workflow

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

### Step 2: Fetch the Paper

Use a cascading strategy — try each method in priority order and fall through on failure. Use the highest-fidelity method that yields validated, readable paper content.

**Rate limiting**: arxiv.org rate-limits automated requests. If you get a 429 response or an HTML "access denied" page, wait a few seconds and retry once, then fall through to the next method.

#### Method 1: TeX Source (preferred)

TeX source gives the highest fidelity — math is in native LaTeX notation, tables and figures are structured, and there are no conversion artifacts.

1. **Download**: `curl -fL -o /tmp/{id}.tar.gz https://arxiv.org/src/{id}`
   - `-f` makes curl return non-zero on HTTP errors (404, 429, etc.)
   - If curl fails → fall through to Method 2
2. **Validate** — run `file /tmp/{id}.tar.gz` and check the output:
   - Contains `gzip` → proceed to step 3
   - Contains `tar` (but not gzip) → uncompressed tar, use `tar -xf` instead of `tar -xzf` in step 3
   - Contains `LaTeX` or `ASCII text` or `UTF-8 Unicode text` → single `.tex` file: `mkdir -p /tmp/arxiv-{id} && mv /tmp/{id}.tar.gz /tmp/arxiv-{id}/main.tex` → skip to step 4
   - Contains `HTML` or `XML` → arxiv returned an error page, not source → fall through to Method 2
   - Anything else → fall through to Method 2
3. **Unpack**: `rm -rf /tmp/arxiv-{id} && mkdir -p /tmp/arxiv-{id} && tar -xzf /tmp/{id}.tar.gz -C /tmp/arxiv-{id}`
4. **Find the entrypoint**: Grep for `\documentclass` in `/tmp/arxiv-{id}/`:
   - If exactly one match → that's the main file
   - If multiple matches → prefer files named `main.tex`, `paper.tex`, or `ms.tex`; then prefer the file that also contains `\begin{document}`; exclude commented-out `\documentclass` lines (leading `%`)
   - If zero matches → the tarball may not contain usable source, fall through to Method 2
5. **Read the paper**:
   - Read the entrypoint `.tex` file
   - Follow `\input{}`, `\include{}`, `\subfile{}`, and `\import{}` directives to read referenced `.tex` files. Resolve relative paths from the including file's directory; try both the literal path and with `.tex` appended.
   - Read `.bib` or `.bbl` files if the user asks about references/citations
   - Skip `.sty`, `.cls`, `.bst`, `.aux`, `.out`, `.log`, `.toc`, `.synctex`, `.blg`, and image files (`.png`, `.jpg`, `.pdf`, `.eps`, `.svg`) — these are style/build/binary files, not content
   - **Context budget**: If the combined `.tex` files are very large, prioritize: abstract, introduction, method, experiments/results, and conclusion. Defer appendices and supplementary material unless the user asks about them. For a targeted question, locate the relevant section first before loading everything.
6. **Note the structure**: Track `\section{}`, `\subsection{}`, `\begin{theorem}`, `\begin{figure}`, etc. to navigate the paper when answering questions

#### Method 2: HuggingFace Papers Markdown

HuggingFace provides a clean markdown conversion of arxiv papers. It's pre-processed and easy to consume, but only works for papers indexed on `hf.co/papers` (many papers are not).

Strip the version suffix before querying HuggingFace — HF indexes by base ID only. For `2401.12345v2`, query `huggingface.co/papers/2401.12345.md`.

1. **Fetch and validate**:
   ```
   HTTP_CODE=$(curl -s -o /tmp/hf-{id}.md -w "%{http_code}" "https://huggingface.co/papers/{id}.md")
   ```
   - If `$HTTP_CODE` is not `200` → fall through to Method 3
   - If `200`, check content quality: valid markdown should contain section headings, an abstract or introduction, and substantial body text. If the file starts with `<!DOCTYPE` or `<html`, it's an HTML page, not markdown → fall through
2. **Read** the markdown file — it contains the full paper content with inline images as URLs, math as LaTeX, and clean section structure
3. If content is just the HF paper page metadata (no full paper body) → fall through to Method 3

#### Method 3: Arxiv HTML

Arxiv renders most papers as HTML via LaTeXML. This is a strong fallback when available, covering papers that aren't indexed by HuggingFace. Never rely on raw HTML as the primary reading format — always convert to markdown first.

1. **Fetch and convert to markdown** using any available page-to-markdown mechanism:
   - If `defuddle` CLI is available: `defuddle parse "https://arxiv.org/html/{id}" --md`
   - Otherwise use any web-fetching tool that converts HTML to markdown (WebFetch, Jina Reader at `r.jina.ai`, or similar)
   - If conversion yields mostly navigation/boilerplate with no real paper content, treat it as failed
2. **Validate**: The converted markdown should have section headings, body text, and recognizable paper structure. If it's truncated or garbled → fall through to Method 4
3. **If arxiv HTML returns 404** (very old papers without HTML rendering) → fall through to Method 4

#### Method 4: PDF (last resort)

Some older papers only have a PDF. This is the least preferred method because PDF parsing loses math notation fidelity and may introduce artifacts.

1. `curl -fL -o /tmp/arxiv-{id}.pdf https://arxiv.org/pdf/{id}`
2. Read the PDF. For long papers (>15 pages), start with the first 15 pages, then read additional pages as needed for the user's question.
3. Let the user know you're working from the PDF — prefer conceptual summaries over exact symbolic reconstruction when equation fidelity is unclear.

### Step 2.5: Validate Before Responding

Before answering, do a quick sanity check on the fetched content:
- Title/authors are present and match the requested paper
- Abstract or introduction is visible
- Section structure exists

If any of these fail, fall through to the next method rather than answering from bad content. If all methods produce partial or degraded content, tell the user which methods were tried, what's missing, and offer a best-effort answer with appropriate caveats.

### Step 3: Respond to the User

Briefly mention which source was used (e.g., "I loaded this from the TeX source" or "Reading the HuggingFace markdown version"). One sentence is enough — don't belabor it.

Respond based on what the user asked:

- **No specific question** (just shared a link): Give a brief 2-3 sentence summary of what the paper is about, then ask what they'd like to know. Don't dump a full summary unprompted.
- **Specific question**: Answer it directly, citing relevant sections and equations from the paper.
- **"Summarize this"**: Provide a structured summary with core thesis, method, key results.
- **"Explain section X"**: Go deep on that section, unpacking the math and intuition.
- **Follow-up questions**: Answer naturally from the loaded content.
- **Paper too long for context**: If only core sections were loaded, tell the user: "I've loaded the main sections. Ask about specific parts and I'll read those in detail."

**Math notation**: When the source is TeX or clean markdown, reproduce key equations using `$inline$` and `$$block$$` notation. Define variables after equations. When the source is HTML or PDF, only reproduce equations that are clearly intact — otherwise paraphrase the mathematical structure and note that notation may be lossy.

**Figures**: You can see figure captions and references in TeX source but cannot view actual images. When discussing figures, describe what the caption and surrounding text say. If the user needs to see a figure, point them to the arxiv HTML version or PDF.

### Handling Multiple Papers

If the user shares multiple arxiv papers in one conversation, fetch them in parallel when possible. Keep track of which paper is which — refer to them by first author and year (e.g., "Schulman 2017" vs "Ouyang 2022") to avoid confusion.

### Cleanup

After the conversation with a paper is done, clean up temp files: `rm -rf /tmp/{id}.tar.gz /tmp/arxiv-{id} /tmp/hf-{id}.md /tmp/arxiv-{id}.pdf`

## What This Skill Does NOT Do

- **Generate Obsidian notes** — use `/note-gen` for that. If the user asks to turn the paper into notes, answer the reading/explanation part here, then suggest `/note-gen` for the note.
- **Manage citations/BibTeX** — use `/citation-assistant` for that
- **Read non-arxiv papers** — this skill is specifically for arxiv. For other PDFs, read them directly.
