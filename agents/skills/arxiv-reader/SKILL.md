---
name: arxiv-reader
user-invocable: true
description: Read an arxiv paper from its TeX source for exact math, tables and figures. Use for an arxiv URL or an ID like "2401.12345", or a request to explain a paper.
allowed-tools: Bash(curl:*), Bash(file:*), Bash(tar:*), Bash(mkdir:*), Bash(mv:*), Bash(rm:*), Bash(head:*), Bash(defuddle:*), Read, Grep
---

# Arxiv Reader

Read arxiv papers and respond conversationally. The goal is to build grounded access to the paper's content so the assistant can answer the user's question accurately.

This skill is a paper reader, not a note generator. Don't produce a structured summary unless the user asks for one. Just load the paper and respond to whatever they need.

## Workflow

### Step 2: Fetch the Paper

Use a cascading strategy — try each method in priority order and fall through on failure. Use the highest-fidelity method that yields validated, readable paper content.

Paths below use `/tmp`; when the harness provides a session scratch directory, use it instead.

**Rate limiting**: arxiv.org rate-limits automated requests. If you get a 429 response or an HTML "access denied" page, wait a few seconds and retry once, then fall through to the next method.

Read the following procedures from this skill root only as their step is reached.
Task downloads and extracted papers stay in the session scratch directory or
`/tmp`, not the installed skill's `references/` directory.

1. Before fetching, read [Identify the paper](references/identify.md): preserve the requested version, sanitize legacy ids only for filesystem paths, and resolve ambiguity before selecting a paper.
2. Fetch in order: [TeX source](references/tex.md) → [HuggingFace markdown](references/huggingface.md) → [arxiv HTML](references/html.md) → [PDF](references/pdf.md). Start with TeX; read each later method only if the previous one fails its checks. Follow the chosen method's validation, not just its HTTP status.
3. Before answering, read [Validate, respond, figures and cleanup](references/respond.md). Match the user's question, retain equation-fidelity limits, open a figure when needed, and clean up only the paper's temporary files after the conversation is done.

Do not answer from an error page or metadata-only response. If all methods yield
partial/degraded content, explain what is missing. This skill reads arxiv papers;
other PDFs are read directly.
