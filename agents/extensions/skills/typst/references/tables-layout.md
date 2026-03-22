# Tables, Figures, and Layout Reference

## Tables

### Basic table

```typst
#table(
  columns: 3,
  [Name], [Age], [City],
  [Alice], [30], [NYC],
  [Bob], [25], [LA],
)
```

### Column sizing

```typst
columns: 3                      // 3 equal auto columns
columns: (1fr, 2fr)             // fractional — 1:2 ratio
columns: (auto, 1fr, auto)     // auto fits content, fr takes remaining
columns: (100pt, 1fr)          // fixed + fractional
columns: (30%, 1fr)            // relative + fractional
```

### Alignment

```typst
// Per-column array (cycles if shorter than column count)
align: (left, center, right)

// Function receiving (column, row) indices
align: (x, y) => if x == 0 { left } else { right }
```

### Fill (backgrounds)

```typst
// Striped rows
fill: (_, y) => if calc.odd(y) { luma(240) }

// Highlight first row and column
fill: (x, y) => if x == 0 or y == 0 { gray.lighten(40%) }
```

### Stroke

```typst
stroke: none                    // no lines
stroke: 0.5pt + gray           // uniform
stroke: (x, y) => if y == 0 { (bottom: 0.7pt + black) }
```

### Headers and footers

Always wrap header rows in `table.header` for accessibility and automatic repetition across pages:

```typst
#table(
  columns: 3,
  table.header(
    [*Name*], [*Score*], [*Grade*],
  ),
  [Alice], [95], [A],
  [Bob], [82], [B],
  table.footer(
    table.cell(colspan: 2)[*Average*], [88.5],
  ),
)
```

Headers repeat on each page by default. Disable with `table.header(repeat: false, ...)`.

### Cell spanning

```typst
#table(
  columns: 3,
  table.header([*Subject*], [*Q1*], [*Q2*]),
  table.cell(colspan: 3, align: center)[*Science Department*],
  [Physics], [A], [B+],
  [Chemistry], [B], [A-],
)
```

For rowspan:

```typst
table.cell(rowspan: 2)[Spans two rows]
```

### Manual lines

```typst
#set table.hline(stroke: 0.6pt)

#table(
  stroke: none,
  columns: (auto, 1fr),
  [09:00], [Opening],
  [10:00], [Talk],
  table.hline(start: 1),   // line only under second column
  [12:00], [_Lunch_],
  table.hline(start: 1),
  [14:00], [Workshop],
  table.hline(),            // full-width line
)
```

### Styled table with show rules

```typst
#show table.cell.where(y: 0): strong
#show table.cell.where(x: 0): strong

#set table(
  stroke: (x, y) => if y == 0 { (bottom: 0.7pt) },
  align: (x, _) => if x > 0 { center } else { left },
)
```

### Importing table sub-elements

```typst
#import table: cell, header

#table(
  columns: 2,
  header([*A*], [*B*]),
  cell(fill: green.lighten(80%))[Pass], [OK],
)
```

## Grid vs Table

`grid` is for layout; `table` is for data. They share the same API but differ in defaults:

| | Table | Grid |
|---|---|---|
| `stroke` | `1pt + black` | `none` |
| `inset` | `5pt` | `0pt` |
| Semantics | Tabular data (accessible) | Visual layout |

Use `grid` for positioning elements side-by-side, multi-column forms, etc. Use `table` for data that a screen reader should navigate as rows/columns.

```typst
#grid(
  columns: (1fr, 1fr),
  gutter: 20pt,
  [Left column content],
  [Right column content],
)
```

## Figures

### Image figure with caption

```typst
#figure(
  image("chart.png", width: 80%),
  caption: [Experimental results.],
) <fig:results>

See @fig:results for details.
```

### Table figure (caption on top)

```typst
#show figure.where(kind: table): set figure.caption(position: top)

#figure(
  table(
    columns: 3,
    table.header([*A*], [*B*], [*C*]),
    [1], [2], [3],
  ),
  caption: [Summary statistics.],
) <tab:summary>
```

### Figure placement

```typst
#figure(
  placement: top,       // float to top of page
  image("fig.png"),
  caption: [A figure.],
)
// placement options: none (inline), auto, top, bottom
```

In multi-column layouts, use `scope: "parent"` for full-width figures:

```typst
#figure(
  placement: bottom,
  scope: "parent",
  image("wide.png", width: 100%),
  caption: [Full-width figure.],
)
```

### Figure numbering

