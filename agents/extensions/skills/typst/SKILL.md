---
description: |
  How to write Typst documents correctly and idiomatically. Use this skill whenever the user
  asks you to write, generate, edit, or convert Typst (.typ) files — including academic papers,
  reports, CVs, letters, presentations, homework, or any typeset document. Also use when the
  user mentions Typst by name, asks to convert LaTeX to Typst, or wants help with Typst syntax,
  math equations, tables, templates, or styling. If the user says "write this up nicely" or
  "make a PDF" and Typst is a reasonable choice, suggest it.
user-invocable: false
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Writing Typst

Typst is a modern typesetting language that compiles to PDF. It replaces LaTeX with cleaner syntax, millisecond compilation, and a coherent design. This skill covers the patterns and gotchas you need to write Typst well.

## Reference files

This skill has deeper reference material in `references/`. Consult them as needed:

- `references/math.md` — Math mode: equations, symbols, alignment, matrices, and operators
- `references/tables-layout.md` — Tables, grids, figures, page setup, and multi-column layout
- `references/templates.md` — Template authoring, document structure, and reusable components
- `references/latex-cheatsheet.md` — LaTeX-to-Typst quick mapping for common commands

## The three modes

Typst has three syntactic modes. Understanding when you're in each mode is the single most important thing for writing correct Typst.

| Mode | Purpose | Enter via |
|------|---------|-----------|
| **Markup** | Writing prose, the default | Top of file, or `[brackets]` |
| **Code** | Logic, variables, function calls | `#` prefix, or `{braces}` |
| **Math** | Equations | `$dollar signs$` |

### Mode switching rules

**Markup → Code**: Prefix with `#`. Once in code mode, you stay there for that expression — no additional `#` needed for nested calls.

```typst
// Markup mode — need # to call functions
This is markup. #rect(fill: blue)[Inside here is markup again]

// WRONG: don't double-hash inside code blocks
#{
  let x = 5
  rect(fill: blue)[Value: #x]  // #x is correct here — back in markup inside []
}
```

**Code → Markup**: Use `[square brackets]` to create content blocks.

```typst
#let greeting(name) = [Hello, *#name*!]  // [] switches back to markup
```

**Markup → Math**: Wrap in `$`. Spaces matter: `$x$` is inline, `$ x $` (with spaces) is display/block.

```typst
Inline: $x^2 + y^2 = z^2$

Display (note the spaces):
$ sum_(k=1)^n k = (n(n+1)) / 2 $
```

### Content blocks `[]` vs code blocks `{}`

This distinction trips up many users:

- `[*Hello* world]` — **content block**: markup is parsed, produces `content`
- `{ let x = 1; x + 2 }` — **code block**: code is executed, values join together
- In code blocks, you don't prefix with `#` (you're already in code mode)
- In content blocks, you do need `#` for expressions

```typst
// Function body as code block — no # needed for function calls
#let card(title) = {
  set text(white)
  rect(fill: navy, inset: 12pt, [*#title*])
}

// Function body as content block — # needed
#let card(title) = [
  #set text(white)
  #rect(fill: navy, inset: 12pt, [*#title*])
]
```

Prefer code blocks `{}` for function bodies — they're less noisy.

## Markup essentials

Bold `*bold*`, italic `_italic_`, heading `= Title` (space required after `=`), bullet `- item`, numbered `+ item`. These work like Markdown. Key differences from Markdown/LaTeX:

| Element | Syntax | Notes |
|---------|--------|-------|
| Term list | `/ Term: definition` | No Markdown equivalent |
| Label | `<my-label>` | Attach to preceding element |
| Reference | `@my-label` | Cross-reference a label |
| Citation | `@key` | Cites from bibliography |
| Line break | `\` (single backslash) | Not `\\` like LaTeX |
| Escape | `\#`, `\$`, `\*`, `\_` | Backslash-escape special chars |
| Non-breaking space | `~` | |
| Highlight | `#highlight[text]` | Background color, wraps across lines |

Code blocks: `` `inline` `` or ```` ```lang ```` for blocks. Typst-specific languages: `typ`, `typc`, `typm`.

## Set rules: styling defaults

Set rules change the defaults for a function. They're the primary styling mechanism — think of them as "from here on, whenever you use this function, apply these defaults."

```typst
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true, leading: 0.65em)
#set page("a4", margin: (x: 2.5cm, y: 2.5cm))
#set heading(numbering: "1.1")
```

Only **optional** parameters can be set. The `set` keyword must directly precede the function call (no `let` binding in between).

### Scoping

Set rules inside a block only apply within that block:

```typst
This text is normal.

