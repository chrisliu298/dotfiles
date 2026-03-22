# LaTeX to Typst Cheatsheet

Quick mapping of common LaTeX commands to Typst equivalents.

## Document structure

| LaTeX | Typst |
|-------|-------|
| `\documentclass{article}` | `#set page("a4")` + set rules (or use a template) |
| `\usepackage{...}` | `#import "@preview/pkg:ver"` or built-in |
| `\begin{document}` | Not needed — just start writing |
| `\title{...}` | `#set document(title: "...")` or template param |
| `\author{...}` | `#set document(author: "...")` or template param |
| `\maketitle` | Handled by template |
| `\tableofcontents` | `#outline()` |
| `\include{file}` | `#include "file.typ"` |
| `\input{file}` | `#include "file.typ"` |

## Sectioning

| LaTeX | Typst |
|-------|-------|
| `\section{Title}` | `= Title` |
| `\subsection{Title}` | `== Title` |
| `\subsubsection{Title}` | `=== Title` |
| `\paragraph{Title}` | `==== Title` |

Typst headings nest arbitrarily deep — just add more `=` signs.

## Text formatting

Most mappings are intuitive (`\textbf` → `*bold*`, `\textit` → `_italic_`, `\texttt` → `` `mono` ``). Non-obvious ones:

| LaTeX | Typst |
|-------|-------|
| `\textsc{SmallCaps}` | `#smallcaps[SmallCaps]` |
| `\sout{strikethrough}` | `#strike[strikethrough]` |
| `\textsuperscript{x}` | `#super[x]` |
| `\textsubscript{x}` | `#sub[x]` |
| `{\color{red} text}` | `#text(fill: red)[text]` |
| `{\small text}` | `#text(size: 0.8em)[text]` |
| `\footnote{text}` | `#footnote[text]` |
| `\hl{text}` (soul) | `#highlight[text]` |
| `\MakeUppercase{text}` | `#upper[text]` |
| `\MakeLowercase{text}` | `#lower[text]` |
| `\setmainfont{...}` | `#set text(font: "...")` |

Typst is Unicode-native — no `fontenc`/`inputenc` packages needed.

## Page layout

| LaTeX | Typst |
|-------|-------|
| `\usepackage[margin=1in]{geometry}` | `#set page(margin: 1in)` |
| `\usepackage{fancyhdr}` | `#set page(header: ..., footer: ...)` |
| `\pagestyle{empty}` | `#set page(numbering: none)` |
| `\pagenumbering{roman}` | `#set page(numbering: "i")` |
| `\twocolumn` | `#set page(columns: 2)` |
| `\newpage` | `#pagebreak()` |
| `\clearpage` | `#pagebreak()` |
| `\landscape` | `#set page(flipped: true)` |

## Lists

| LaTeX | Typst |
|-------|-------|
| `\begin{itemize} \item ...` | `- item` |
| `\begin{enumerate} \item ...` | `+ item` |
| `\begin{description} \item[term] ...` | `/ term: description` |
| Nested lists | Indent with spaces |
| Custom markers | `#set list(marker: [--])` |
| Custom numbering | `#set enum(numbering: "a)")` |

## Math

| LaTeX | Typst |
|-------|-------|
| `$x$` (inline) | `$x$` |
| `\[ x \]` or `$$x$$` (display) | `$ x $` (spaces!) |
| `\frac{a}{b}` | `$ a/b $` or `$ frac(a,b) $` |
| `x^{2}` | `$ x^2 $` or `$ x^(2+n) $` |
| `x_{i}` | `$ x_i $` or `$ x_(i+1) $` |
| `\sqrt{x}` | `$ sqrt(x) $` |
| `\sqrt[3]{x}` | `$ root(3, x) $` |
| `\sum_{i=1}^{n}` | `$ sum_(i=1)^n $` |
| `\int_{a}^{b}` | `$ integral_a^b $` |
| `\left( \right)` | Automatic! Or `$ lr(( )) $` |
| `\begin{aligned} ... \end{aligned}` | `$ x &= 1 \ &= 2 $` |
| `\begin{pmatrix} a & b \\ c & d \end{pmatrix}` | `$ mat(a, b; c, d) $` |
| `\begin{bmatrix} ... \end{bmatrix}` | `$ mat(delim: "[", a, b; c, d) $` |
| `\begin{cases} ... \end{cases}` | `$ cases(x "if" y, z "else") $` |
| `\binom{n}{k}` | `$ binom(n, k) $` |
| `\mathbb{R}` | `$ RR $` (also `NN`, `ZZ`, `QQ`, `CC`) |
| `\mathcal{L}` | `$ cal(L) $` |
| `\text{word}` | `$ "word" $` (quotes for text in math) |
| `\operatorname{argmax}` | `$ op("argmax") $` |
| `\bar{x}` | `$ macron(x) $` (NOT `bar`) |
| `\overline{x}` | `$ overline(x) $` |
| `\hat{x}`, `\dot{x}`, `\vec{x}` | `$ hat(x) $`, `$ dot(x) $`, `$ arrow(x) $` |
| `\partial` | `$ partial $` (NOT `diff` — `diff` is the differential d) |
| `\cdot` | `$ dot.c $` (NOT `dot` — `dot` is the accent) |
| `\times` | `$ times $` |
| `\leq`, `\geq`, `\neq` | `$ <= $`, `$ >= $`, `$ != $` |
| `\rightarrow`, `\Rightarrow` | `$ -> $`, `$ => $` |
| `\ldots`, `\vdots`, `\ddots` | `$ dots $`, `$ dots.v $`, `$ dots.down $` |
| `\label{eq:x}` | `$ ... $ <eq:x>` |
| `\eqref{eq:x}` | `@eq:x` |
| `\nonumber` | Numbering is off by default; enable with `#set math.equation(numbering: ...)` |

