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
   - Skip `.sty`, `.cls`, `.bst`, `.aux`, `.out`, `.log`, `.toc`, `.synctex`, and `.blg` build files. Don't read figure images up front; open one when a question depends on it
   - **Context budget**: If the combined `.tex` files are very large, prioritize: abstract, introduction, method, experiments/results, and conclusion. Defer appendices and supplementary material unless the user asks about them. For a targeted question, locate the relevant section first before loading everything.
6. **Note the structure**: Track `\section{}`, `\subsection{}`, `\begin{theorem}`, `\begin{figure}`, etc. to navigate the paper when answering questions