#[
  #set text(fill: red)
  This text is red.
]

This text is normal again.
```

This scoping is fundamental to Typst's design. Use it deliberately.

### Conditional set rules

```typst
#let task(body, critical: false) = {
  set text(red) if critical
  [- #body]
}
```

## Show rules: redefining appearance

Show rules transform how elements are displayed. They're more powerful than set rules — they can completely replace an element's rendering.

### Show-set rules (most common)

Apply a set rule only to a specific element type:

```typst
#show heading: set text(navy)
#show heading.where(level: 1): set text(size: 18pt)
#show raw.where(block: true): set text(size: 9pt)
```

### Transformational show rules

Replace an element with custom content. The function receives the element as its argument:

```typst
#show heading.where(level: 1): it => {
  set text(navy, size: 16pt)
  block(below: 1em)[
    #counter(heading).display(it.numbering) #smallcaps(it.body)
  ]
}
```

### Text and regex show rules

Replace or transform specific text:

```typst
#show "LaTeX": [L#super[A]T#sub[E]X]
#show regex("\d{4}-\d{2}-\d{2}"): it => emph(it)
```

### The "everything" show rule

Apply a function to all subsequent content. This is the basis of templates:

```typst
#show: rest => columns(2, rest)
```

### Selector types

| Selector | Example |
|----------|---------|
| Element function | `show heading: ...` |
| Element + filter | `show heading.where(level: 2): ...` |
| Specific text | `show "word": ...` |
| Regex pattern | `show regex("\\d+"): ...` |
| Label | `show <intro>: ...` |
| Everything | `show: ...` |

### Composing set and show rules

Keep styling modular. Use separate show-set rules for different properties rather than embedding everything in one transformational show rule:

```typst
// Good: composable, each can be overridden independently
#show heading: set align(center)
#show heading: set text(font: "Inria Serif")
#show heading: it => block(above: 1.4em, below: 1em, it.body)

