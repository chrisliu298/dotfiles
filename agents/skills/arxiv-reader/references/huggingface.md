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