Most Greek letters and symbols use the same name without backslash: `alpha`, `beta`, `infinity`, `nabla`, `forall`, `exists`, `subset`, `union`, `sect`.

## Figures and images

| LaTeX | Typst |
|-------|-------|
| `\includegraphics[width=0.8\textwidth]{img}` | `#image("img.png", width: 80%)` |
| `\begin{figure}[h] ... \caption{...} \end{figure}` | `#figure(image(...), caption: [...])` |
| `\label{fig:x}` | `<fig:x>` (after figure) |
| `\ref{fig:x}` | `@fig:x` |
| `\listoffigures` | `#outline(target: figure)` |

## Tables

| LaTeX | Typst |
|-------|-------|
| `\begin{tabular}{lcr}` | `#table(columns: 3, align: (left, center, right), ...)` |
| `\hline` | Default (or `table.hline()`) |
| `&` (column sep) | `,` between cells |
| `\\` (row sep) | Just keep listing cells |
| `\multicolumn{2}{c}{text}` | `table.cell(colspan: 2, align: center)[text]` |
| `\multirow{2}{*}{text}` | `table.cell(rowspan: 2)[text]` |
| `\caption{...}` | Wrap in `#figure(table(...), caption: [...])` |

## References and bibliography

| LaTeX | Typst |
|-------|-------|
| `\cite{key}` | `@key` |
| `\citet{key}` | `#cite(<key>, form: "prose")` |
| `\bibliographystyle{...}` | `#bibliography("refs.bib", style: "ieee")` |
| `\bibliography{refs}` | `#bibliography("refs.bib")` |
| `\label{sec:intro}` | `<sec:intro>` |
| `\ref{sec:intro}` | `@sec:intro` |

## Spacing and breaks

| LaTeX | Typst |
|-------|-------|
| `\\` (line break) | `\` (single backslash) |
| `\newline` | `\` |
| `\par` | Blank line |
| `\vspace{1em}` | `#v(1em)` |
| `\hspace{1em}` | `#h(1em)` |
| `\hfill` | `#h(1fr)` |
| `\vfill` | `#v(1fr)` |
| `~` (non-breaking space) | `~` |
| `---` (em dash) | `---` |
| `--` (en dash) | `--` |

## Environments → Typst equivalents

| LaTeX | Typst |
|-------|-------|
| `\begin{center}` | `#align(center)[...]` |
| `\begin{flushleft}` | `#align(left)[...]` |
| `\begin{flushright}` | `#align(right)[...]` |
| `\begin{quote}` | `#quote[...]` or `#pad(x: 2em)[...]` |
| `\begin{verbatim}` | `` ```raw text``` `` |
| `\begin{abstract}` | Template-dependent (usually a parameter) |
| `\begin{appendix}` | Reset heading counter + change numbering |
| `\begin{multicols}{2}` | `#columns(2)[...]` |

## Key conceptual differences

1. **No preamble/body split** — Typst documents start immediately with content
2. **No compilation lag** — Typst compiles in milliseconds
3. **No backslash commands** — Everything is `#function()` or markup shortcuts
4. **No environments** — Use function calls with content blocks instead
5. **Consistent syntax** — All functions work the same way (unlike LaTeX's per-package conventions)
6. **Set rules replace preamble** — Style defaults anywhere in the document
7. **Show rules replace renewcommand** — Redefine element rendering cleanly
8. **Unicode native** — No special packages for UTF-8 or non-Latin scripts
9. **Built-in batteries** — Colors, bibliography, hyperlinks, etc. need no packages
10. **Functions are deterministic** — Output depends only on arguments and context