Figures auto-detect their kind (image, table, raw). Each kind has a separate counter:

```typst
#set figure(numbering: "1")       // applies to all kinds

// Access kind-specific counter
#context counter(figure.where(kind: image)).get()
#context counter(figure.where(kind: table)).get()
```

### Custom figure kinds

```typst
#figure(
  rect[Diagram],
  caption: [Network topology.],
  kind: "diagram",
  supplement: [Diagram],
)
```

## Page setup

### Basic configuration

```typst
#set page(
  paper: "a4",                    // or "us-letter", "a5", etc.
  margin: (x: 2.5cm, y: 2.5cm),  // or (top:, bottom:, left:, right:)
  numbering: "1",
)
```

### Headers and footers

```typst
#set page(
  header: [_My Document_ #h(1fr) Draft],
  footer: context [
    #h(1fr) #counter(page).display("1 / 1", both: true)
  ],
)
```

`both: true` in the numbering pattern passes both current and total page numbers.

### Conditional header (skip first page)

```typst
#set page(header: context {
  if counter(page).get().first() > 1 [
    #emph[Document Title] #h(1fr) #counter(page).display()
  ]
})
```

### Background and foreground

```typst
#set page(background: place(
  top + right,
  dx: -10pt, dy: 10pt,
  rotate(-45deg, text(24pt, fill: red.lighten(70%))[DRAFT]),
))
```

### Landscape

```typst
#set page(flipped: true)
```

### Multi-column document

```typst
#set page(columns: 2)
```

Or for a specific section:

```typst
#columns(2, gutter: 12pt)[
  Content here...
  #colbreak()
  More content...
]
```

## Layout primitives

### align

```typst
#align(center)[Centered]
#align(right + bottom)[Bottom-right]
#set align(center)   // sets default for block
```

For inline same-line spacing, use `#h(1fr)` instead:

```typst
Left #h(1fr) Right
```

### stack

```typst
#stack(dir: ltr, spacing: 12pt,
  rect(width: 40pt, fill: red),
  rect(width: 60pt, fill: blue),
  rect(width: 40pt, fill: green),
)
```

Directions: `ltr`, `rtl`, `ttb` (default), `btt`.

### box and block

- `box` is inline — stays in the text flow
- `block` is block-level — creates a paragraph break

```typst
#box(fill: aqua, inset: 4pt, radius: 2pt)[inline box]

#block(fill: luma(230), inset: 12pt, radius: 4pt, width: 100%)[
  Block-level content with full width.
]
```

### place

Position content absolutely relative to the parent:

```typst
#place(top + right)[Logo]
#place(center + horizon)[Centered overlay]
```

### pad

Add or remove spacing:

```typst
#pad(x: 20pt)[Indented content]
#pad(left: -1cm)[Extend into left margin]  // negative values extend
```

### v and h (spacing)

```typst
#v(1em)          // vertical space
#h(2em)          // horizontal space
Left #h(1fr) Right  // fractional: push apart
```

### Transforms (visual only — no layout reflow)

These transform content visually but do NOT change layout — surrounding elements see the original size:

```typst
#rotate(-90deg)[Vertical text]
#rotate(90deg, reflow: true)[Reflows layout around rotated bounds]
#scale(150%)[Bigger]
#scale(x: -100%)[Mirrored]
#move(dx: 10pt, dy: -5pt)[Shifted without affecting layout]
#hide[Invisible but takes space]    // useful for alignment tricks
```

**Gotcha**: Rotated/scaled content can overlap neighbors. Use `reflow: true` or wrap in a sized `box` to reserve space.

### measure and layout (responsive sizing)

```typst
// Measure content dimensions (requires context)
#context {
  let size = measure([Hello World])
  [Width: #size.width, Height: #size.height]
}

// Get current container dimensions
#layout(size => [Available: #size.width × #size.height])

// Responsive: adapt based on available space
#layout(size => {
  if size.width > 400pt { columns(2)[#body] } else { body }
})
```

`measure` without width constraints assumes infinite space — measured dimensions may differ from final layout.

## Images

```typst
#image("photo.jpg", width: 80%)
#image("diagram.svg", height: 4cm)
#image("icon.png", width: 1em, fit: "contain")
```

Supported formats: PNG, JPG, GIF, SVG, PDF, WebP. Always add `alt` text for accessibility:

```typst
#image("chart.png", width: 80%, alt: "Bar chart showing revenue growth")
```

To make images inline (not block-level), wrap in `box`:

```typst
#box(image("icon.svg", height: 1em)) Some text
```