// Less good: monolithic, harder to override parts
#show heading: it => {
  set align(center)
  set text(font: "Inria Serif")
  block(above: 1.4em, below: 1em, it.body)
}
```

## Functions

Functions are defined with `let`. They are deterministic (output depends on arguments and context).

```typst
#let alert(body, fill: red) = {
  set text(white)
  set align(center)
  rect(fill: fill, inset: 8pt, radius: 4pt, [*Warning:\ #body*])
}

#alert[Danger!]
#alert(fill: blue)[Info]
```

### Trailing content arguments

When a function's last parameter accepts content, you can pass it after the parentheses:

```typst
#rect(fill: aqua)[Content goes here]
// Equivalent to: #rect(fill: aqua, [Content goes here])

// Multiple trailing content blocks become multiple arguments
#list[First][Second][Third]
```

### Argument sinks and spreading

```typst
#let format(title, ..authors) = {
  let by = authors.pos().join(", ", last: " and ")
  [*#title* \ _Written by #by;_]
}
#format("Paper", "Alice", "Bob")

// Spread an array into a function call
#let nums = (1, 5, 3)
#calc.min(..nums)
```

### Partial application with `.with()`

```typst
#let warn = rect.with(fill: yellow, inset: 8pt)
#warn[Be careful!]
```

### Selectors with `.where()`

```typst
#show heading.where(level: 2): set text(blue)
#counter(figure.where(kind: table)).display()
```

## Control flow

### Conditionals

```typst
#if x > 0 [Positive] else if x == 0 [Zero] else [Negative]
```

### Loops

Loop bodies **join** their results into content — they do NOT produce an array:

```typst
#for name in ("Alice", "Bob") [Hello, #name! \ ]

// Dictionary iteration with destructuring
#for (key, value) in (name: "Alice", age: 30) [#key: #value \ ]

// While loop
#{
  let n = 1
  while n <= 3 { [#n ]; n += 1 }
}
```

`break` exits early; `continue` skips to next iteration.

### Destructuring

```typst
#let (a, b) = (1, 2)
#let (first, .., last) = (1, 2, 3, 4)   // rest pattern
#let (_, y, _) = (1, 2, 3)               // discard with _
```

## Collection methods

### Arrays

```typst
#let nums = (3, 1, 4, 1, 5)
#nums.map(n => n * 2)              // (6, 2, 8, 2, 10)
#nums.filter(n => n > 2)           // (3, 4, 5)
#nums.sorted()                     // (1, 1, 3, 4, 5)
#nums.enumerate()                  // ((0, 3), (1, 1), ...)
#nums.sum()                        // 14
#nums.any(n => n > 4)              // true
#("A", "B", "C").join(", ", last: " and ")  // "A, B, and C"
```

Mutating methods: `push`, `pop`, `insert`, `remove` (modify in place).

**Gotcha**: `(1)` is an integer, `(1,)` is a single-element array. Empty array: `()`. Empty dict: `(:)`.

### Dictionaries

```typst
#let meta = (title: "Paper", year: 2025)
#meta.at("title")                   // "Paper"
#meta.at("missing", default: "N/A") // "N/A" — no error
#meta.keys()                        // ("title", "year")
#meta.pairs()                       // (("title", "Paper"), ("year", 2025))
```

### Strings

```typst
#"hello world".split(" ")           // ("hello", "world")
#"  padded  ".trim()                // "padded"
#"abc".contains("b")                // true
#"foo bar".replace("bar", "baz")    // "foo baz"
```

**Gotcha**: `.len()` returns UTF-8 byte count, not character count. Use `.clusters().len()` for grapheme count.

## Context expressions

Some values depend on *where* in the document they appear — page numbers, heading counters, current text language. Access these with `context`:

```typst
#context text.lang           // current language
#context text.size           // current font size
#context counter(page).get() // (1,) — returns array, use .first() for int
```

Context expressions produce **opaque content** — you cannot extract the value outside the context block. All dependent operations must happen inside:

```typst
// WRONG: trying to use context result outside
#let size = context text.size
#if size > 12pt [Big]  // Error: size is opaque content, not a length

// RIGHT: keep logic inside context
#context {
  let size = text.size
  if size > 12pt [Big] else [Normal]
}
```

### Counters

```typst
#set heading(numbering: "1.")

= Introduction <intro>
#context counter(heading).get()      // (1,)

= Background <bg>
#context counter(heading).get()      // (2,)

// "Time travel" — check counter at a label
#context counter(heading).at(<intro>)  // (1,)

// Total page count
#context counter(page).final().first()
```

### Custom counters and state

```typst
#let theorem-counter = counter("theorem")
#let theorem(body) = {
  theorem-counter.step()
  block(inset: 8pt, stroke: black)[
    *Theorem #context theorem-counter.display():* #body
  ]
}

#theorem[Every even number greater than 2 is the sum of two primes.]
```

For mutable document state beyond simple counting, use `state()`:

```typst
#let total = state("total", 0)
#total.update(v => v + 10)
#total.update(v => v + 20)
Total: #context total.get()  // 30
```

**Warning**: `state.update` and `counter.step` return content that must be placed in the document. They resolve in layout order, not evaluation order. Avoid self-referential introspection (querying something that changes based on the query result) — it may not converge.

### Querying document elements

`query()` finds elements matching a selector. Essential for dynamic headers, custom TOCs, and cross-reference logic:

```typst
// Custom header showing current chapter title
#set page(header: context {
  let chapters = query(selector(heading.where(level: 1)).before(here()))
  if chapters.len() > 0 {
    emph(chapters.last().body) + h(1fr) + counter(page).display()
  }
})

// Find all elements with a label
#context query(<important>).len()
```

Use `here()` for current location, `locate(<label>)` for a label's physical position. Embed invisible queryable data with `metadata("value") <tag>`.

### Numbering patterns

Pattern strings use counting symbols with literal prefix/suffix:

```typst
"1."      // 1. 2. 3.
"(1)"     // (1) (2) (3)
"a)"      // a) b) c)
"i"       // i ii iii
"I."      // I. II. III.
"1.1"     // hierarchical: 1.1, 1.2, 2.1
"1.a)"    // nested: top 1., inner a)
```

Works in `heading(numbering:)`, `page(numbering:)`, `enum(numbering:)`, `figure(numbering:)`, and `math.equation(numbering:)`.

### Dates

```typst
#datetime.today().display("[month repr:long] [day], [year]")  // March 22, 2026
#datetime(year: 2025, month: 6, day: 15).display("[year]-[month]-[day]")
```

Format components: `[year]`, `[month]`, `[day]`, `[hour]`, `[minute]`, `[weekday]`. Modifiers: `repr:long`, `repr:short`, `repr:numerical`.

## Imports and packages

```typst
// Import from local file
#import "template.typ": conf

