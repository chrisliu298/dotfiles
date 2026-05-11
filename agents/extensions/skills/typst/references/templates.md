# Templates and Document Structure

## How templates work

A Typst template is a function that accepts the document body (and metadata) and returns styled content. Applied via an "everything" show rule.

### Minimal template

```typst
// template.typ
#let article(body) = {
  set text(font: "Libertinus Serif", size: 11pt)
  set par(justify: true)
  set page("a4", margin: auto, numbering: "1")
  body
}
```

```typst
// main.typ
#import "template.typ": article
#show: article
= Introduction
...
```

### Template with metadata

```typst
// template.typ
#let conf(
  title: none,
  authors: (),
  date: none,
  abstract: none,
  body,
) = {
  set document(title: title, author: authors.map(a => a.name))
  set text(font: "New Computer Modern", size: 11pt)
  set par(justify: true)
  set page("us-letter", margin: (x: 2.5cm, y: 2.5cm), numbering: "1")
  set heading(numbering: "1.1")

  // Title block
  align(center)[
    #text(size: 18pt, weight: "bold", title)
    #v(1em)
    #if date != none [#date \ ]
    #v(0.5em)
    #grid(
      columns: calc.min(authors.len(), 3) * (1fr,),
      gutter: 16pt,
      ..authors.map(author => align(center)[
        #text(weight: "bold", author.name) \
        #author.affiliation \
        #link("mailto:" + author.email)
      ]),
    )
  ]

  // Abstract
  if abstract != none {
    v(2em)
    align(center)[
      #block(width: 80%)[
        *Abstract* \
        #abstract
      ]
    ]
    v(2em)
  }

  body
}
```

### Applying with `.with()`

The `.with()` method pre-fills arguments, creating a clean entry point:

```typst
// main.typ
#import "template.typ": conf

#show: conf.with(
  title: [Towards Improved Modelling],
  authors: (
    (name: "Alice Smith", affiliation: "MIT", email: "alice@mit.edu"),
    (name: "Bob Jones", affiliation: "Stanford", email: "bob@stanford.edu"),
  ),
  date: [March 2025],
  abstract: [We present a novel approach...],
)

= Introduction
#lorem(50)

= Methods
#lorem(50)
```

This is equivalent to writing a closure:

```typst
#show: doc => conf(
  title: [Towards Improved Modelling],
  ..., // other params
  doc,
)
```

`.with()` is preferred — it's cleaner and the standard convention for Typst Universe templates.

## Template design patterns

### Show rules inside templates

Templates commonly include show rules for consistent styling:

```typst
#let article(body) = {
  // Set rules for defaults
  set text(font: "Libertinus Serif", size: 11pt)
  set par(justify: true, leading: 0.65em)
  set heading(numbering: "1.1")

  // Show rules for custom rendering
  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    v(2em)
    text(size: 18pt, weight: "bold", it.body)
    v(1em)
  }

  show heading.where(level: 2): set text(size: 14pt)

  // Code block styling
  show raw.where(block: true): block.with(
    fill: luma(240), inset: 10pt, radius: 4pt, width: 100%,
  )

  // Link styling
  show link: underline

  body
}
```

### Configurable components

Make components that users can call throughout their document:

```typst
// In template.typ
#let note(body) = block(
  inset: 10pt, radius: 4pt, width: 100%,
  fill: yellow.lighten(80%),
  stroke: yellow.darken(20%),
)[*Note:* #body]

#let todo(body) = block(
  inset: 10pt, radius: 4pt, width: 100%,
  fill: red.lighten(90%),
  stroke: red,
)[*TODO:* #body]
```

```typst
// In main.typ
#import "template.typ": conf, note, todo

#note[Remember to cite the original paper.]
#todo[Add experimental results.]
```

### Appendix handling

```typst
#let appendix(body) = {
  set heading(numbering: "A.1", supplement: [Appendix])
  counter(heading).update(0)
  body
}

// Usage
#show: appendix
= Additional Proofs
```

## File organization

### Single-file document

For short documents, put everything in one file:

```typst
// preamble
#set text(...)
#set page(...)

// content
= Introduction
...
```

### Multi-file project

```
project/
├── main.typ          // imports template, contains content
├── template.typ      // styling and layout
├── refs.bib          // bibliography
├── chapters/
│   ├── intro.typ
│   ├── methods.typ
│   └── results.typ
└── figures/
    ├── plot1.png
    └── diagram.svg
```

