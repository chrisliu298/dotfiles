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
#import "@preview/touying:0.5.0": *
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

## Packages from Typst Universe

Use `#import "@preview/name:version"` to import community packages. Browse at https://typst.app/universe/. Common ones: `cetz` (drawing), `touying` (presentations), `unify` (units), `glossarium` (glossaries). Initialize a project from a template: `typst init @preview/charged-ieee`.