// Import everything
#import "utils.typ": *

// Import from Typst Universe (community packages)
#import "@preview/cetz:0.4.1"
#import "@preview/touying:0.5.0": *

// Include file content directly (not as module)
#include "chapter1.typ"
```

Package names follow `@namespace/name:version`. The `preview` namespace is the community package registry.

## Data loading

Typst can load `csv()`, `json()`, `yaml()`, `toml()`, `xml()`, and `read()` (raw text). All return native Typst types:

```typst
#let data = csv("data.csv")
#table(columns: data.first().len(), ..data.flatten().map(c => [#c]))
```

## Colors

Named colors (`red`, `blue`, `navy`, etc.), custom via `rgb("#hex")` or `rgb(r, g, b)`, grayscale via `luma(0-255)`. Methods: `.lighten(%)`, `.darken(%)`. Gradients: `gradient.linear(red, blue)`.

## Common gotchas

### 1. Spaces in math mode determine display vs inline

```typst
$x^2$         // inline
$ x^2 $       // display (block) — spaces after $ and before $
```

If your equation appears inline when you wanted it centered on its own line, add spaces.

### 2. Multi-letter names in math are function calls

In math mode, single letters are variables, but multi-letter sequences are interpreted as function/symbol names:

```typst
$ sin(x) $     // sin is a built-in operator — correct
$ diff $       // renders as the differential symbol, not "d·i·f·f"
$ "word" $     // use quotes for literal multi-letter text
$ x "if" y > 0 $
```

### 3. No backslash commands

Typst uses `#function()`, not `\command{}`. There are no backslash commands:

```typst
// WRONG (LaTeX habit)
\textbf{bold}    \frac{1}{2}    \begin{enumerate}

// RIGHT (Typst)
*bold*           $1/2$          + First item
```

### 4. Naming convention is kebab-case

```typst
#set text(number-type: "old-style")
#set par(first-line-indent: 1.8em)
// NOT: numberType, firstLineIndent
```

### 5. Content vs strings

Content and strings are different types. Content supports markup; strings are plain characters:

```typst
#let a = [*bold* content]   // content — markup is parsed
#let b = "*not* bold"       // string — literal characters

// Functions expecting content accept strings (auto-converted)
// But you can't use content methods on strings or vice versa
```

### 6. Trailing commas and single-element arrays

```typst
(1, 2, 3)    // array
(1,)         // single-element array — comma required
(1)          // just the integer 1, NOT an array
()           // empty array
(:)          // empty dictionary
```

### 7. Line break is `\`, not `\\`

```typst
First line \
Second line
```

### 8. Page function forces page breaks

Unlike LaTeX, you cannot change page margins mid-page. A new `#set page(...)` rule creates a page break. For temporary margin adjustments, use `#pad` with negative values.

### 9. Smart quotes are automatic

Typst converts `"` and `'` to language-appropriate smart quotes. If you need literal straight quotes (rare), escape them.

### 10. `#` is not needed inside `{}`

```typst
// WRONG: double-hashing in code blocks
#{
  #let x = 5    // Don't prefix with #
  #rect()       // Don't prefix with #
}

// RIGHT
#{
  let x = 5
  rect()
}
```

### 11. `#expr` needs parentheses for binary operations

```typst
Value: #(1 + 2)     // RIGHT — parenthesize binary ops
Value: #1 + 2       // WRONG — only #1 is the expression
```

Use `;` to force-end a code expression before following markup: `#let n = 3; The value is #n.`

### 12. Labels only work on referenceable elements

`@label` produces "Section 1" or "Figure 2" only for elements with numbering/supplement (headings, figures, equations, footnotes). For arbitrary labeled content, use `#link(<label>)` instead:

```typst
= Intro <intro>
@intro              // works: "Section 1"

#block[Note] <note>
// @note            // WRONG: block has no supplement
#link(<note>)[see note]  // RIGHT: use link for arbitrary labels
```

### 13. Custom blocks need `figure(kind:)` to be cross-referenceable

A plain counter + block won't work with `@ref`. Wrap in `figure` with a custom kind:

```typst
#let theorem(body) = figure(
  kind: "theorem", supplement: [Theorem], body,
)
#show figure.where(kind: "theorem"): it => block(
  inset: 10pt, stroke: (left: 2pt + navy),
)[*#it.supplement #it.counter.display(it.numbering).* #it.body]

#theorem[$a^2 + b^2 = c^2$] <thm:pyth>
See @thm:pyth.
```