```typst
// main.typ
#import "template.typ": conf
#show: conf.with(title: [My Thesis], ...)

#include "chapters/intro.typ"
#include "chapters/methods.typ"
#include "chapters/results.typ"

#bibliography("refs.bib")
```

### Import vs include

- `#import "file.typ": func` — loads the file as a module, selectively imports names
- `#include "file.typ"` — inserts the file's content directly (like copy-paste)
- `#import "file.typ"` — imports the entire module, access via `file.func`

Use `import` for functions/templates. Use `include` for content (chapters, sections).

## Common template recipes

### LaTeX article look

```typst
#set page(margin: 1.75in)
#set par(leading: 0.55em, spacing: 0.55em, first-line-indent: 1.8em, justify: true)
#set text(font: "New Computer Modern", size: 10pt)
#show raw: set text(font: "New Computer Modern Mono")
#show heading: set block(above: 1.4em, below: 1em)
```

### Letter/memo

```typst
#let letter(
  sender: none,
  recipient: none,
  date: none,
  subject: none,
  body,
) = {
  set page("us-letter", margin: (x: 2.5cm, y: 2.5cm))
  set text(font: "Libertinus Serif", size: 11pt)
  set par(justify: true)

  // Sender
  if sender != none { align(right, sender); v(2em) }
  // Date
  if date != none { align(right, date); v(1em) }
  // Recipient
  if recipient != none { recipient; v(2em) }
  // Subject
  if subject != none [*Re: #subject* \ ]; v(1em)

  body
}
```

### Presentation (with touying package)

```typst
#import "@preview/touying:0.7.3": *   // check Universe for current version
#import themes.simple: *

#show: simple-theme.with(aspect-ratio: "16-9")

= First Slide
Content here.

= Second Slide
More content.
```

### Table of contents and outlines

```typst
#outline()                                          // basic TOC
#outline(depth: 2, indent: auto)                    // limit depth, auto-indent
#outline(title: [List of Figures], target: figure.where(kind: image))
#outline(title: [List of Tables], target: figure.where(kind: table))
#outline(title: none)                               // no title
```

Style outline entries with show rules:

```typst
#show outline.entry.where(level: 1): set text(weight: "bold")
#show outline.entry.where(level: 1): set block(above: 1.2em)
#set outline.entry(fill: repeat[.#h(4pt)])          // custom fill dots
```

Exclude specific elements from the outline: `#heading(outlined: false)[Preface]`.

### Heading offset for included files

In multi-file projects, shift heading levels in included files:

```typst
// main.typ — included files' = headings become level 2
= Part I
#set heading(offset: 1)
#include "chapter1.typ"
```

## Quick patterns

Small recipes that are common in templates and ad-hoc documents.

### Paragraph spacing

```typst
// leading = between lines within a paragraph
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
#set list(marker: ([--], [\*]))   // per nesting level — escape * to avoid strong parsing
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
@smith2024                              // [1] or (Smith, 2024); style-dependent
#cite(<smith2024>, form: "prose")       // Smith (2024)
#cite(<smith2024>, form: "author")      // Smith
#cite(<smith2024>, form: "year")        // 2024
@smith2024[pp.~1--10]                   // with supplement

// Use #cite(label("...")) when the key contains characters that <label> can't parse.
```

### Bibliography

```typst
// Hayagriva YAML (Typst-native — preferred for non-trivial entry types)
#bibliography("refs.yml", style: "apa")

// BibLaTeX .bib (works out of the box — no biber/biblatex required)
#bibliography("refs.bib", style: "ieee")
```

Built-in CSL styles include `"ieee"`, `"apa"`, `"chicago-author-date"`,
`"chicago-notes"`, `"mla"`, `"nature"`, `"acm"`, `"vancouver"`,
`"harvard-cite-them-right"`. Pass a path to a `.csl` file for anything else.

### Custom numbered blocks (theorems, definitions)

Use `figure(kind:)` as the default so `@thm:...` references work. Manual
`counter()` + `block` is fine only when the block does not need referencing.

```typst
#let theorem(body, title: none) = figure(
  kind: "theorem",
  supplement: [Theorem],
  numbering: "1",
  caption: none,
  block(
    width: 100%, inset: 10pt,
    stroke: (left: 2pt + navy),
    fill: navy.lighten(95%),
  )[
    #if title != none [*#title.* ]
    #body
  ],
)

#show figure.where(kind: "theorem"): it => block[
  *#it.supplement #context it.counter.display(it.numbering).* #it.body
]

#theorem[$a^2 + b^2 = c^2$] <thm:pyth>
See @thm:pyth.
```