### 14. Custom header/footer overrides default page numbering

Once you set `footer:`, the `numbering:` parameter no longer displays automatically. You must render page numbers yourself:

```typst
#set page(
  footer: context [My Doc #h(1fr) #counter(page).display()],
)
```

## Idiomatic patterns

### Document preamble

```typst
#set document(title: "My Paper", author: "Author Name")
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em)
#set page("a4", margin: auto, numbering: "1")
#set heading(numbering: "1.1")

// Optional: style headings, code blocks, etc.
#show heading.where(level: 1): set text(size: 16pt)
#show raw.where(block: true): block.with(fill: luma(240), inset: 10pt, radius: 4pt)
```

### Accessibility checklist

For any serious document:

- `#set document(title: "...", author: "...")` — required for PDF metadata
- `#set text(lang: "en")` — affects hyphenation, smart quotes, screen readers
- `image("...", alt: "description")` — alt text for images
- Use `table.header` for table headers (not just bold text)
- Use `figure` for numbered content (not manual counters + blocks)
- Don't put essential content only in headers/footers (invisible to assistive tech)

### Paragraph spacing

```typst
// leading = between lines WITHIN a paragraph
// spacing = between paragraphs
#set par(leading: 0.65em, spacing: 1.2em)

// "Double spacing" for homework/papers
#set par(leading: 1.3em, spacing: 1.3em)

// First-line indent (all paragraphs including after headings)
#set par(first-line-indent: (amount: 1.8em, all: true))
```

### List and enum customization

```typst
#set enum(numbering: "a)")        // a) b) c)
#set enum(numbering: "(1)")       // (1) (2) (3)
#set enum(numbering: "i.")        // i. ii. iii.
#set enum(numbering: "1.a)")      // nested: top 1., inner a)
#set enum(start: 3)               // begin at 3
#set list(marker: ([--], [*]))    // per nesting level
```

### Footnotes

```typst
See here#footnote[Footnote text.]

#set footnote(numbering: "*")     // symbols instead of numbers
#set footnote.entry(
  separator: line(length: 30%, stroke: 0.5pt),
  gap: 0.5em,
)
```

### Cross-reference customization

```typst
#set heading(supplement: [Sec.])  // @intro → "Sec. 1"
#set figure(supplement: [Fig.])   // @fig:x → "Fig. 1"
@intro[Chapter]                   // one-off: "Chapter 1"
```

### Citation forms

```typst
@smith2024                              // [1] or (Smith, 2024)
#cite(<smith2024>, form: "prose")       // Smith (2024)
#cite(<smith2024>, form: "author")      // Smith
#cite(<smith2024>, form: "year")        // 2024
@smith2024[pp.~1--10]                   // with supplement
```

### Using a template

```typst
#import "template.typ": conf

#show: conf.with(
  title: [My Paper Title],
  authors: (
    (name: "Alice", affiliation: "MIT", email: "alice@mit.edu"),
  ),
  abstract: [This paper presents...],
)

= Introduction
...
```

### Custom numbered blocks (theorems, definitions)

```typst
#let theorem-counter = counter("theorem")

#let theorem(body, title: none) = {
  theorem-counter.step()
  block(
    width: 100%, inset: 10pt,
    stroke: (left: 2pt + navy),
    fill: navy.lighten(95%),
  )[
    *Theorem #context theorem-counter.display()#if title != none [: #title]*
    #parbreak() #body
  ]
}
```

### Two-column layout

```typst
// Whole document
#set page(columns: 2)

// Just a section
#columns(2)[
  Left column content.
  #colbreak()
  Right column content.
]
```

### Figures with captions

```typst
#figure(
  image("plot.png", width: 80%),
  caption: [Experimental results showing...],
) <fig:results>

As shown in @fig:results, ...
```

For table figures, captions go on top by convention:

```typst
#show figure.where(kind: table): set figure.caption(position: top)
```

### Page header/footer

```typst
#set page(
  header: context {
    if counter(page).get().first() > 1 [
      _My Document_ #h(1fr) #counter(page).display()
    ]
  },
)
```

### Bibliography

```typst
// At end of document
#bibliography("refs.bib", style: "ieee")

// Cite in text
As shown by @smith2024, ...
#cite(<smith2024>, form: "prose")  // "Smith (2024) showed..."
```