## Safe-copy skeletons

Complete, compileable starting points. Copy one, replace the placeholders, and
add content. They compile under Typst 0.14.2 except for any image paths you add
yourself.

### article

```typst
#set document(title: [Title], author: ("Author Name",))
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em)
#set page("us-letter", margin: (x: 1in, y: 1in), numbering: "1")
#set heading(numbering: "1.1")
#set math.equation(numbering: "(1)")

#align(center)[
  #text(size: 18pt, weight: "bold")[Title] \
  #v(0.4em)
  Author Name · #datetime.today().display("[month repr:long] [day], [year]")
]
#v(1em)

#align(center)[
  #block(width: 80%)[
    *Abstract.* One-paragraph summary of the work.
  ]
]
#v(1em)

= Introduction
Body text. Cite with @key (define a bibliography below).

= Methods
$ E = m c^2 $ <eq:einstein>

See @eq:einstein.

= Results
#figure(
  rect(width: 60%, height: 3cm, fill: luma(230))[plot placeholder],
  caption: [Caption goes here.],
) <fig:plot>

= Conclusion
Body text.

// Uncomment when a bibliography is available:
// #bibliography("refs.bib", style: "ieee")
```

### homework

```typst
#set document(title: [Homework N], author: ("Your Name",))
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set page("us-letter", margin: 1in, header: align(right)[Your Name · Course])
#set par(leading: 0.7em)
#set enum(numbering: "1.")
#set math.equation(numbering: "(1)")

#align(center)[
  #text(size: 14pt, weight: "bold")[Course · Homework N] \
  Your Name · #datetime.today().display("[year]-[month]-[day]")
]
#v(1em)

#let problem(n, body) = [
  *Problem #n.* #body
]

#problem(1)[
  Statement of the first problem.

  *Solution.* Working below.
  $ x = (-b plus.minus sqrt(b^2 - 4 a c)) / (2 a) $
]

#problem(2)[
  Statement of the second problem.

  *Solution.* Working below.
]
```

### cv

```typst
#set document(title: [Your Name — CV], author: ("Your Name",))
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en")
#set page("us-letter", margin: (x: 0.75in, y: 0.75in), numbering: none)
#set par(leading: 0.55em)
#show heading.where(level: 1): set text(size: 14pt, weight: "bold")
#show heading.where(level: 1): set block(above: 1em, below: 0.4em)
#show heading.where(level: 1): it => {
  it.body
  v(-0.2em)
  line(length: 100%, stroke: 0.6pt)
}

#align(center)[
  #text(size: 20pt, weight: "bold")[Your Name] \
  #v(0.2em)
  City · email\@example.com · #link("https://example.com")[example.com]
]
#v(0.5em)

= Experience

#grid(columns: (1fr, auto), gutter: 4pt,
  [*Role* — Company], [#h(1fr) 2024 — present],
)
- Bullet describing impact.
- Bullet describing impact.

#v(0.5em)

#grid(columns: (1fr, auto), gutter: 4pt,
  [*Previous Role* — Earlier Company], [#h(1fr) 2022 — 2024],
)
- Bullet describing impact.

= Education

#grid(columns: (1fr, auto), gutter: 4pt,
  [*B.S. in Major* — University], [#h(1fr) 2018 — 2022],
)
```

### letter

```typst
#set document(title: [Letter], author: ("Your Name",))
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set page("us-letter", margin: (x: 1in, y: 1in))
#set par(justify: true, leading: 0.65em)

#align(right)[
  Your Name \
  Street Address \
  City, ST ZIP
]

#v(1em)

#datetime.today().display("[month repr:long] [day], [year]")

#v(1em)

Recipient Name \
Recipient Title \
Organization \
Address

#v(1em)

Dear Recipient Name,

Body of the letter. Replace this paragraph with the actual message.

Closing paragraph stating the requested next step.

#v(1em)

Sincerely,

#v(2em)
Your Name
```

## Packages from Typst Universe

Use `#import "@preview/name:version"` to import community packages. Browse at
<https://typst.app/universe/>. Common ones: `cetz` (drawing), `touying`
(presentations), `unify` (units), `glossarium` (glossaries), `lilaq` (plotting),
`subpar` (sub-figures), `oxifmt` (string formatting). Initialize a project from
a template: `typst init @preview/charged-ieee`.

**Always check the package's Universe page for the current version before
pinning.** Versions change quickly and APIs sometimes change with them.
